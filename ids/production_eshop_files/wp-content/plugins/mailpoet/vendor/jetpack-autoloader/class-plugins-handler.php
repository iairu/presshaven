<?php
namespace Automattic\Jetpack\Autoloader\jpbd85136368c3501bec76a9a8dd9738ea\al5_0_23;
if (!defined('ABSPATH')) exit;
class Plugins_Handler {
const TRANSIENT_KEY = 'jetpack_autoloader_plugin_paths';
private $plugin_locator;
private $path_processor;
public function __construct( $plugin_locator, $path_processor ) {
$this->plugin_locator = $plugin_locator;
$this->path_processor = $path_processor;
}
public function get_active_plugins( $include_deactivating, $record_unknown ) {
global $jetpack_autoloader_activating_plugins_paths;
$active_plugins = array();
if ( is_array( $jetpack_autoloader_activating_plugins_paths ) ) {
foreach ( $jetpack_autoloader_activating_plugins_paths as $path ) {
$active_plugins[ $path ] = $path;
}
}
$plugins = $this->plugin_locator->find_using_option( 'active_plugins' );
foreach ( $plugins as $path ) {
$active_plugins[ $path ] = $path;
}
if ( is_multisite() ) {
$plugins = $this->plugin_locator->find_using_option( 'active_sitewide_plugins', true );
foreach ( $plugins as $path ) {
$active_plugins[ $path ] = $path;
}
}
$plugins = $this->plugin_locator->find_using_request_action( array( 'activate', 'activate-selected', 'deactivate', 'deactivate-selected' ) );
foreach ( $plugins as $path ) {
$active_plugins[ $path ] = $path;
}
$current_plugin = $this->plugin_locator->find_current_plugin();
if ( $record_unknown && ! in_array( $current_plugin, $active_plugins, true ) ) {
$active_plugins[ $current_plugin ] = $current_plugin;
$jetpack_autoloader_activating_plugins_paths[] = $current_plugin;
}
if ( ! $include_deactivating ) {
$plugins = $this->plugin_locator->find_using_request_action( array( 'deactivate', 'deactivate-selected' ) );
foreach ( $plugins as $path ) {
unset( $active_plugins[ $path ] );
}
}
return array_values( $active_plugins );
}
public function get_cached_plugins() {
$cached = get_transient( self::TRANSIENT_KEY );
if ( ! is_array( $cached ) || empty( $cached ) ) {
return array();
}
return array_map( array( $this->path_processor, 'untokenize_path_constants' ), $cached );
}
public function cache_plugins( $plugins ) {
$plugins = array_map( array( $this->path_processor, 'tokenize_path_constants' ), $plugins );
set_transient( self::TRANSIENT_KEY, $plugins );
}
public function have_plugins_changed( $plugins ) {
global $jetpack_autoloader_cached_plugin_paths;
if ( $jetpack_autoloader_cached_plugin_paths !== $plugins ) {
$jetpack_autoloader_cached_plugin_paths = $plugins;
return true;
}
return false;
}
}
