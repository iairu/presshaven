<?php
declare( strict_types = 1 );
namespace Automattic\WooCommerce\EmailEditor\Integrations\Core\Renderer\Blocks;
if (!defined('ABSPATH')) exit;
use Automattic\WooCommerce\EmailEditor\Engine\Renderer\ContentRenderer\Rendering_Context;
use Automattic\WooCommerce\EmailEditor\Integrations\Utils\Dom_Document_Helper;
use Automattic\WooCommerce\EmailEditor\Integrations\Utils\Styles_Helper;
use Automattic\WooCommerce\EmailEditor\Integrations\Utils\Table_Wrapper_Helper;
use Automattic\WooCommerce\EmailEditor\Integrations\Utils\Html_Processing_Helper;
class Table extends Abstract_Block_Renderer {
private const VALID_TEXT_ALIGNMENTS = array( 'left', 'center', 'right' );
protected function render_content( string $block_content, array $parsed_block, Rendering_Context $rendering_context ): string {
$extracted_data = $this->extract_table_and_caption_from_figure( $block_content );
$table_content = $extracted_data['table'];
$caption = $extracted_data['caption'];
if ( ! $this->is_valid_table_content( $table_content ) ) {
return '';
}
if ( ! preg_match( '/<(th|td)/i', $table_content ) ) {
return '';
}
$block_attributes = wp_parse_args(
$parsed_block['attrs'] ?? array(),
array(
'style' => array(),
)
);
$html = new \WP_HTML_Tag_Processor( $table_content );
$classes = 'email-table-block';
if ( $html->next_tag() ) {
$block_classes = (string) ( $html->get_attribute( 'class' ) ?? '' );
$classes .= ' ' . $block_classes;
$block_classes = Html_Processing_Helper::clean_css_classes( $block_classes );
$html->set_attribute( 'class', $block_classes );
$table_content = $html->get_updated_html();
}
$classes = Html_Processing_Helper::clean_css_classes( $classes );
$spacing_styles = Styles_Helper::get_block_styles( $block_attributes, $rendering_context, array( 'spacing' ) );
$table_styles = Styles_Helper::get_block_styles( $block_attributes, $rendering_context, array( 'background-color', 'color', 'typography' ) );
$spacing_css = $spacing_styles['css'] ?? '';
$spacing_css = (string) ( preg_replace( '/background[^;]*;?/', '', $spacing_css ) ?? '' );
$spacing_css = (string) ( preg_replace( '/\s*;\s*;/', ';', $spacing_css ) ?? '' );
$spacing_css = trim( $spacing_css, '; ' );
$spacing_styles['css'] = $spacing_css ? $spacing_css . '; background: transparent !important;' : 'background: transparent !important;';
$additional_styles = array(
'min-width' => '100%',
);
if ( empty( $table_styles['declarations']['color'] ) ) {
$email_styles = $rendering_context->get_theme_styles();
$color = $parsed_block['email_attrs']['color'] ?? $email_styles['color']['text'] ?? '#000000';
$additional_styles['color'] = Html_Processing_Helper::sanitize_color( $color );
}
$additional_styles['text-align'] = $rendering_context->get_default_text_align();
if ( ! empty( $parsed_block['attrs']['textAlign'] ) ) {
$text_align = $rendering_context->sanitize_text_align( $parsed_block['attrs']['textAlign'] );
if ( null !== $text_align ) {
$additional_styles['text-align'] = $text_align;
}
} elseif ( null !== $rendering_context->sanitize_text_align( $parsed_block['attrs']['align'] ?? null ) ) {
$additional_styles['text-align'] = $rendering_context->resolve_text_align( $parsed_block['attrs']['align'] );
}
$table_styles = Styles_Helper::extend_block_styles( $table_styles, $additional_styles );
$is_striped_table = $this->is_striped_table( $block_content, $parsed_block );
$table_content = $this->process_table_content( $table_content, $parsed_block, $rendering_context, $is_striped_table );
$table_content_with_styles = $this->apply_styles_to_table_element( $table_content, $table_styles['css'] );
if ( false !== strpos( $block_content, 'wp-block-table' ) ) {
$table_content_with_styles = $this->add_class_to_table_element( $table_content_with_styles, 'wp-block-table' );
}
$complete_content = $table_content_with_styles;
if ( ! empty( $caption ) ) {
$sanitized_caption = Html_Processing_Helper::sanitize_caption_html( $caption );
$caption_styles = $this->extract_typography_styles_for_caption( $table_styles['css'] );
$complete_content .= '<div style="text-align: center; margin-top: 8px; ' . $caption_styles . '">' . $sanitized_caption . '</div>';
}
$table_attrs = array(
'style' => 'border-collapse: separate;',
'width' => '100%',
);
$cell_attrs = array(
'class' => $classes,
'style' => $spacing_styles['css'],
'align' => $additional_styles['text-align'],
);
$rendered_table = Table_Wrapper_Helper::render_table_wrapper( $complete_content, $table_attrs, $cell_attrs );
return $rendered_table;
}
private function process_table_content( string $block_content, array $parsed_block, Rendering_Context $rendering_context, bool $is_striped_table = false ): string {
$html = new \WP_HTML_Tag_Processor( $block_content );
$custom_border_color = $this->get_custom_border_color( $parsed_block, $rendering_context );
$custom_border_width = $this->get_custom_border_width( $parsed_block );
if ( $custom_border_color ) {
$border_color = $custom_border_color;
} else {
$email_styles = $rendering_context->get_theme_styles();
$border_color = Html_Processing_Helper::sanitize_color( $parsed_block['email_attrs']['color'] ?? $email_styles['color']['text'] ?? '#000000' );
}
$current_section = '';
$row_count = 0;
while ( $html->next_tag() ) {
$tag_name = $html->get_tag();
if ( 'TABLE' === $tag_name ) {
$html->set_attribute( 'border', '1' );
$html->set_attribute( 'cellpadding', '8' );
$html->set_attribute( 'cellspacing', '0' );
$html->set_attribute( 'role', 'presentation' );
$html->set_attribute( 'width', '100%' );
$existing_style = (string) ( $html->get_attribute( 'style' ) ?? '' );
$class_attr = (string) ( $html->get_attribute( 'class' ) ?? '' );
$table_layout = $this->has_fixed_layout( $class_attr ) ? 'table-layout: fixed; ' : '';
$email_table_styles = "{$table_layout}border-collapse: collapse; width: 100%;";
$existing_style = rtrim( $existing_style, "; \t\n\r\0\x0B" );
$new_style = $existing_style ? $existing_style . '; ' . $email_table_styles : $email_table_styles;
$html->set_attribute( 'style', $new_style );
$class_attr = Html_Processing_Helper::clean_css_classes( $class_attr );
$html->set_attribute( 'class', $class_attr );
} elseif ( 'THEAD' === $tag_name ) {
$current_section = 'thead';
$row_count = 0;
} elseif ( 'TBODY' === $tag_name ) {
$current_section = 'tbody';
$row_count = 0;
} elseif ( 'TFOOT' === $tag_name ) {
$current_section = 'tfoot';
$row_count = 0;
} elseif ( 'TR' === $tag_name ) {
++$row_count;
} elseif ( 'TD' === $tag_name || 'TH' === $tag_name ) {
$html->set_attribute( 'valign', 'top' );
$existing_style = (string) ( $html->get_attribute( 'style' ) ?? '' );
$existing_style = rtrim( $existing_style, "; \t\n\r\0\x0B" );
$border_width = $custom_border_width ? $custom_border_width : '1px';
$border_style = $this->get_custom_border_style( $parsed_block );
$cell_text_align = $this->get_cell_text_alignment( $html, $rendering_context );
$email_cell_styles = "vertical-align: top; border: {$border_width} {$border_style} {$border_color}; padding: 8px; text-align: {$cell_text_align};";
$email_cell_styles = $this->add_header_footer_borders( $html, $email_cell_styles, $border_color, $current_section, $custom_border_width );
if ( $is_striped_table && 'tbody' === $current_section && 1 === $row_count % 2 ) {
$email_cell_styles .= ' background-color: #f8f9fa;';
}
$new_cell_style = $existing_style ? $existing_style . '; ' . $email_cell_styles : $email_cell_styles;
$html->set_attribute( 'style', $new_cell_style );
}
}
return $html->get_updated_html();
}
private function get_custom_border_color( array $parsed_block, Rendering_Context $rendering_context ): ?string {
$block_attributes = $parsed_block['attrs'] ?? array();
if ( ! empty( $block_attributes['borderColor'] ) ) {
$border_color = $rendering_context->translate_slug_to_color( $block_attributes['borderColor'] );
return Html_Processing_Helper::sanitize_color( $border_color );
}
return null;
}
private function get_custom_border_width( array $parsed_block ): ?string {
$block_attributes = $parsed_block['attrs'] ?? array();
if ( ! empty( $block_attributes['style']['border']['width'] ) ) {
$border_width = $block_attributes['style']['border']['width'];
$border_width = Html_Processing_Helper::sanitize_css_value( $border_width );
if ( empty( $border_width ) ) {
return null;
}
if ( is_numeric( $border_width ) ) {
return $border_width . 'px';
}
if ( preg_match( '/^[0-9]+\.?[0-9]*(px|em|rem|pt|pc|in|cm|mm|ex|ch|vw|vh|vmin|vmax)$/', $border_width ) ) {
return $border_width;
}
return null;
}
return null;
}
private function get_custom_border_style( array $parsed_block ): string {
$style = strtolower( (string) ( $parsed_block['attrs']['style']['border']['style'] ?? '' ) );
$allowed = array( 'solid', 'dashed', 'dotted' );
return in_array( $style, $allowed, true ) ? $style : 'solid';
}
private function add_header_footer_borders( \WP_HTML_Tag_Processor $html, string $base_styles, string $border_color, string $current_section = '', ?string $custom_border_width = null ): string {
$tag_name = $html->get_tag();
if ( $custom_border_width ) {
return $base_styles;
}
if ( 'TH' === $tag_name ) {
$base_styles .= " border-bottom: 3px solid {$border_color};";
}
if ( 'TD' === $tag_name && 'tfoot' === $current_section ) {
$base_styles .= " border-top: 3px solid {$border_color};";
}
return $base_styles;
}
private function get_cell_text_alignment( \WP_HTML_Tag_Processor $html, Rendering_Context $rendering_context ): string {
$data_align = $html->get_attribute( 'data-align' );
if ( $data_align && in_array( $data_align, self::VALID_TEXT_ALIGNMENTS, true ) ) {
return $data_align;
}
$class_attr = (string) ( $html->get_attribute( 'class' ) ?? '' );
if ( false !== strpos( $class_attr, 'has-text-align-center' ) ) {
return 'center';
}
if ( false !== strpos( $class_attr, 'has-text-align-right' ) ) {
return 'right';
}
if ( false !== strpos( $class_attr, 'has-text-align-left' ) ) {
return 'left';
}
if ( 'TH' === $html->get_tag() ) {
return 'center';
}
return $rendering_context->get_default_text_align();
}
private function has_fixed_layout( string $class_attr ): bool {
return false !== strpos( $class_attr, 'has-fixed-layout' );
}
private function extract_table_and_caption_from_figure( string $block_content ): array {
$dom_helper = new Dom_Document_Helper( $block_content );
$figure_tag = $dom_helper->find_element( 'figure' );
if ( ! $figure_tag ) {
return array(
'table' => $block_content,
'caption' => '',
);
}
$figure_class_attr = $dom_helper->get_attribute_value( $figure_tag, 'class' );
$figure_class = (string) ( $figure_class_attr ? $figure_class_attr : '' );
if ( false === strpos( $figure_class, 'wp-block-table' ) ) {
return array(
'table' => $block_content,
'caption' => '',
);
}
$figure_html = $dom_helper->get_outer_html( $figure_tag );
if ( ! preg_match( '/<table[^>]*>.*?<\/table>/is', $figure_html, $table_matches ) ) {
return array(
'table' => $block_content,
'caption' => '',
);
}
$table_html = $table_matches[0];
$caption = '';
if ( preg_match( '/<figcaption[^>]*>(.*?)<\/figcaption>/is', $figure_html, $figcaption_matches ) ) {
$caption = $figcaption_matches[1];
}
return array(
'table' => $table_html,
'caption' => $caption,
);
}
private function apply_styles_to_table_element( string $table_content, string $styles ): string {
$html = new \WP_HTML_Tag_Processor( $table_content );
if ( $html->next_tag( array( 'tag_name' => 'TABLE' ) ) ) {
$existing_style = (string) ( $html->get_attribute( 'style' ) ?? '' );
$existing_style = rtrim( $existing_style, "; \t\n\r\0\x0B" );
$border_width_styles = $this->get_default_border_widths( $existing_style );
$new_style = $existing_style;
if ( ! empty( $border_width_styles ) ) {
$new_style = $new_style ? $new_style . '; ' . $border_width_styles : $border_width_styles;
}
if ( ! empty( $styles ) ) {
$new_style = $new_style ? $new_style . '; ' . $styles : $styles;
}
$html->set_attribute( 'style', $new_style );
return $html->get_updated_html();
}
return $table_content;
}
private function get_default_border_widths( string $existing_style ): string {
$sides = array( 'top', 'right', 'bottom', 'left' );
$border_width_styles = array();
foreach ( $sides as $side ) {
$has_color = strpos( $existing_style, "border-{$side}-color:" ) !== false;
$has_width = strpos( $existing_style, "border-{$side}-width:" ) !== false;
if ( $has_color && ! $has_width ) {
$border_width_styles[] = "border-{$side}-width: 1.5px";
}
}
return implode( '; ', $border_width_styles );
}
private function add_class_to_table_element( string $table_content, string $class_name ): string {
if ( ! preg_match( '/^[a-zA-Z0-9\-_]+$/', $class_name ) ) {
return $table_content;
}
$html = new \WP_HTML_Tag_Processor( $table_content );
if ( $html->next_tag( array( 'tag_name' => 'TABLE' ) ) ) {
$existing_class = (string) ( $html->get_attribute( 'class' ) ?? '' );
$existing_class = trim( $existing_class );
if ( false === strpos( $existing_class, $class_name ) ) {
$new_class = $existing_class ? $existing_class . ' ' . $class_name : $class_name;
$html->set_attribute( 'class', $new_class );
}
return $html->get_updated_html();
}
return $table_content;
}
private function extract_typography_styles_for_caption( string $css ): string {
$typography_properties = Html_Processing_Helper::get_caption_css_properties();
$caption_styles = array();
foreach ( $typography_properties as $property ) {
if ( preg_match( '/' . preg_quote( $property, '/' ) . '\s*:\s*([^;]+)/i', $css, $matches ) ) {
$value = trim( $matches[1] );
$sanitized_value = Html_Processing_Helper::sanitize_css_value( $value );
if ( ! empty( $sanitized_value ) ) {
$caption_styles[] = $property . ': ' . $sanitized_value;
}
}
}
return implode( '; ', $caption_styles );
}
private function is_striped_table( string $block_content, array $parsed_block ): bool {
if ( isset( $parsed_block['attrs']['className'] ) && false !== strpos( $parsed_block['attrs']['className'], 'is-style-stripes' ) ) {
return true;
}
if ( false !== strpos( $block_content, 'is-style-stripes' ) ) {
return true;
}
return false;
}
private function is_valid_table_content( string $content ): bool {
return (bool) preg_match( '/<table[^>]*>.*?<\/table>/is', $content );
}
}
