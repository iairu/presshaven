<?php
declare( strict_types = 1 );
namespace Automattic\WooCommerce\EmailEditor\Integrations\Core\Renderer\Blocks;
if (!defined('ABSPATH')) exit;
use Automattic\WooCommerce\EmailEditor\Engine\Renderer\ContentRenderer\Rendering_Context;
use Automattic\WooCommerce\EmailEditor\Integrations\Utils\Table_Wrapper_Helper;
use Automattic\WooCommerce\EmailEditor\Integrations\Utils\Styles_Helper;
use Automattic\WooCommerce\EmailEditor\Integrations\Utils\Dom_Document_Helper;
use Automattic\WooCommerce\EmailEditor\Integrations\Utils\Html_Processing_Helper;
class Gallery extends Abstract_Block_Renderer {
protected function render_content( string $block_content, array $parsed_block, Rendering_Context $rendering_context ): string {
$columns = $this->get_columns_from_attributes( $parsed_block['attrs'] ?? array() );
$layout_width = (int) Styles_Helper::parse_value( $rendering_context->get_layout_width_without_padding() );
$gallery_images = $this->extract_images_from_gallery_content( $block_content, $parsed_block, $columns, $layout_width );
if ( empty( $gallery_images ) ) {
return '';
}
return $this->build_email_layout( $gallery_images, $parsed_block, $block_content, $rendering_context );
}
private function get_cell_width( int $index, int $image_count, int $columns, int $layout_width ): int {
$columns = max( 1, $columns );
$row_start = intdiv( $index, $columns ) * $columns;
$images_in_row = max( 1, min( $columns, $image_count - $row_start ) );
return (int) max( 1, floor( $layout_width / $images_in_row ) );
}
private function extract_images_from_gallery_content( string $block_content, array $parsed_block, int $columns, int $layout_width ): array {
$gallery_images = array();
$inner_blocks = $parsed_block['innerBlocks'] ?? array();
$gallery_attrs = isset( $parsed_block['attrs'] ) && is_array( $parsed_block['attrs'] ) ? $parsed_block['attrs'] : array();
$gallery_aspect_ratio = isset( $gallery_attrs['aspectRatio'] ) && is_string( $gallery_attrs['aspectRatio'] ) ? $gallery_attrs['aspectRatio'] : null;
$image_blocks = array();
foreach ( $inner_blocks as $block ) {
if ( 'core/image' === $block['blockName'] && isset( $block['innerHTML'] ) ) {
$image_blocks[] = $block;
}
}
$image_count = count( $image_blocks );
foreach ( $image_blocks as $index => $block ) {
$image_attrs = isset( $block['attrs'] ) && is_array( $block['attrs'] ) ? $block['attrs'] : array();
$image_ratio = isset( $image_attrs['aspectRatio'] ) && is_string( $image_attrs['aspectRatio'] ) ? $image_attrs['aspectRatio'] : null;
$aspect_ratio = ( null !== $image_ratio && null !== $this->parse_aspect_ratio( $image_ratio ) ) ? $image_ratio : $gallery_aspect_ratio;
$cell_width = $this->get_cell_width( $index, $image_count, $columns, $layout_width );
$extracted_image = $this->extract_image_from_html( $block['innerHTML'], $aspect_ratio, $cell_width, $image_attrs );
if ( ! empty( $extracted_image ) ) {
$gallery_images[] = $extracted_image;
}
}
return $gallery_images;
}
private function extract_image_from_html( string $html_content, ?string $aspect_ratio = null, int $cell_width = 0, array $image_attrs = array() ): string {
$result = '';
if ( preg_match( '/<a[^>]*href=(["\'])(.*?)\1[^>]*>(\s*<img[^>]*>)\s*<\/a>/s', $html_content, $link_matches ) ) {
$sanitized_url = esc_url( $link_matches[2] );
$sanitized_img = $this->prepare_image_html( $link_matches[3], $aspect_ratio, $cell_width, $image_attrs );
if ( '' !== $sanitized_img ) {
if ( ! empty( $sanitized_url ) ) {
$result .= '<a href="' . $sanitized_url . '">' . $sanitized_img . '</a>';
} else {
$result .= $sanitized_img;
}
}
} elseif ( preg_match( '/<img[^>]*>/', $html_content, $img_matches ) ) {
$sanitized_img = $this->prepare_image_html( $img_matches[0], $aspect_ratio, $cell_width, $image_attrs );
if ( '' !== $sanitized_img ) {
$result .= $sanitized_img;
}
}
if ( preg_match( '/(<figcaption[^>]*>)(.*?)(<\/figcaption>)/s', $html_content, $caption_matches ) ) {
if ( Html_Processing_Helper::validate_container_attributes( $caption_matches[1] . $caption_matches[3] ) ) {
$sanitized_caption = Html_Processing_Helper::sanitize_caption_html( $caption_matches[2] );
$result .= '<br><div class="wp-element-caption" style="font-size: 13px; line-height: 1.0;">' . $sanitized_caption . '</div>';
}
} elseif ( preg_match( '/(<span class="wp-element-caption"[^>]*>)(.*?)(<\/span>)/s', $html_content, $caption_matches ) ) {
if ( Html_Processing_Helper::validate_container_attributes( $caption_matches[1] . $caption_matches[3] ) ) {
$sanitized_caption = Html_Processing_Helper::sanitize_caption_html( $caption_matches[2] );
$result .= '<br><div class="wp-element-caption" style="font-size: 13px; line-height: 1.0;">' . $sanitized_caption . '</div>';
}
}
return $result;
}
private function prepare_image_html( string $raw_img_html, ?string $aspect_ratio, int $cell_width, array $image_attrs ): string {
$sanitized = Html_Processing_Helper::sanitize_image_html( $raw_img_html );
$sanitized = $this->apply_aspect_ratio_crop( $sanitized, $aspect_ratio, $cell_width, $image_attrs );
return $this->normalize_image_for_email( $sanitized, $cell_width );
}
private function normalize_image_for_email( string $img_html, int $cell_width ): string {
if ( '' === $img_html ) {
return $img_html;
}
$html = new \WP_HTML_Tag_Processor( $img_html );
if ( ! $html->next_tag( array( 'tag_name' => 'img' ) ) ) {
return $img_html;
}
$html->remove_attribute( 'class' );
if ( $cell_width > 0 ) {
$raw_width = $html->get_attribute( 'width' );
$width = is_string( $raw_width ) && is_numeric( $raw_width ) ? (int) $raw_width : 0;
if ( $width > $cell_width ) {
$raw_height = $html->get_attribute( 'height' );
$height = is_string( $raw_height ) && is_numeric( $raw_height ) ? (int) $raw_height : 0;
if ( $height > 0 ) {
$scaled_height = max( 1, (int) round( $height * ( $cell_width / $width ) ) );
$html->set_attribute( 'height', esc_attr( (string) $scaled_height ) );
}
$html->set_attribute( 'width', esc_attr( (string) $cell_width ) );
}
}
return $html->get_updated_html();
}
private function apply_aspect_ratio_crop( string $img_html, ?string $aspect_ratio, int $cell_width = 0, array $image_attrs = array() ): string {
if ( null === $aspect_ratio || '' === $img_html ) {
return $img_html;
}
$aspect_ratio = trim( $aspect_ratio );
$ratio_value = $this->parse_aspect_ratio( $aspect_ratio );
if ( null === $ratio_value ) {
return $img_html;
}
$html = new \WP_HTML_Tag_Processor( $img_html );
if ( ! $html->next_tag( array( 'tag_name' => 'img' ) ) ) {
return $img_html;
}
$width = $cell_width > 0 ? $cell_width : 0;
$height = $width > 0 ? max( 1, (int) round( $width / $ratio_value ) ) : 0;
$src_attribute = $html->get_attribute( 'src' );
$image_url = is_string( $src_attribute ) ? $src_attribute : '';
$filtered_url = apply_filters( 'woocommerce_email_editor_gallery_cropped_image_url', $image_url, $aspect_ratio, $width, $height, $image_attrs );
$is_server_cropped = is_string( $filtered_url ) && '' !== $image_url && '' !== $filtered_url && $filtered_url !== $image_url;
$cropped_url = $is_server_cropped ? esc_url( (string) $filtered_url ) : '';
if ( '' !== $cropped_url ) {
$html->set_attribute( 'src', $cropped_url );
if ( $width > 0 && $height > 0 ) {
$html->set_attribute( 'width', esc_attr( (string) $width ) );
$html->set_attribute( 'height', esc_attr( (string) $height ) );
}
$crop_styles = sprintf( 'aspect-ratio: %s; object-fit: cover; width: 100%%; height: auto; max-width: 100%%; display: block;', $aspect_ratio );
} else {
$crop_styles = sprintf( 'aspect-ratio: %s; object-fit: cover; width: 100%%; height: auto; display: block;', $aspect_ratio );
}
$existing_style = $html->get_attribute( 'style' ) ?? '';
$existing_style = '' !== $existing_style ? ( rtrim( $existing_style, ';' ) . '; ' ) : '';
$html->set_attribute( 'style', esc_attr( $existing_style . $crop_styles ) );
return $html->get_updated_html();
}
private function parse_aspect_ratio( string $aspect_ratio ): ?float {
if ( ! preg_match( '/^(\d+(?:\.\d+)?)(?:\s*\/\s*(\d+(?:\.\d+)?))?$/', trim( $aspect_ratio ), $matches ) ) {
return null;
}
$numerator = (float) $matches[1];
$denominator = isset( $matches[2] ) ? (float) $matches[2] : 1.0;
if ( $numerator <= 0 || $denominator <= 0 ) {
return null;
}
return $numerator / $denominator;
}
private function extract_gallery_caption( string $block_content ): string {
if ( preg_match( '/(<figcaption class="blocks-gallery-caption[^"]*"[^>]*>)(.*?)(<\/figcaption>)/s', $block_content, $matches ) ) {
if ( Html_Processing_Helper::validate_container_attributes( $matches[1] . $matches[3] ) ) {
return Html_Processing_Helper::sanitize_caption_html( trim( $matches[2] ) );
}
}
return '';
}
private function build_email_layout( array $gallery_images, array $parsed_block, string $block_content, Rendering_Context $rendering_context ): string {
$original_wrapper_classname = ( new Dom_Document_Helper( $block_content ) )->get_attribute_value_by_tag_name( 'figure', 'class' ) ?? '';
$block_attrs = $parsed_block['attrs'] ?? array();
$columns = $this->get_columns_from_attributes( $block_attrs );
$gallery_caption = $this->extract_gallery_caption( $block_content );
$block_styles = Styles_Helper::get_block_styles( $block_attrs, $rendering_context, array( 'padding', 'border', 'background', 'background-color', 'color' ) );
$block_styles = Styles_Helper::extend_block_styles(
$block_styles,
array(
'width' => '100%',
'border-collapse' => 'collapse',
'text-align' => $rendering_context->get_default_text_align(),
)
);
$table_attrs = array(
'class' => 'email-block-gallery ' . Html_Processing_Helper::clean_css_classes( $original_wrapper_classname ),
'style' => $block_styles['css'],
'width' => '100%',
);
$cell_attrs = array();
if ( isset( $parsed_block['email_attrs']['width'] ) ) {
$cell_attrs['width'] = $parsed_block['email_attrs']['width'];
}
$gallery_content = $this->build_gallery_table( $gallery_images, $columns );
if ( ! empty( $gallery_caption ) ) {
$gallery_content .= '<br><div class="blocks-gallery-caption wp-element-caption" style="font-size: 13px; line-height: 1.0; text-align: center;">' . $gallery_caption . '</div>';
}
return Table_Wrapper_Helper::render_table_wrapper( $gallery_content, $table_attrs, $cell_attrs );
}
private function build_gallery_table( array $gallery_images, int $columns ): string {
$content_parts = array();
$image_count = count( $gallery_images );
$cell_padding = 8;
for ( $i = 0; $i < $image_count; $i += $columns ) {
$row_images = array_slice( $gallery_images, $i, $columns );
$content_parts[] = $this->build_gallery_row_table( $row_images, $columns, $cell_padding );
}
return implode( '', $content_parts );
}
private function build_gallery_row_table( array $row_images, int $total_columns, int $cell_padding ): string {
$images_in_row = count( $row_images );
$row_cells = '';
if ( 1 === $images_in_row ) {
$cell_attrs = array(
'style' => sprintf( 'width: %s; padding: %dpx; vertical-align: top; text-align: center;', Html_Processing_Helper::sanitize_css_value( '100%' ), $cell_padding ),
'valign' => 'top',
'colspan' => $total_columns,
);
$row_cells .= Table_Wrapper_Helper::render_table_cell( $row_images[0], $cell_attrs );
} else {
$cell_width_percent = 100 / $images_in_row;
foreach ( $row_images as $image_html ) {
$cell_attrs = array(
'style' => sprintf(
'width: %s; padding: %dpx; vertical-align: top; text-align: center;',
Html_Processing_Helper::sanitize_css_value( sprintf( '%.2f%%', $cell_width_percent ) ),
$cell_padding
),
'valign' => 'top',
);
$row_cells .= Table_Wrapper_Helper::render_table_cell( $image_html, $cell_attrs );
}
}
return sprintf(
'<table role="presentation" style="width: %s; border-collapse: collapse; table-layout: fixed;"><tr>%s</tr></table>',
Html_Processing_Helper::sanitize_css_value( '100%' ),
$row_cells
);
}
private function get_columns_from_attributes( array $block_attrs ): int {
$columns = $block_attrs['columns'] ?? 3;
$columns = max( 1, min( 8, (int) $columns ) );
return $columns;
}
}
