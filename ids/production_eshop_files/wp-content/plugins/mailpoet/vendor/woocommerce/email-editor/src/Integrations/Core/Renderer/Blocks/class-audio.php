<?php
declare( strict_types = 1 );
namespace Automattic\WooCommerce\EmailEditor\Integrations\Core\Renderer\Blocks;
if (!defined('ABSPATH')) exit;
use Automattic\WooCommerce\EmailEditor\Engine\Renderer\ContentRenderer\Rendering_Context;
use Automattic\WooCommerce\EmailEditor\Integrations\Utils\Table_Wrapper_Helper;
class Audio extends Abstract_Block_Renderer {
public function render( string $block_content, array $parsed_block, Rendering_Context $rendering_context ): string {
if ( ! isset( $parsed_block['attrs'] ) || ! is_array( $parsed_block['attrs'] ) ||
! class_exists( '\Automattic\WooCommerce\EmailEditor\Integrations\Utils\Table_Wrapper_Helper' ) ) {
return '';
}
$attr = $parsed_block['attrs'];
$has_attachment_id = ! empty( $attr['id'] );
$has_src_in_html = preg_match( '#<audio[^>]*\ssrc=["\']([^"\']*)["\'][^>]*/?>#', $block_content );
if ( ! $has_attachment_id && ! $has_src_in_html ) {
return '';
}
$rendered_content = $this->render_content( $block_content, $parsed_block, $rendering_context );
if ( empty( $rendered_content ) ) {
return '';
}
return $this->add_spacer_with_context( $rendered_content, $parsed_block['email_attrs'] ?? array(), $rendering_context );
}
protected function render_content( string $block_content, array $parsed_block, Rendering_Context $rendering_context ): string {
$attr = $parsed_block['attrs'];
if ( isset( $attr['id'] ) ) {
$url = \wp_get_attachment_url( $attr['id'] );
$meta = \get_post_meta( $attr['id'], '_wp_attachment_metadata', true );
$length = ( is_array( $meta ) && isset( $meta['length_formatted'] ) && is_string( $meta['length_formatted'] ) ) ? $meta['length_formatted'] : '';
} else {
preg_match( '#<audio[^>]*\ssrc=["\']([^"\']*)["\'][^>]*/?>#', $block_content, $audio );
$url = isset( $audio[1] ) ? $audio[1] : $attr['src'] ?? '';
$length = null;
}
if ( empty( $url ) ) {
return '';
}
if ( ! str_starts_with( $url, 'data:audio/' ) &&
! str_starts_with( $url, '/' ) &&
! str_starts_with( $url, 'https://' ) ) {
return '';
}
if ( str_starts_with( $url, 'https://' ) && ! wp_http_validate_url( $url ) ) {
return '';
}
$email_attrs = $parsed_block['email_attrs'] ?? array();
$table_margin_style = '';
if ( ! empty( $email_attrs ) && class_exists( '\WP_Style_Engine' ) ) {
$table_margin_style = \WP_Style_Engine::compile_css( array_intersect_key( $email_attrs, array_flip( array( 'margin' ) ) ), '' );
}
$icon_image = $this->get_audio_icon_url();
$label = ! empty( $attr['label'] ) ? $attr['label'] : __( 'Listen to the audio', 'woocommerce' );
if ( ! empty( $length ) ) {
$label .= ' (' . esc_html( (string) $length ) . ')';
}
$audio_url = esc_url( $url );
$background_color = '#f6f7f7';
$border_color = '#AAA';
$icon_size = '18px';
$font_size = '14px';
$start_side = $rendering_context->get_start_side();
$end_side = $rendering_context->get_end_side();
$icon_content = sprintf(
'<a href="%1$s" rel="noopener nofollow" target="_blank" style="padding: 0.25em; padding-%5$s: 17px; display: inline-block; vertical-align: middle;"><img height="%2$s" src="%3$s" style="display:block;margin-%6$s:0;vertical-align:middle;" width="%2$s" alt="%4$s"></a>',
$audio_url,
esc_attr( $icon_size ),
esc_url( $icon_image ),
sprintf( __( '%s icon', 'woocommerce' ), __( 'Audio', 'woocommerce' ) ),
esc_attr( $start_side ),
esc_attr( $end_side )
);
$icon_content = Table_Wrapper_Helper::render_table_cell( $icon_content, array( 'style' => sprintf( 'vertical-align:middle;font-size:%s;', $font_size ) ) );
$label_content = sprintf(
'<a href="%1$s" rel="noopener nofollow" target="_blank" style="text-decoration:none; padding: 0.25em; padding-%3$s: 17px; display: inline-block;"><span style="margin-left:.5em;margin-right:.5em;font-weight:bold"> %2$s </span></a>',
$audio_url,
esc_html( $label ),
esc_attr( $end_side )
);
$label_cell_style = sprintf(
'vertical-align:middle;font-size:%s;',
$font_size
);
$label_content = Table_Wrapper_Helper::render_table_cell( $label_content, array( 'style' => $label_cell_style ) );
$audio_content = $icon_content . $label_content;
$main_table_styles = sprintf(
'background-color: %s; border-radius: 9999px; float: none; border: 1px solid %s; border-collapse: separate;',
$background_color,
$border_color
);
$main_table_attrs = array(
'align' => $rendering_context->get_default_text_align(),
'style' => $main_table_styles,
);
$main_table = Table_Wrapper_Helper::render_table_wrapper( $audio_content, $main_table_attrs, array(), array(), false );
$table_style = 'width: 100%;';
if ( ! empty( $table_margin_style ) ) {
$table_style = $table_margin_style . '; ' . $table_style;
} else {
$table_style = 'margin: 16px 0; ' . $table_style;
}
$table_attrs = array(
'style' => $table_style,
);
$cell_attrs = array(
'style' => 'min-width: 100%; vertical-align: middle; word-break: break-word; text-align: ' . $rendering_context->get_default_text_align() . ';',
);
$main_wrapper = Table_Wrapper_Helper::render_table_wrapper( $main_table, $table_attrs, $cell_attrs );
return Table_Wrapper_Helper::render_outlook_table_wrapper( $main_wrapper, array( 'align' => $rendering_context->get_default_text_align() ) );
}
private function get_audio_icon_url(): string {
$file_name = '/icons/audio/audio-play.png';
return plugins_url( $file_name, __FILE__ );
}
}
