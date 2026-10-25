<?php
declare(strict_types = 1);
namespace Automattic\WooCommerce\EmailEditor\Engine\Renderer\ContentRenderer\Preprocessors;
if (!defined('ABSPATH')) exit;
class Cleanup_Preprocessor implements Preprocessor {
public function preprocess( array $parsed_blocks, array $layout, array $styles ): array {
foreach ( $parsed_blocks as $key => $block ) {
if ( null === $block['blockName'] && '' === trim( $block['innerHTML'] ?? '' ) ) {
unset( $parsed_blocks[ $key ] );
}
}
return array_values( $parsed_blocks );
}
}
