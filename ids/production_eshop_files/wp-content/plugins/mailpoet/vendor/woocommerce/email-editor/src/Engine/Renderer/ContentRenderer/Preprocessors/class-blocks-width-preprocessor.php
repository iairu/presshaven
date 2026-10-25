<?php
declare(strict_types = 1);
namespace Automattic\WooCommerce\EmailEditor\Engine\Renderer\ContentRenderer\Preprocessors;
if (!defined('ABSPATH')) exit;
use Automattic\WooCommerce\EmailEditor\Engine\Renderer\ContentRenderer\Preset_Variable_Resolver;
class Blocks_Width_Preprocessor implements Preprocessor {
public function preprocess( array $parsed_blocks, array $layout, array $styles ): array {
$variables_map = $styles['__variables_map'] ?? array();
$styles['spacing']['padding']['left'] = '0px';
$styles['spacing']['padding']['right'] = '0px';
return $this->calculate_widths( $parsed_blocks, $layout, $styles, $variables_map );
}
private function calculate_widths( array $parsed_blocks, array $layout, array $styles, array $variables_map = array() ): array {
foreach ( $parsed_blocks as $key => $block ) {
$layout_width = $this->parse_number_from_string_with_pixels( $layout['contentSize'] );
$alignment = $block['attrs']['align'] ?? null;
if ( 'full' !== $alignment ) {
$layout_width -= $this->parse_number_from_string_with_pixels( $styles['spacing']['padding']['left'] ?? '0px' );
$layout_width -= $this->parse_number_from_string_with_pixels( $styles['spacing']['padding']['right'] ?? '0px' );
}
if ( 'full' !== $alignment ) {
$layout_width -= $this->parse_number_from_string_with_pixels( $block['email_attrs']['root-padding-left'] ?? '0px' );
$layout_width -= $this->parse_number_from_string_with_pixels( $block['email_attrs']['root-padding-right'] ?? '0px' );
$layout_width -= $this->parse_number_from_string_with_pixels( Preset_Variable_Resolver::resolve( $block['email_attrs']['container-padding-left'] ?? '0px', $variables_map ) );
$layout_width -= $this->parse_number_from_string_with_pixels( Preset_Variable_Resolver::resolve( $block['email_attrs']['container-padding-right'] ?? '0px', $variables_map ) );
}
$suppress_h_padding = ! empty( $block['email_attrs']['suppress-horizontal-padding'] );
$block_padding_left = $suppress_h_padding ? '0px' : Preset_Variable_Resolver::resolve( $block['attrs']['style']['spacing']['padding']['left'] ?? '0px', $variables_map );
$block_padding_right = $suppress_h_padding ? '0px' : Preset_Variable_Resolver::resolve( $block['attrs']['style']['spacing']['padding']['right'] ?? '0px', $variables_map );
$block_border_horizontal = $this->get_block_horizontal_border( $block );
$width_input = $block['attrs']['width'] ?? '100%';
$width_input = is_numeric( $width_input ) ? "$width_input%" : $width_input;
$width_input = is_string( $width_input ) ? $width_input : '100%';
$width = $this->convert_width_to_pixels( $width_input, $layout_width );
if ( 'core/columns' === $block['blockName'] ) {
$columns_width = $layout_width;
$columns_width -= $this->parse_number_from_string_with_pixels( $block_padding_left );
$columns_width -= $this->parse_number_from_string_with_pixels( $block_padding_right );
$border_width = $block['attrs']['style']['border']['width'] ?? '0px';
$columns_width -= $this->parse_number_from_string_with_pixels( $block['attrs']['style']['border']['left']['width'] ?? $border_width );
$columns_width -= $this->parse_number_from_string_with_pixels( $block['attrs']['style']['border']['right']['width'] ?? $border_width );
$block['innerBlocks'] = $this->add_missing_column_widths( $block['innerBlocks'], $columns_width, $variables_map );
}
$inner_content_width = max( 0, $width - $block_border_horizontal );
$modified_layout = $layout;
$modified_layout['contentSize'] = "{$inner_content_width}px";
$modified_styles = $styles;
$modified_styles['spacing']['padding']['left'] = $block_padding_left;
$modified_styles['spacing']['padding']['right'] = $block_padding_right;
$block['email_attrs']['width'] = "{$width}px";
$block['innerBlocks'] = $this->calculate_widths( $block['innerBlocks'], $modified_layout, $modified_styles, $variables_map );
$parsed_blocks[ $key ] = $block;
}
return $parsed_blocks;
}
private function convert_width_to_pixels( string $current_width, float $layout_width ): float {
$width = $layout_width;
if ( strpos( $current_width, '%' ) !== false ) {
$width = (float) str_replace( '%', '', $current_width );
$width = round( $width / 100 * $layout_width );
} elseif ( strpos( $current_width, 'px' ) !== false ) {
$width = $this->parse_number_from_string_with_pixels( $current_width );
}
return $width;
}
private function parse_number_from_string_with_pixels( string $value ): float {
return (float) str_replace( 'px', '', $value );
}
private function get_block_horizontal_border( array $block ): float {
$border_width = $block['attrs']['style']['border']['width'] ?? '0px';
$left = $block['attrs']['style']['border']['left']['width'] ?? $border_width;
$right = $block['attrs']['style']['border']['right']['width'] ?? $border_width;
return $this->parse_number_from_string_with_pixels( (string) $left ) + $this->parse_number_from_string_with_pixels( (string) $right );
}
private function add_missing_column_widths( array $columns, float $columns_width, array $variables_map = array() ): array {
$columns_count_with_defined_width = 0;
$defined_column_width = 0;
$columns_count = count( $columns );
foreach ( $columns as $column ) {
if ( isset( $column['attrs']['width'] ) && ! empty( $column['attrs']['width'] ) ) {
++$columns_count_with_defined_width;
$defined_column_width += $this->convert_width_to_pixels( $column['attrs']['width'], $columns_width );
} else {
$defined_column_width += $this->parse_number_from_string_with_pixels( Preset_Variable_Resolver::resolve( $column['attrs']['style']['spacing']['padding']['left'] ?? '0px', $variables_map ) );
$defined_column_width += $this->parse_number_from_string_with_pixels( Preset_Variable_Resolver::resolve( $column['attrs']['style']['spacing']['padding']['right'] ?? '0px', $variables_map ) );
$border_width = $column['attrs']['style']['border']['width'] ?? '0px';
$defined_column_width += $this->parse_number_from_string_with_pixels( $column['attrs']['style']['border']['left']['width'] ?? $border_width );
$defined_column_width += $this->parse_number_from_string_with_pixels( $column['attrs']['style']['border']['right']['width'] ?? $border_width );
}
}
if ( $columns_count - $columns_count_with_defined_width > 0 ) {
$default_columns_width = round( ( $columns_width - $defined_column_width ) / ( $columns_count - $columns_count_with_defined_width ), 2 );
foreach ( $columns as $key => $column ) {
if ( ! isset( $column['attrs']['width'] ) || empty( $column['attrs']['width'] ) ) {
$column_width = $default_columns_width;
$column_width += $this->parse_number_from_string_with_pixels( Preset_Variable_Resolver::resolve( $column['attrs']['style']['spacing']['padding']['left'] ?? '0px', $variables_map ) );
$column_width += $this->parse_number_from_string_with_pixels( Preset_Variable_Resolver::resolve( $column['attrs']['style']['spacing']['padding']['right'] ?? '0px', $variables_map ) );
$border_width = $column['attrs']['style']['border']['width'] ?? '0px';
$column_width += $this->parse_number_from_string_with_pixels( $column['attrs']['style']['border']['left']['width'] ?? $border_width );
$column_width += $this->parse_number_from_string_with_pixels( $column['attrs']['style']['border']['right']['width'] ?? $border_width );
$columns[ $key ]['attrs']['width'] = "{$column_width}px";
}
}
}
return $columns;
}
}
