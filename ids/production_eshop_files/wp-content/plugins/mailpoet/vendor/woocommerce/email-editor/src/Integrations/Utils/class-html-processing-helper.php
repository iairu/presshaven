<?php
declare( strict_types = 1 );
namespace Automattic\WooCommerce\EmailEditor\Integrations\Utils;
if (!defined('ABSPATH')) exit;
class Html_Processing_Helper {
public static function clean_css_classes( string $classes ): string {
if ( strlen( $classes ) > 1000 ) {
$classes = substr( $classes, 0, 1000 );
}
$result = preg_replace( '/\bhas-background\b/', '', $classes );
if ( null === $result ) {
$classes = '';
} else {
$classes = $result;
}
$result = preg_replace( '/\bhas-[a-z-]*border[a-z-]*\b/', '', $classes );
if ( null === $result ) {
$classes = '';
} else {
$classes = $result;
}
$result = preg_replace( '/\b[a-z-]+-border-[a-z-]+\b/', '', $classes );
if ( null === $result ) {
$classes = '';
} else {
$classes = $result;
}
$result = preg_replace( '/\s+/', ' ', $classes );
if ( null === $result ) {
$classes = '';
} else {
$classes = $result;
}
return trim( $classes );
}
public static function remove_wrapper_handled_classes( \WP_HTML_Tag_Processor $html ): void {
$class_attribute = $html->get_attribute( 'class' );
if ( ! is_string( $class_attribute ) ) {
return;
}
$class_names = preg_split( '/\s+/', trim( $class_attribute ) );
if ( ! is_array( $class_names ) ) {
return;
}
foreach ( $class_names as $class_name ) {
if ( '' !== $class_name && self::is_wrapper_handled_class( $class_name ) ) {
$html->remove_class( $class_name );
}
}
}
private static function is_wrapper_handled_class( string $class_name ): bool {
if ( 'has-background' === $class_name ) {
return true;
}
if ( str_starts_with( $class_name, 'has-' ) && str_ends_with( $class_name, '-background-color' ) ) {
return true;
}
return false !== strpos( $class_name, '-border-' );
}
public static function sanitize_css_value( string $value ): string {
$result = preg_replace( '/[<>]/', '', $value );
if ( null === $result ) {
$value = '';
} else {
$value = $result;
}
$dangerous_patterns = array(
'/expression\s*\(/i',
'/url\s*\(\s*javascript\s*:/i',
'/url\s*\(\s*data\s*:/i',
'/url\s*\(\s*vbscript\s*:/i',
'/import\s*\(/i',
'/behavior\s*:/i',
'/binding\s*:/i',
'/filter\s*:/i',
'/progid\s*:/i',
);
foreach ( $dangerous_patterns as $pattern ) {
if ( preg_match( $pattern, $value ) ) {
return '';
}
}
return trim( $value );
}
public static function sanitize_dimension_value( $value ): string {
if ( ! is_string( $value ) && ! is_numeric( $value ) ) {
return '';
}
$value = (string) $value;
if ( is_numeric( $value ) ) {
$value = $value . 'px';
}
$sanitized_value = self::sanitize_css_value( $value );
if ( ! empty( $sanitized_value ) && preg_match( '/^(\d+(?:\.\d+)?)(px|em|rem|%|vh|vw|ex|ch|in|cm|mm|pt|pc)$/', $sanitized_value ) ) {
return $sanitized_value;
}
return '';
}
public static function sanitize_color( string $color ): string {
$color = trim( $color );
if ( preg_match( '/^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/', $color ) ) {
return strtolower( $color );
}
if ( preg_match( '/^rgba?\(\s*(25[0-5]|2[0-4]\d|1\d{2}|\d{1,2})\s*,\s*(25[0-5]|2[0-4]\d|1\d{2}|\d{1,2})\s*,\s*(25[0-5]|2[0-4]\d|1\d{2}|\d{1,2})\s*(?:,\s*(?:1(?:\.0+)?|0(?:\.\d+)?|\.\d+)\s*)?\)$/', $color ) ) {
return $color;
}
if ( preg_match( '/^hsla?\(\s*(360|3[0-5]\d|[12]\d{2}|\d{1,2})\s*,\s*(100|[1-9]?\d)%\s*,\s*(100|[1-9]?\d)%\s*(?:,\s*(?:1(?:\.0+)?|0(?:\.\d+)?|\.\d+)\s*)?\)$/', $color ) ) {
return $color;
}
if ( preg_match( '/^[a-zA-Z][a-zA-Z0-9-]*$/', $color ) && ! preg_match( '/^(expression|javascript|vbscript|data|import|behavior|binding|filter|progid)/i', $color ) ) {
return strtolower( $color );
}
if ( preg_match( '/^var\(--[a-zA-Z0-9\-_]+\)$/', $color ) ) {
return $color;
}
return '#000000';
}
private static function normalize_rel_attribute( ?string $rel_value, bool $require_security_tokens = false ): string {
$allowed_tokens = array( 'noopener', 'noreferrer', 'nofollow', 'external' );
$required_tokens = $require_security_tokens ? array( 'noopener', 'noreferrer' ) : array();
if ( null === $rel_value && empty( $required_tokens ) ) {
return '';
}
$tokens = $required_tokens;
if ( null !== $rel_value ) {
$existing_tokens = preg_split( '/\s+/', trim( $rel_value ) );
if ( false !== $existing_tokens ) {
$normalized_existing = array_filter(
array_map( 'strtolower', $existing_tokens ),
function ( $token ) use ( $allowed_tokens ) {
return ! empty( $token ) && in_array( $token, $allowed_tokens, true );
}
);
$tokens = array_unique( array_merge( $tokens, $normalized_existing ) );
}
}
return empty( $tokens ) ? '' : implode( ' ', $tokens );
}
public static function validate_caption_attribute( \WP_HTML_Tag_Processor $html, string $attr_name ): void {
$attr_value = $html->get_attribute( $attr_name );
if ( null === $attr_value ) {
return;
}
if ( str_starts_with( $attr_name, 'on' ) ) {
$html->remove_attribute( $attr_name );
return;
}
switch ( $attr_name ) {
case 'href':
if ( ! preg_match( '/^(https?:\/\/|mailto:|tel:)/i', (string) $attr_value ) ) {
$html->remove_attribute( $attr_name );
break;
}
$sanitized_url = esc_url_raw( (string) $attr_value );
if ( empty( $sanitized_url ) ) {
$html->remove_attribute( $attr_name );
} else {
$html->set_attribute( $attr_name, $sanitized_url );
}
break;
case 'target':
$allowed_targets = array( '_blank', '_self' );
$target_value = strtolower( (string) $attr_value );
if ( ! in_array( $target_value, $allowed_targets, true ) ) {
$html->remove_attribute( $attr_name );
} elseif ( '_blank' === $target_value ) {
$current_rel = $html->get_attribute( 'rel' );
$rel_value = is_string( $current_rel ) ? $current_rel : null;
$normalized_rel = self::normalize_rel_attribute( $rel_value, true );
$html->set_attribute( 'rel', $normalized_rel );
}
break;
case 'rel':
$rel_value = is_string( $attr_value ) ? $attr_value : null;
$normalized_rel = self::normalize_rel_attribute( $rel_value, false );
if ( empty( $normalized_rel ) ) {
$html->remove_attribute( $attr_name );
} else {
$html->set_attribute( $attr_name, $normalized_rel );
}
break;
case 'style':
$safe_properties = self::get_safe_css_properties();
$sanitized_styles = array();
$style_parts = explode( ';', (string) $attr_value );
foreach ( $style_parts as $style_part ) {
$style_part = trim( $style_part );
if ( empty( $style_part ) ) {
continue;
}
$property_parts = explode( ':', $style_part, 2 );
if ( count( $property_parts ) !== 2 ) {
continue;
}
$property = trim( strtolower( $property_parts[0] ) );
$value = trim( $property_parts[1] );
if ( in_array( $property, $safe_properties, true ) ) {
$sanitized_value = self::sanitize_css_value( $value );
if ( ! empty( $sanitized_value ) ) {
$sanitized_styles[] = $property . ': ' . $sanitized_value;
}
}
}
if ( empty( $sanitized_styles ) ) {
$html->remove_attribute( $attr_name );
} else {
$html->set_attribute( $attr_name, implode( '; ', $sanitized_styles ) );
}
break;
case 'class':
if ( ! preg_match( '/^[a-zA-Z0-9\s\-_]+$/', (string) $attr_value ) ) {
$html->remove_attribute( $attr_name );
}
break;
case 'data-type':
case 'data-id':
if ( ! preg_match( '/^[a-zA-Z0-9\-_]+$/', (string) $attr_value ) ) {
$html->remove_attribute( $attr_name );
}
break;
default:
if ( str_starts_with( $attr_name, 'data-' ) ) {
if ( ! preg_match( '/^[a-zA-Z0-9\-_]+$/', (string) $attr_value ) ) {
$html->remove_attribute( $attr_name );
}
break;
}
$html->remove_attribute( $attr_name );
break;
}
}
public static function get_safe_css_properties(): array {
return array(
'color',
'background-color',
'font-family',
'font-size',
'font-weight',
'font-style',
'text-decoration',
'text-align',
'line-height',
'letter-spacing',
'text-transform',
);
}
public static function get_caption_css_properties(): array {
return array(
'font-family',
'font-size',
'font-weight',
'font-style',
'text-decoration',
'line-height',
'letter-spacing',
'text-transform',
);
}
public static function validate_container_attributes( string $container_html ): bool {
$html = new \WP_HTML_Tag_Processor( $container_html );
if ( ! $html->next_tag() ) {
return false;
}
$attributes = $html->get_attribute_names_with_prefix( '' );
if ( is_array( $attributes ) ) {
foreach ( $attributes as $attr_name ) {
$attr_value = $html->get_attribute( $attr_name );
if ( null === $attr_value ) {
continue;
}
if ( str_starts_with( $attr_name, 'on' ) ) {
return false;
}
$escaped_value = htmlspecialchars( (string) $attr_value, ENT_QUOTES, 'UTF-8' );
$temp_html = new \WP_HTML_Tag_Processor( '<span ' . $attr_name . '="' . $escaped_value . '">test</span>' );
if ( $temp_html->next_tag() ) {
$original_value = $temp_html->get_attribute( $attr_name );
self::validate_caption_attribute( $temp_html, $attr_name );
$validated_value = $temp_html->get_attribute( $attr_name );
if ( null !== $original_value && null === $validated_value ) {
return false;
}
}
}
}
return true;
}
public static function sanitize_caption_html( string $caption_html ): string {
if ( false === strpos( $caption_html, '<' ) ) {
return $caption_html;
}
foreach ( array( 'script', 'style', 'iframe', 'object', 'embed', 'form', 'input', 'button' ) as $tag ) {
$result = preg_replace( '/<' . $tag . '\b[^>]*>.*?<\/' . $tag . '>/is', '', $caption_html );
if ( null !== $result ) {
$caption_html = $result;
}
}
$caption_html = wp_kses( $caption_html, self::get_allowed_caption_html(), array( 'http', 'https', 'mailto', 'tel' ) );
$html = new \WP_HTML_Tag_Processor( $caption_html );
while ( $html->next_tag() ) {
$attributes = $html->get_attribute_names_with_prefix( '' );
if ( is_array( $attributes ) ) {
foreach ( $attributes as $attr_name ) {
self::validate_caption_attribute( $html, $attr_name );
}
}
}
return $html->get_updated_html();
}
private static function get_allowed_caption_html(): array {
$common_attributes = array(
'class' => true,
'style' => true,
'data-*' => true,
);
return array(
'a' => array_merge(
$common_attributes,
array(
'href' => true,
'target' => true,
'rel' => true,
)
),
'br' => $common_attributes,
'em' => $common_attributes,
'kbd' => $common_attributes,
'mark' => $common_attributes,
's' => $common_attributes,
'span' => $common_attributes,
'strong' => $common_attributes,
'sub' => $common_attributes,
'sup' => $common_attributes,
);
}
public static function sanitize_image_html( string $image_html ): string {
if ( false === strpos( $image_html, '<' ) ) {
return $image_html;
}
if ( ! preg_match( '/<img[^>]*>/i', $image_html, $matches ) ) {
return $image_html;
}
$img_tag = $matches[0];
$sanitized_attributes = array();
$has_src = false;
$html = new \WP_HTML_Tag_Processor( $img_tag );
if ( $html->next_tag() ) {
$attributes = $html->get_attribute_names_with_prefix( '' );
if ( is_array( $attributes ) ) {
foreach ( $attributes as $attr_name ) {
$attr_value = $html->get_attribute( $attr_name );
switch ( $attr_name ) {
case 'src':
$sanitized_src = esc_url( (string) $attr_value );
if ( ! empty( $sanitized_src ) ) {
$sanitized_attributes[] = $attr_name . '="' . $sanitized_src . '"';
$has_src = true;
}
break;
case 'alt':
case 'width':
case 'height':
$sanitized_attributes[] = $attr_name . '="' . esc_attr( (string) $attr_value ) . '"';
break;
case 'class':
$cleaned_classes = self::clean_css_classes( (string) $attr_value );
if ( ! empty( $cleaned_classes ) ) {
$sanitized_attributes[] = $attr_name . '="' . esc_attr( $cleaned_classes ) . '"';
}
break;
case 'style':
$sanitized_styles = self::sanitize_image_styles( (string) $attr_value );
if ( ! empty( $sanitized_styles ) ) {
$sanitized_attributes[] = $attr_name . '="' . esc_attr( $sanitized_styles ) . '"';
}
break;
}
}
}
}
if ( ! $has_src ) {
return '';
}
if ( empty( $sanitized_attributes ) ) {
return '';
}
return '<img ' . implode( ' ', $sanitized_attributes ) . '>';
}
public static function extract_url_from_text( string $text ): string {
if ( preg_match( '/(?<![a-zA-Z0-9.-])https?:\/\/[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}[a-zA-Z0-9\/?=&%_.~+#-]*(?![a-zA-Z0-9._~+#-])/', $text, $matches ) ) {
return $matches[0];
}
return '';
}
private static function sanitize_image_styles( string $style_value ): string {
$sanitized_styles = array();
$style_parts = explode( ';', $style_value );
foreach ( $style_parts as $style_part ) {
$style_part = trim( $style_part );
if ( empty( $style_part ) ) {
continue;
}
$property_parts = explode( ':', $style_part, 2 );
if ( count( $property_parts ) !== 2 ) {
continue;
}
$property = trim( strtolower( $property_parts[0] ) );
$value = trim( $property_parts[1] );
$safe_properties = array( 'width', 'height', 'max-width', 'max-height', 'display', 'margin', 'padding', 'border', 'border-radius' );
if ( in_array( $property, $safe_properties, true ) ) {
$sanitized_value = self::sanitize_css_value( $value );
if ( ! empty( $sanitized_value ) ) {
$sanitized_styles[] = $property . ': ' . $sanitized_value;
}
}
}
return implode( '; ', $sanitized_styles );
}
}
