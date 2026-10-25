<?php
if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

$glt_css = wp_kses_post(
    (string) get_option( 'googlelanguagetranslator_css', '' )
);

$language_switcher_width = sanitize_text_field(
    (string) get_option( 'glt_language_switcher_width', '' )
);

$language_switcher_text_color = sanitize_hex_color(
    get_option( 'glt_language_switcher_text_color', '' )
);

$language_switcher_bg_color = sanitize_hex_color(
    get_option( 'glt_language_switcher_bg_color', '' )
);

$glt_display = sanitize_text_field(
    (string) get_option( 'googlelanguagetranslator_display', '' )
);

if ( 'SIMPLE' === $glt_display ) {
    $glt_display = 'Vertical';
}

$floating_widget_position = sanitize_key(
    get_option( 'glt_floating_widget_position', '' )
);

$floating_widget_text_color = sanitize_hex_color(
    get_option( 'glt_floating_widget_text_color', '' )
);

$floating_widget_bg_color = sanitize_hex_color(
    get_option( 'glt_floating_widget_bg_color', '' )
);

$css = $glt_css;

if ( 1 === absint( get_option( 'googlelanguagetranslator_flags' ) ) ) {
    $alignment = sanitize_key(
        get_option( 'googlelanguagetranslator_flags_alignment', '' )
    );

    $is_horizontal = 'Horizontal' === $glt_display;
    $is_right      = 'flags_right' === $alignment;

    $display    = $is_horizontal ? 'inline-block' : 'block';
    $clear      = $is_horizontal ? 'none' : 'both';
    $text_align = $is_right ? 'right' : 'left';
    $text_color = $is_horizontal ? '#666' : 'darkgray';

    $css .= "#flags,#google_language_translator {display:{$display};float:none;clear:{$clear};vertical-align:middle;text-align:{$text_align};}";
    $css .= '#google_language_translator {width:auto;}';
    $css .= '#flags ul {float:none!important;}';
    $css .= '#flags a {display:inline-block;margin-left:0;margin-right:0;}';
    $css .= '#google_language_translator select.gt_selector {float:none;}';
    $css .= "p.hello {font-size:12px;color:{$text_color};text-align:{$text_align};}";

    if ( $is_right ) {
        $css .= '#flags a {margin-left:2px;}';
    } else {
        $css .= '#flags a {margin-right:2px;}';
    }
}

if (
    'no' === get_option( 'googlelanguagetranslator_translatebox' ) &&
    1 === absint( get_option( 'googlelanguagetranslator_active' ) )
) {
    $css .= '#google_language_translator {display:none;}';
}

if ( ! empty( $language_switcher_text_color ) ) {
    $css .= '#google_language_translator select.gt_selector{color:' . $language_switcher_text_color . ';}';
}

if (
    0 === absint( get_option( 'googlelanguagetranslator_flags' ) ) &&
    1 === absint( get_option( 'googlelanguagetranslator_active' ) )
) {
    $css .= '#flags {display:none;}';
}

if ( 'bottom_left' === $floating_widget_position ) {
    $css .= '#glt-translate-trigger{left:20px;right:auto;}';
} elseif ( 'top_right' === $floating_widget_position ) {
    $css .= '#glt-translate-trigger{bottom:auto;top:0;}';
    $css .= '.tool-container.tool-top{top:50px!important;bottom:auto!important;}';
    $css .= '.tool-container.tool-top .arrow{border-color:transparent transparent #d0cbcb;top:-14px;}';
} elseif ( 'top_left' === $floating_widget_position ) {
    $css .= '#glt-translate-trigger{bottom:auto;top:0;left:20px;right:auto;}';
    $css .= '.tool-container.tool-top{top:50px!important;bottom:auto!important;}';
    $css .= '.tool-container.tool-top .arrow{border-color:transparent transparent #d0cbcb;top:-14px;}';
} elseif ( 'top_center' === $floating_widget_position ) {
    $css .= '#glt-translate-trigger{bottom:auto;top:0;left:50%;margin-left:-63px;right:auto;}';
    $css .= '.tool-container.tool-top{top:50px!important;bottom:auto!important;}';
    $css .= '.tool-container.tool-top .arrow{border-color:transparent transparent #d0cbcb;top:-14px;}';
} elseif ( 'bottom_center' === $floating_widget_position ) {
    $css .= '#glt-translate-trigger{left:50%;margin-left:-63px;right:auto;}';
}

if ( ! empty( $floating_widget_text_color ) ) {
    $css .= '#glt-translate-trigger > span{color:' . $floating_widget_text_color . ';}';
}

if ( ! empty( $floating_widget_bg_color ) ) {
    $css .= '#glt-translate-trigger{background:' . $floating_widget_bg_color . ';}';
}

if (
    ! empty( $language_switcher_width ) &&
    'Horizontal' !== $glt_display
) {
    $css .= 'select.gt_selector{width:' . $language_switcher_width . ';}';
}

if ( ! empty( $language_switcher_bg_color ) ) {
    $css .= '#google_language_translator select.gt_selector{background:' . $language_switcher_bg_color . ';border:0!important;}';
}

echo '<style>';
echo wp_kses_post( $css );
echo '</style>';