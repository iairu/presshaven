<?php
declare(strict_types = 1);
namespace Automattic\WooCommerce\EmailEditor\Engine;
if (!defined('ABSPATH')) exit;
use Automattic\WooCommerce\EmailEditor\Engine\PersonalizationTags\HTML_Tag_Processor;
use Automattic\WooCommerce\EmailEditor\Engine\PersonalizationTags\Personalization_Tag;
use Automattic\WooCommerce\EmailEditor\Engine\PersonalizationTags\Personalization_Tags_Registry;
class Personalizer {
private const TAG_NAME_PATTERN = '[a-zA-Z0-9\-\/]+';
public const RENDERING_CONTEXT_HTML = 'html';
public const RENDERING_CONTEXT_TEXT = 'text';
public const RENDERING_CONTEXT_HREF = 'href';
public const RENDERING_CONTEXT_KEY = 'rendering_context';
private Personalization_Tags_Registry $tags_registry;
private array $context;
private $value_interceptor = null;
public function __construct( Personalization_Tags_Registry $tags_registry ) {
$this->tags_registry = $tags_registry;
$this->context = array();
}
public function set_context( array $context ) {
$this->context = $context;
}
public function get_context(): array {
return $this->context;
}
public function set_value_interceptor( ?callable $interceptor ): ?callable {
$previous = $this->value_interceptor;
$this->value_interceptor = $interceptor;
return $previous;
}
private function intercept_value( string $value, string $source, string $rendering_context ): string {
if ( null === $this->value_interceptor ) {
return $value;
}
return ( $this->value_interceptor )( $value, $source, $rendering_context );
}
public function personalize_content( string $content, string $rendering_context = self::RENDERING_CONTEXT_HTML ): string {
if ( ! in_array( $rendering_context, array( self::RENDERING_CONTEXT_HTML, self::RENDERING_CONTEXT_TEXT ), true ) ) {
$rendering_context = self::RENDERING_CONTEXT_HTML;
}
$content_processor = new HTML_Tag_Processor( $content );
while ( $content_processor->next_token() ) {
if ( $content_processor->get_token_type() === '#comment' ) {
$modifiable_text = $content_processor->get_modifiable_text();
$token = $this->parse_token( $modifiable_text );
$tag = $this->tags_registry->get_by_token( $token['token'] );
if ( ! $tag ) {
continue;
}
$value = $tag->execute_callback( $this->get_callback_context( $rendering_context ), $token['arguments'] );
if ( self::RENDERING_CONTEXT_HTML === $rendering_context && Personalization_Tag::VALUE_TYPE_TEXT === $tag->get_value_type() ) {
$value = esc_html( $value );
}
$value = $this->intercept_value( (string) $value, trim( $modifiable_text ), $rendering_context );
$content_processor->replace_token( $value );
} elseif ( $content_processor->get_token_type() === '#tag' && $content_processor->get_tag() === 'TITLE' ) {
$modifiable_text = $content_processor->get_modifiable_text();
$title = $this->personalize_content( $modifiable_text, self::RENDERING_CONTEXT_TEXT );
$content_processor->set_modifiable_text( $title );
} elseif ( $content_processor->get_token_type() === '#tag' && $content_processor->get_tag() === 'A' && $content_processor->get_attribute( 'data-link-href' ) ) {
$href = (string) $content_processor->get_attribute( 'data-link-href' );
$token = $this->parse_token( $href );
$tag = $this->tags_registry->get_by_token( $token['token'] );
if ( ! $tag ) {
continue;
}
$value = $tag->execute_callback( $this->get_callback_context( self::RENDERING_CONTEXT_HREF ), $token['arguments'] );
$value = $this->replace_link_href( $href, $tag->get_token(), $value );
$value = $this->intercept_value( $value, $href, self::RENDERING_CONTEXT_HREF );
if ( '' !== $value ) {
$content_processor->set_attribute( 'href', $value );
$content_processor->remove_attribute( 'data-link-href' );
$content_processor->remove_attribute( 'contenteditable' );
}
} elseif ( $content_processor->get_token_type() === '#tag' && $content_processor->get_tag() === 'A' ) {
$href = $content_processor->get_attribute( 'href' );
if ( ! is_string( $href ) ) {
continue;
}
$personalized_href = $this->personalize_href_tokens( $href );
if ( null !== $personalized_href ) {
$content_processor->set_attribute( 'href', $personalized_href );
}
}
}
$content_processor->flush_updates();
return $content_processor->get_updated_html();
}
private function personalize_href_tokens( string $href ): ?string {
$decoded_href = html_entity_decode( urldecode( $href ), ENT_QUOTES, 'UTF-8' );
if ( ! preg_match_all( '/\[' . self::TAG_NAME_PATTERN . '(?:\s+[^\]]+)?\]/', $decoded_href, $matches ) ) {
return null;
}
$replacements = array();
foreach ( array_unique( $matches[0] ) as $token_string ) {
$token = $this->parse_token( $token_string );
$tag = $this->tags_registry->get_by_token( $token['token'] );
if ( ! $tag ) {
continue;
}
$value = $tag->execute_callback( $this->get_callback_context( self::RENDERING_CONTEXT_HREF ), $token['arguments'] );
$value = $this->intercept_value( $value, $token_string, self::RENDERING_CONTEXT_HREF );
if ( '' !== $value ) {
$replacements[ $token_string ] = $value;
}
}
if ( ! $replacements ) {
return null;
}
$base = $href;
foreach ( array_keys( $replacements ) as $token_string ) {
if ( substr_count( $href, $token_string ) !== substr_count( $decoded_href, $token_string ) ) {
$base = $decoded_href;
break;
}
}
if ( preg_match( '#^https?://(\[' . self::TAG_NAME_PATTERN . '(?:\s+[^\]]+)?\])#i', $base, $prefix_match ) && isset( $replacements[ $prefix_match[1] ] ) ) {
$base = (string) preg_replace( '#^https?://#i', '', $base );
}
return strtr( $base, $replacements );
}
private function get_callback_context( string $rendering_context ): array {
return array_replace( $this->context, array( self::RENDERING_CONTEXT_KEY => $rendering_context ) );
}
private function parse_token( string $token ): array {
$result = array(
'token' => '',
'arguments' => array(),
);
if ( preg_match( '/^\[(' . self::TAG_NAME_PATTERN . ')\s*(.*?)\]$/', trim( $token ), $matches ) ) {
$result['token'] = "[{$matches[1]}]";
$attributes_string = $matches[2];
if ( preg_match_all( '/(\w+)=(?:"([^"]*)"|\'([^\']*)\'|([^\s\]]+(?:\s+(?!\w+=)[^\s\]]+)*))/', $attributes_string, $attribute_matches, PREG_SET_ORDER ) ) {
foreach ( $attribute_matches as $attribute ) {
$double_quoted_value = $attribute[2] ?? '';
$single_quoted_value = $attribute[3] ?? '';
$unquoted_value = $attribute[4] ?? '';
if ( '' !== $double_quoted_value ) {
$result['arguments'][ $attribute[1] ] = $double_quoted_value;
} elseif ( '' !== $single_quoted_value ) {
$result['arguments'][ $attribute[1] ] = $single_quoted_value;
} else {
$result['arguments'][ $attribute[1] ] = $unquoted_value;
}
}
}
}
return $result;
}
private function replace_link_href( string $content, string $token, string $replacement ) {
$escaped_shortcode = preg_quote( substr( $token, 1, strlen( $token ) - 2 ), '/' );
$pattern = '/\[' . $escaped_shortcode . '(?:\s+[^\]]+)?\]/';
return trim( (string) preg_replace( $pattern, addcslashes( $replacement, '\\$' ), $content ) );
}
}
