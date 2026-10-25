<?php
declare( strict_types = 1 );
namespace Automattic\WooCommerce\EmailEditor\Engine\Renderer;
if (!defined('ABSPATH')) exit;
class Html2Text {
public static function default_options(): array {
return array(
'ignore_errors' => false,
'drop_links' => false,
'char_set' => 'auto',
);
}
public static function convert( string $html, $options = array() ): string {
if ( false === $options || true === $options ) {
$options = array( 'ignore_errors' => $options );
}
$options = array_merge( static::default_options(), $options );
foreach ( array_keys( $options ) as $key ) {
if ( ! in_array( $key, array_keys( static::default_options() ), true ) ) {
error_log( 'Html2Text: Invalid option provided: ' . htmlspecialchars( (string) $key, ENT_QUOTES, 'UTF-8' ) . '. Valid options are: ' . htmlspecialchars( implode( ',', array_keys( static::default_options() ) ), ENT_QUOTES, 'UTF-8' ) );
throw new \InvalidArgumentException( 'Invalid option provided for html2text conversion.' );
}
}
$is_office_document = self::is_office_document( $html );
if ( $is_office_document ) {
$html = str_replace( array( '<o:p>', '</o:p>' ), '', $html );
}
$html = self::fix_newlines( $html );
if ( PHP_MAJOR_VERSION * 10 + PHP_MINOR_VERSION < 81 && mb_detect_encoding( $html, 'UTF-8', true ) ) {
$converted = mb_convert_encoding( $html, 'HTML-ENTITIES', 'UTF-8' );
$html = false !== $converted ? $converted : $html;
}
if ( ! is_string( $html ) ) {
$html = (string) $html;
}
$doc = self::get_document( $html, $options );
$output = self::iterate_over_node( $doc, null, false, $is_office_document, $options );
$output = self::process_whitespace_newlines( $output );
return $output;
}
public static function fix_newlines( string $text ): string {
$text = str_replace( "\r\n", "\n", $text );
$text = str_replace( "\r", "\n", $text );
return $text;
}
public static function nbsp_codes(): array {
return array(
"\xc2\xa0",
"\u00a0",
);
}
public static function zwnj_codes(): array {
return array(
"\xe2\x80\x8c",
"\u200c",
);
}
public static function process_whitespace_newlines( string $text ): string {
$result = preg_replace( '/ *\t */im', "\t", $text );
$text = null !== $result ? $result : $text;
$text = ltrim( $text );
$result = preg_replace( "/\n[ \t]*/im", "\n", $text );
$text = null !== $result ? $result : $text;
$text = self::render_text( $text );
$text = rtrim( $text );
$result = preg_replace( "/[ \t]*\n/im", "\n", $text );
$text = null !== $result ? $result : $text;
$text = self::fix_newlines( $text );
$result = preg_replace( "/\n\n\n*/im", "\n\n", $text );
return null !== $result ? $result : $text;
}
public static function is_office_document( string $html ): bool {
return strpos( $html, 'urn:schemas-microsoft-com:office' ) !== false;
}
public static function is_whitespace( string $text ): bool {
return 0 === strlen( trim( self::render_text( $text ), "\n\r\t " ) );
}
private static function get_document( string $html, array $options ): \DOMDocument {
$doc = new \DOMDocument();
$html = trim( $html );
if ( ! $html ) {
return $doc;
}
if ( '<' !== $html[0] ) {
$html = '<body>' . $html . '</body>';
}
$header = '';
if ( PHP_MAJOR_VERSION * 10 + PHP_MINOR_VERSION >= 81 ) {
$char_set = ! empty( $options['char_set'] ) && is_string( $options['char_set'] ) ? $options['char_set'] : 'auto';
if ( 'auto' === $char_set ) {
$detected = mb_detect_encoding( $html );
$char_set = false !== $detected ? $detected : 'UTF-8';
} elseif ( strpos( $char_set, ',' ) !== false ) {
$encoding_list = explode( ',', $char_set );
$encoding_list = array_map( 'trim', $encoding_list );
$encoding_list = array_filter(
$encoding_list,
function ( $encoding ) {
return ! empty( $encoding );
}
);
if ( ! empty( $encoding_list ) ) {
$encoding_list = array_values( $encoding_list );
mb_detect_order( $encoding_list );
$detected = mb_detect_encoding( $html );
$char_set = false !== $detected ? $detected : 'UTF-8';
}
}
if ( strpos( $char_set, '1252' ) !== false ) {
$options['ignore_errors'] = true;
}
$header = '<?xml version="1.0" encoding="' . $char_set . '">';
}
if ( ! empty( $options['ignore_errors'] ) ) {
$doc->strictErrorChecking = false;
$doc->recover = true;
$doc->xmlStandalone = true;
$old_internal_errors = libxml_use_internal_errors( true );
$load_result = $doc->loadHTML( $header . $html, LIBXML_NOWARNING | LIBXML_NOERROR | LIBXML_NONET | LIBXML_PARSEHUGE );
libxml_use_internal_errors( $old_internal_errors );
} else {
$load_result = $doc->loadHTML( $header . $html );
}
if ( ! $load_result ) {
$html_preview = strlen( $html ) > 500 ? substr( $html, 0, 500 ) . '...[truncated]' : $html;
error_log( 'Html2Text: Failed to load HTML content: ' . htmlspecialchars( $html_preview, ENT_QUOTES, 'UTF-8' ) );
throw new Html2Text_Exception( 'Could not load HTML - the content may be malformed.' );
}
return $doc;
}
private static function render_text( string $text ): string {
$text = str_replace( self::nbsp_codes(), ' ', $text );
$text = str_replace( self::zwnj_codes(), '', $text );
return $text;
}
private static function next_child_name( ?\DOMNode $node ): ?string {
if ( null === $node || null === $node->nextSibling ) {
return null;
}
$next_node = $node->nextSibling;
while ( null !== $next_node ) {
if ( $next_node instanceof \DOMText ) {
if ( ! self::is_whitespace( $next_node->wholeText ) ) {
break;
}
}
if ( $next_node instanceof \DOMElement ) {
break;
}
$next_node = $next_node->nextSibling;
}
$next_name = null;
if ( $next_node instanceof \DOMElement || $next_node instanceof \DOMText ) {
$next_name = strtolower( $next_node->nodeName );
}
return $next_name;
}
private static function iterate_over_node( \DOMNode $node, ?string $prev_name, bool $in_pre, bool $is_office_document, array $options ): string {
if ( $node instanceof \DOMText ) {
if ( $in_pre ) {
$text = "\n" . trim( self::render_text( $node->wholeText ), "\n\r\t " ) . "\n";
$result = preg_replace( "/[ \t]*\n/im", "\n", $text );
$text = null !== $result ? $result : $text;
return str_replace( "\n", "\r", $text );
}
$text = self::render_text( $node->wholeText );
$result = preg_replace( "/[\\t\\n\\f\\r ]+/im", ' ', $text );
$text = null !== $result ? $result : $text;
if ( ! self::is_whitespace( $text ) && ( 'p' === $prev_name || 'div' === $prev_name ) ) {
return "\n" . $text;
}
return $text;
}
if ( $node instanceof \DOMDocumentType || $node instanceof \DOMProcessingInstruction ) {
return '';
}
$name = strtolower( $node->nodeName );
$next_name = self::next_child_name( $node );
switch ( $name ) {
case 'hr':
$prefix = '';
if ( null !== $prev_name ) {
$prefix = "\n";
}
return $prefix . "---------------------------------------------------------------\n";
case 'style':
case 'head':
case 'title':
case 'meta':
case 'script':
return '';
case 'h1':
case 'h2':
case 'h3':
case 'h4':
case 'h5':
case 'h6':
case 'ol':
case 'ul':
case 'pre':
$output = "\n\n";
break;
case 'td':
case 'th':
$output = "\t";
break;
case 'p':
if ( $is_office_document && $node instanceof \DOMElement && 'MsoNormal' === $node->getAttribute( 'class' ) ) {
$output = '';
$name = 'br';
break;
}
$output = "\n\n";
break;
case 'tr':
$output = "\n";
break;
case 'div':
$output = '';
if ( null !== $prev_name ) {
$output .= "\n";
}
break;
case 'li':
$output = '- ';
break;
default:
$output = '';
break;
}
if ( $node->childNodes->length > 0 ) {
$n = $node->childNodes->item( 0 );
$previous_sibling_names = array();
$previous_sibling_name = null;
$parts = array();
$trailing_whitespace = 0;
while ( null !== $n ) {
$text = self::iterate_over_node( $n, $previous_sibling_name, $in_pre || 'pre' === $name, $is_office_document, $options );
if ( $n instanceof \DOMDocumentType
|| $n instanceof \DOMProcessingInstruction
|| ( $n instanceof \DOMText && self::is_whitespace( $text ) ) ) {
++$trailing_whitespace;
} else {
$previous_sibling_name = strtolower( $n->nodeName );
$previous_sibling_names[] = $previous_sibling_name;
$trailing_whitespace = 0;
}
$node->removeChild( $n );
$n = $node->childNodes->item( 0 );
$parts[] = $text;
}
while ( $trailing_whitespace-- > 0 ) {
array_pop( $parts );
}
$last_name = array_pop( $previous_sibling_names );
if ( 'br' === $last_name ) {
$last_name = array_pop( $previous_sibling_names );
if ( '#text' === $last_name ) {
array_pop( $parts );
}
}
$output .= implode( '', $parts );
}
switch ( $name ) {
case 'h1':
case 'h2':
case 'h3':
case 'h4':
case 'h5':
case 'h6':
case 'pre':
case 'p':
$output .= "\n\n";
break;
case 'br':
$output .= "\n";
break;
case 'div':
break;
case 'a':
$href = $node instanceof \DOMElement ? $node->getAttribute( 'href' ) : '';
$output = trim( $output );
if ( '[' === substr( $output, 0, 1 ) && ']' === substr( $output, -1 ) ) {
$output = substr( $output, 1, strlen( $output ) - 2 );
if ( $node instanceof \DOMElement && $node->getAttribute( 'title' ) ) {
$output = $node->getAttribute( 'title' );
}
}
if ( ! $output && $node instanceof \DOMElement && $node->getAttribute( 'title' ) ) {
$output = $node->getAttribute( 'title' );
}
if ( ! $href ) {
if ( $node instanceof \DOMElement && $node->getAttribute( 'name' ) ) {
if ( $options['drop_links'] ) {
$output = "$output";
} else {
$output = "[$output]";
}
}
} elseif ( $href === $output || "mailto:$output" === $href || "http://$output" === $href || "https://$output" === $href ) {
$output = "$output";
} elseif ( $output ) {
if ( $options['drop_links'] ) {
$output = "$output";
} else {
$output = "[$output]($href)";
}
} else {
$output = "$href";
}
switch ( $next_name ) {
case 'h1':
case 'h2':
case 'h3':
case 'h4':
case 'h5':
case 'h6':
$output .= "\n";
break;
}
break;
case 'img':
if ( $node instanceof \DOMElement && $node->getAttribute( 'title' ) ) {
$output = '[' . $node->getAttribute( 'title' ) . ']';
} elseif ( $node instanceof \DOMElement && $node->getAttribute( 'alt' ) ) {
$output = '[' . $node->getAttribute( 'alt' ) . ']';
} else {
$output = '';
}
break;
case 'li':
$output .= "\n";
break;
case 'blockquote':
$output = self::process_whitespace_newlines( $output );
$output = "\n" . $output;
$result = preg_replace( "/\n/im", "\n> ", $output );
$output = null !== $result ? $result : $output;
$result = preg_replace( "/\n> >/im", "\n>>", $output );
$output = null !== $result ? $result : $output;
$output = "\n" . $output . "\n\n";
break;
default:
}
return $output;
}
}
