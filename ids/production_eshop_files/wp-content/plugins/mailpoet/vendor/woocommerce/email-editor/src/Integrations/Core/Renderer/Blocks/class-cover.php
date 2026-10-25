<?php
declare( strict_types = 1 );
namespace Automattic\WooCommerce\EmailEditor\Integrations\Core\Renderer\Blocks;
if (!defined('ABSPATH')) exit;
use Automattic\WooCommerce\EmailEditor\Engine\Renderer\ContentRenderer\Rendering_Context;
use Automattic\WooCommerce\EmailEditor\Integrations\Utils\Table_Wrapper_Helper;
use Automattic\WooCommerce\EmailEditor\Integrations\Utils\Styles_Helper;
use Automattic\WooCommerce\EmailEditor\Integrations\Utils\Dom_Document_Helper;
use Automattic\WooCommerce\EmailEditor\Integrations\Utils\Html_Processing_Helper;
class Cover extends Abstract_Block_Renderer {
protected function render_content( string $block_content, array $parsed_block, Rendering_Context $rendering_context ): string {
$block_attrs = $parsed_block['attrs'] ?? array();
$inner_blocks = $parsed_block['innerBlocks'] ?? array();
$inner_content = '';
foreach ( $inner_blocks as $block ) {
$inner_content .= render_block( $block );
}
if ( empty( $inner_content ) ) {
return '';
}
$background_image = $this->extract_background_image( $block_attrs, $parsed_block['innerHTML'] ?? $block_content );
return $this->build_email_layout( $inner_content, $block_attrs, $block_content, $background_image, $rendering_context );
}
private function build_email_layout( string $inner_content, array $block_attrs, string $block_content, string $background_image, Rendering_Context $rendering_context ): string {
$original_wrapper_classname = ( new Dom_Document_Helper( $block_content ) )->get_attribute_value_by_tag_name( 'div', 'class' ) ?? '';
$background_color = $this->get_background_color( $block_attrs, $rendering_context );
$block_styles = Styles_Helper::get_block_styles( $block_attrs, $rendering_context, array( 'padding', 'border', 'background-color' ) );
$default_styles = array(
'width' => '100%',
'border-collapse' => 'collapse',
'text-align' => 'center',
);
$min_height = $this->get_minimum_height( $block_attrs );
$default_styles['min-height'] = ! empty( $min_height ) ? $min_height : '430px';
$block_styles = Styles_Helper::extend_block_styles(
$block_styles,
$default_styles
);
if ( ! empty( $background_image ) ) {
$block_styles = Styles_Helper::extend_block_styles(
$block_styles,
array(
'background-image' => 'url("' . esc_url_raw( $background_image ) . '")',
'background-size' => 'cover',
'background-position' => 'center',
'background-repeat' => 'no-repeat',
)
);
} elseif ( ! empty( $background_color ) ) {
$block_styles = Styles_Helper::extend_block_styles(
$block_styles,
array(
'background-color' => $background_color,
)
);
}
$table_attrs = array(
'class' => 'email-block-cover ' . esc_attr( $original_wrapper_classname ),
'style' => $block_styles['css'],
'align' => 'center',
'width' => '100%',
);
$cover_content = $this->build_cover_content( $inner_content );
$cell_attrs = array(
'valign' => 'middle',
'align' => 'center',
);
$cell = Table_Wrapper_Helper::render_table_cell( $cover_content, $cell_attrs );
return Table_Wrapper_Helper::render_table_wrapper( $cell, $table_attrs, array(), array(), false );
}
private function extract_background_image( array $block_attrs, string $block_content ): string {
if ( ! empty( $block_attrs['url'] ) ) {
return esc_url_raw( $block_attrs['url'] );
}
$html = new \WP_HTML_Tag_Processor( $block_content );
while ( $html->next_tag( array( 'tag_name' => 'img' ) ) ) {
$class_attr = $html->get_attribute( 'class' );
if ( is_string( $class_attr ) && false !== strpos( $class_attr, 'wp-block-cover__image-background' ) ) {
$src = $html->get_attribute( 'src' );
if ( is_string( $src ) ) {
return esc_url_raw( $src );
}
}
}
return '';
}
private function get_minimum_height( array $block_attrs ): string {
if ( ! empty( $block_attrs['minHeight'] ) ) {
return Html_Processing_Helper::sanitize_dimension_value( $block_attrs['minHeight'] );
}
if ( ! empty( $block_attrs['style']['dimensions']['minHeight'] ) ) {
return Html_Processing_Helper::sanitize_dimension_value( $block_attrs['style']['dimensions']['minHeight'] );
}
return '';
}
private function get_background_color( array $block_attrs, Rendering_Context $rendering_context ): string {
if ( ! empty( $block_attrs['customOverlayColor'] ) ) {
$color = $block_attrs['customOverlayColor'];
$sanitized_color = $this->validate_and_sanitize_color( $color );
if ( ! empty( $sanitized_color ) ) {
return $sanitized_color;
}
}
if ( ! empty( $block_attrs['overlayColor'] ) ) {
$translated_color = $rendering_context->translate_slug_to_color( $block_attrs['overlayColor'] );
$sanitized_color = $this->validate_and_sanitize_color( $translated_color );
if ( ! empty( $sanitized_color ) ) {
return $sanitized_color;
}
}
return '';
}
private function validate_and_sanitize_color( string $color ): string {
$sanitized_color = Html_Processing_Helper::sanitize_color( $color );
if ( '#000000' === $sanitized_color && '#000000' !== $color ) {
return '';
}
return $sanitized_color;
}
private function build_cover_content( string $inner_content ): string {
$cover_style = 'position: relative; display: inline-block; width: 100%; max-width: 100%;';
$inner_wrapper_style = 'padding: 20px;';
$inner_wrapper_html = sprintf(
'<div class="wp-block-cover__inner-container" style="%s">%s</div>',
$inner_wrapper_style,
$inner_content
);
return sprintf(
'<div class="wp-block-cover" style="%s">%s</div>',
$cover_style,
$inner_wrapper_html
);
}
}
