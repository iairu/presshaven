<?php
if (!defined('ABSPATH')) exit;
$template_html = apply_filters( 'woocommerce_email_editor_preview_post_template_html', get_post() );
echo $template_html;
