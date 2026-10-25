<?php
if (!defined('ABSPATH')) exit;
class Plugin_Locator {
private $path_processor;
public function __construct( $path_processor ) {
$this->path_processor = $path_processor;
}
public function find_current_plugin() {
$plugin_directory = dirname( __DIR__, 2 );
$path = $this->path_processor->find_directory_with_autoloader( $plugin_directory, array() );
if ( false === $path ) {
throw new \RuntimeException( 'Failed to locate plugin ' . $plugin_directory );
}
return $path;
}
public function find_using_option( $option_name, $site_option = false ) {
$raw = $site_option ? get_site_option( $option_name ) : get_option( $option_name );
if ( false === $raw ) {
return array();
}
return $this->convert_plugins_to_paths( $raw );
}
public function find_using_request_action( $allowed_actions ) {
if ( empty( $_REQUEST['_wpnonce'] ) ) {
return array();
}
$action = isset( $_REQUEST['action'] ) ? wp_unslash( $_REQUEST['action'] ) : false;
if ( ! in_array( $action, $allowed_actions, true ) ) {
return array();
}
$plugin_slugs = array();
switch ( $action ) {
case 'activate':
case 'deactivate':
if ( empty( $_REQUEST['plugin'] ) ) {
break;
}
$plugin_slugs[] = wp_unslash( $_REQUEST['plugin'] );
break;
case 'activate-selected':
case 'deactivate-selected':
if ( empty( $_REQUEST['checked'] ) ) {
break;
}
$plugin_slugs = wp_unslash( $_REQUEST['checked'] );
break;
}
return $this->convert_plugins_to_paths( $plugin_slugs );
}
private function convert_plugins_to_paths( $plugins ) {
if ( ! is_array( $plugins ) || empty( $plugins ) ) {
return array();
}
$path_constants = array( WP_PLUGIN_DIR, WPMU_PLUGIN_DIR );
$plugin_paths = array();
foreach ( $plugins as $key => $value ) {
$path = $this->path_processor->find_directory_with_autoloader( $key, $path_constants );
if ( $path ) {
$plugin_paths[] = $path;
}
$path = $this->path_processor->find_directory_with_autoloader( $value, $path_constants );
if ( $path ) {
$plugin_paths[] = $path;
}
}
return $plugin_paths;
}
}
