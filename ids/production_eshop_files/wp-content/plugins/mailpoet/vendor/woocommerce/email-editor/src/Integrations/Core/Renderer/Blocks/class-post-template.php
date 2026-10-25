<?php
declare( strict_types = 1 );
namespace Automattic\WooCommerce\EmailEditor\Integrations\Core\Renderer\Blocks;
if (!defined('ABSPATH')) exit;
use Automattic\WooCommerce\EmailEditor\Engine\Renderer\ContentRenderer\Rendering_Context;
use Automattic\WooCommerce\EmailEditor\Integrations\Utils\Dom_Document_Helper;
use Automattic\WooCommerce\EmailEditor\Integrations\Utils\Html_Processing_Helper;
use Automattic\WooCommerce\EmailEditor\Integrations\Utils\Styles_Helper;
use Automattic\WooCommerce\EmailEditor\Integrations\Utils\Table_Wrapper_Helper;
class Post_Template extends Abstract_Block_Renderer {
private const MAX_COLUMNS = 16;
private const CELL_PADDING = 8;
private const IMAGE_STYLE = 'border: 0; line-height: 100%; width: 100%; max-width: 100%; height: auto; display: block;';
protected function render_content( string $block_content, array $parsed_block, Rendering_Context $rendering_context ): string {
if ( '' === trim( $block_content ) ) {
return $block_content;
}
$dom = new Dom_Document_Helper( $block_content );
$list_element = $this->find_post_template_list( $dom );
if ( null === $list_element ) {
return $block_content;
}
$items = $this->extract_list_items( $dom, $list_element );
if ( empty( $items ) ) {
return $block_content;
}
$columns = $this->get_column_count( $parsed_block, $dom, $list_element );
if ( $columns < 2 ) {
return $block_content;
}
$layout_width = (int) Styles_Helper::parse_value( $rendering_context->get_layout_width_without_padding() );
return $this->build_grid_table( $items, $columns, $dom, $list_element, $layout_width );
}
private function find_post_template_list( Dom_Document_Helper $dom ): ?\DOMElement {
foreach ( $dom->find_elements( 'ul' ) as $list_element ) {
$classes = preg_split( '/\s+/', trim( $dom->get_attribute_value( $list_element, 'class' ) ) );
if ( is_array( $classes ) && in_array( 'wp-block-post-template', $classes, true ) ) {
return $list_element;
}
}
return null;
}
private function extract_list_items( Dom_Document_Helper $dom, \DOMElement $list_element ): array {
$items = array();
foreach ( $list_element->childNodes as $node ) {
if ( $node instanceof \DOMElement && 'li' === $node->tagName ) {
$items[] = $dom->get_element_inner_html( $node );
}
}
return $items;
}
private function get_column_count( array $parsed_block, Dom_Document_Helper $dom, \DOMElement $list_element ): int {
$layout = $parsed_block['attrs']['layout'] ?? array();
$type = is_array( $layout ) && isset( $layout['type'] ) && is_string( $layout['type'] ) ? $layout['type'] : '';
if ( '' !== $type && 'grid' !== $type && 'flex' !== $type ) {
return 1;
}
$columns = 0;
if ( is_array( $layout ) && isset( $layout['columnCount'] ) && is_numeric( $layout['columnCount'] ) ) {
$columns = (int) $layout['columnCount'];
}
if ( $columns < 1 && preg_match( '/(?:^|\s)columns-(\d+)(?:\s|$)/', $dom->get_attribute_value( $list_element, 'class' ), $matches ) ) {
$columns = (int) $matches[1];
}
if ( $columns < 1 ) {
return 1;
}
return min( self::MAX_COLUMNS, $columns );
}
private function build_grid_table( array $items, int $columns, Dom_Document_Helper $dom, \DOMElement $list_element, int $layout_width ): string {
$cell_width = $this->get_cell_width( $layout_width, $columns );
$rows = array();
$item_count = count( $items );
for ( $i = 0; $i < $item_count; $i += $columns ) {
$rows[] = $this->build_grid_row( array_slice( $items, $i, $columns ), $columns, $cell_width );
}
$grid_content = implode( '', $rows );
$original_class = $dom->get_attribute_value( $list_element, 'class' );
$table_attrs = array(
'class' => trim( 'email-block-post-template ' . Html_Processing_Helper::clean_css_classes( $original_class ) ),
'style' => 'width: 100%; border-collapse: collapse;',
'width' => '100%',
);
return Table_Wrapper_Helper::render_table_wrapper( $grid_content, $table_attrs );
}
private function get_cell_width( int $layout_width, int $columns ): int {
$cell_width = (int) floor( $layout_width / $columns ) - ( 2 * self::CELL_PADDING );
return max( 1, $cell_width );
}
private function build_grid_row( array $row_items, int $columns, int $cell_width ): string {
$cell_width_percent = 100 / $columns;
$cells = '';
for ( $col = 0; $col < $columns; $col++ ) {
$cell_content = isset( $row_items[ $col ] ) ? $this->prepare_item_content( $row_items[ $col ], $cell_width ) : '';
$cell_attrs = array(
'style' => sprintf(
'width: %s; padding: %dpx; vertical-align: top; text-align: center;',
Html_Processing_Helper::sanitize_css_value( sprintf( '%.4f%%', $cell_width_percent ) ),
self::CELL_PADDING
),
'valign' => 'top',
);
$cells .= Table_Wrapper_Helper::render_table_cell( $cell_content, $cell_attrs );
}
return sprintf(
'<table role="presentation" style="width: %s; border-collapse: collapse; table-layout: fixed;"><tr>%s</tr></table>',
Html_Processing_Helper::sanitize_css_value( '100%' ),
$cells
);
}
private function prepare_item_content( string $item_html, int $cell_width ): string {
if ( false === stripos( $item_html, '<img' ) ) {
return $item_html;
}
$item_dom = new Dom_Document_Helper( $item_html );
$images = array();
$remove_targets = array();
foreach ( $item_dom->find_elements( 'img' ) as $img_element ) {
$remove_targets[] = $this->find_image_removal_target( $img_element );
$normalized_img = $this->normalize_image_for_email( $item_dom->get_outer_html( $img_element ), $cell_width );
if ( '' === $normalized_img ) {
continue;
}
$href = $this->find_link_href( $img_element );
if ( '' !== $href ) {
$images[] = '<a href="' . esc_url( $href ) . '">' . $normalized_img . '</a>';
} else {
$images[] = $normalized_img;
}
}
if ( empty( $remove_targets ) ) {
return $item_html;
}
foreach ( $remove_targets as $target ) {
$item_dom->remove_element( $target );
}
return implode( '', $images ) . $this->extract_remaining_content( $item_dom );
}
private function find_image_removal_target( \DOMElement $img_element ): \DOMElement {
$target = $img_element;
$parent = $img_element->parentNode;
while ( $parent instanceof \DOMElement ) {
if ( '' !== trim( $parent->textContent ) || 1 !== $this->count_media_descendants( $parent ) ) {
break;
}
$target = $parent;
$parent = $parent->parentNode;
}
return $target;
}
private function count_media_descendants( \DOMElement $element ): int {
$count = $element->getElementsByTagName( 'img' )->length;
foreach ( array( 'video', 'audio', 'iframe', 'svg' ) as $tag_name ) {
$count += $element->getElementsByTagName( $tag_name )->length;
}
return $count;
}
private function extract_remaining_content( Dom_Document_Helper $item_dom ): string {
$this->strip_unsafe_markup( $item_dom );
$remainder = $item_dom->get_root_html();
if ( '' === trim( str_replace( "\xc2\xa0", '', wp_strip_all_tags( $remainder ) ) )
&& ! preg_match( '/<(img|video|audio|iframe|svg)\b/i', $remainder ) ) {
return '';
}
return $remainder;
}
private function strip_unsafe_markup( Dom_Document_Helper $item_dom ): void {
foreach ( array( 'script', 'style' ) as $tag_name ) {
foreach ( $item_dom->find_elements( $tag_name ) as $element ) {
$item_dom->remove_element( $element );
}
}
foreach ( $item_dom->find_elements( '*' ) as $element ) {
$attributes = $element->attributes;
if ( null === $attributes ) {
continue;
}
$handler_attributes = array();
foreach ( $attributes as $attribute ) {
if ( 0 === stripos( $attribute->name, 'on' ) ) {
$handler_attributes[] = $attribute->name;
}
}
foreach ( $handler_attributes as $attribute_name ) {
$element->removeAttribute( $attribute_name );
}
}
}
private function find_link_href( \DOMElement $img_element ): string {
$parent = $img_element->parentNode;
while ( $parent instanceof \DOMElement ) {
if ( 'a' === $parent->tagName ) {
return $parent->getAttribute( 'href' );
}
$parent = $parent->parentNode;
}
return '';
}
private function normalize_image_for_email( string $img_html, int $cell_width ): string {
if ( '' === $img_html ) {
return '';
}
$sanitized = Html_Processing_Helper::sanitize_image_html( $img_html );
$html = new \WP_HTML_Tag_Processor( $sanitized );
if ( ! $html->next_tag( array( 'tag_name' => 'img' ) ) ) {
return '';
}
$src = $html->get_attribute( 'src' );
if ( ! is_string( $src ) || '' === $src ) {
return '';
}
$raw_width = $html->get_attribute( 'width' );
$raw_height = $html->get_attribute( 'height' );
$width = is_string( $raw_width ) && is_numeric( $raw_width ) ? (int) $raw_width : 0;
$height = is_string( $raw_height ) && is_numeric( $raw_height ) ? (int) $raw_height : 0;
if ( $width > 0 && $height > 0 ) {
$scaled_height = max( 1, (int) round( $height * ( $cell_width / $width ) ) );
$html->set_attribute( 'height', esc_attr( (string) $scaled_height ) );
} else {
$html->remove_attribute( 'height' );
}
$html->set_attribute( 'width', esc_attr( (string) $cell_width ) );
$html->remove_attribute( 'class' );
$html->set_attribute( 'style', esc_attr( self::IMAGE_STYLE ) );
return $html->get_updated_html();
}
}
