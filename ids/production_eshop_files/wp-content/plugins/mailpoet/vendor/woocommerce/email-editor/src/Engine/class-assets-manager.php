<?php
declare(strict_types=1);
namespace Automattic\WooCommerce\EmailEditor\Engine;
if (!defined('ABSPATH')) exit;
use Automattic\WooCommerce\EmailEditor\Engine\Logger\Email_Editor_Logger;
class Assets_Manager {
private Settings_Controller $settings_controller;
private Theme_Controller $theme_controller;
private User_Theme $user_theme;
private string $assets_path = '';
private string $assets_url = '';
private Email_Editor_Logger $logger;
private bool $editor_html_rendered = false;
public function __construct(
Settings_Controller $settings_controller,
Theme_Controller $theme_controller,
User_Theme $user_theme,
Email_Editor_Logger $logger
) {
$this->settings_controller = $settings_controller;
$this->theme_controller = $theme_controller;
$this->user_theme = $user_theme;
$this->logger = $logger;
}
public function set_assets_path( string $assets_path ): void {
$this->assets_path = $assets_path;
}
public function set_assets_url( string $assets_url ): void {
$this->assets_url = $assets_url;
}
public function initialize(): void {
add_action( 'admin_enqueue_scripts', array( $this, 'enqueue_admin_styles' ) );
}
public function enqueue_admin_styles(): void {
do_action( 'enqueue_block_editor_assets' );
wp_enqueue_style( 'wp-edit-post' );
wp_add_inline_style( 'wp-edit-post', (string) file_get_contents( __DIR__ . '/rich-text-comment.css' ) );
wp_enqueue_style( 'wp-format-library' );
wp_enqueue_global_styles_css_custom_properties();
wp_enqueue_media();
}
public function render_email_editor_html( string $element_id = 'woocommerce-email-editor' ): void {
if ( $this->editor_html_rendered ) {
return;
}
$this->editor_html_rendered = true;
require_once ABSPATH . 'wp-admin/admin-header.php';
echo '<div id="' . esc_attr( $element_id ) . '" class="block-editor block-editor__container hide-if-no-js"></div>';
}
public function load_editor_assets( $edited_item, string $script_name ): void {
$post_type = $edited_item instanceof \WP_Post ? $edited_item->post_type : 'wp_template';
$post_id = $edited_item instanceof \WP_Post ? $edited_item->ID : $edited_item->id;
$email_editor_assets_path = rtrim( $this->assets_path, '/' ) . '/';
$email_editor_assets_url = rtrim( $this->assets_url, '/' ) . '/';
$assets_file = $email_editor_assets_path . 'style.asset.php';
if ( ! file_exists( $assets_file ) ) {
$this->logger->error( 'Email editor assets file does not exist.', array( 'path' => $assets_file ) );
} else {
$assets_file = require $assets_file;
wp_enqueue_style(
'wc-admin-email-editor-integration',
$email_editor_assets_url . 'style.css',
array(),
$assets_file['version']
);
}
if ( $edited_item instanceof \WP_Block_Template ) {
$context = new \WP_Block_Editor_Context(
array(
'post' => $edited_item,
)
);
} else {
$context = $edited_item;
}
wp_add_inline_script(
'wp-blocks',
sprintf( 'wp.blocks.setCategories( %s );', wp_json_encode( get_block_categories( $context ), JSON_HEX_TAG | JSON_UNESCAPED_SLASHES ) ),
'after'
);
wp_add_inline_script(
'wp-blocks',
sprintf( 'wp.blocks.unstable__bootstrapServerSideBlockDefinitions( %s );', wp_json_encode( get_block_editor_server_block_settings(), JSON_HEX_TAG | JSON_UNESCAPED_SLASHES ) )
);
$localization_data = array(
'current_post_type' => $post_type,
'current_post_id' => $post_id,
'current_wp_user_email' => wp_get_current_user()->user_email,
'editor_settings' => $this->settings_controller->get_settings(),
'editor_theme' => $this->theme_controller->get_base_theme()->get_raw_data(),
'user_theme_post_id' => $this->user_theme->get_user_theme_post()->ID,
'urls' => array(
'listings' => admin_url( 'admin.php?page=wc-settings&tab=email' ),
'send' => admin_url( 'admin.php?page=wc-settings&tab=email' ),
'back' => admin_url( 'admin.php?page=wc-settings&tab=email' ),
'createCoupon' => admin_url( 'post-new.php?post_type=shop_coupon' ),
),
);
wp_localize_script(
$script_name,
'WooCommerceEmailEditor',
apply_filters( 'woocommerce_email_editor_script_localization_data', $localization_data )
);
$this->preload_rest_api_data( $post_id, $post_type );
}
private function preload_rest_api_data( $post_id, string $post_type ): void {
$email_post_type = $post_type;
$user_theme_post_id = $this->user_theme->get_user_theme_post()->ID;
$post = is_numeric( $post_id ) ? get_post( (int) $post_id ) : null;
$template_slug = get_post_meta( (int) $post_id, '_wp_page_template', true );
$routes = array(
"/wp/v2/{$email_post_type}/" . intval( $post_id ) . '?context=edit',
"/wp/v2/types/{$email_post_type}?context=edit",
'/wp/v2/global-styles/' . intval( $user_theme_post_id ) . '?context=view',
'/wp/v2/block-patterns/patterns',
'/wp/v2/templates?context=view',
'/wp/v2/block-patterns/categories',
'/wp/v2/settings',
'/wp/v2/types?context=view',
'/wp/v2/taxonomies?context=view',
);
if ( is_string( $template_slug ) && '' !== $template_slug ) {
$routes[] = '/wp/v2/templates/lookup?slug=' . $template_slug;
}
if ( $post instanceof \WP_Post && '' === $post->post_content ) {
$routes[] = "/wp/v2/{$email_post_type}?context=edit&per_page=30&status=publish,sent";
}
$routes = apply_filters( 'woocommerce_email_editor_preload_rest_api_routes', $routes, $post_type, $post_id );
if ( ! is_array( $routes ) ) {
$routes = array();
}
$preload_data = array_reduce(
$routes,
'rest_preload_api_request',
array()
);
wp_add_inline_script(
'wp-blocks',
sprintf(
'wp.apiFetch.use( wp.apiFetch.createPreloadingMiddleware( %s ) );',
wp_json_encode( $preload_data, JSON_HEX_TAG | JSON_UNESCAPED_SLASHES )
)
);
}
}
