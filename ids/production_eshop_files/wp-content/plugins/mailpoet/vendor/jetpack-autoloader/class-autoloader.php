<?php
namespace Automattic\Jetpack\Autoloader\jpbd85136368c3501bec76a9a8dd9738ea\al5_0_23;
if (!defined('ABSPATH')) exit;
class Autoloader {
public static function init( $container = null ) {
if ( ! isset( $container ) ) {
require_once __DIR__ . '/class-container.php';
$container = new Container();
}
$autoloader_handler = $container->get( Autoloader_Handler::class );
$was_included_by_autoloader = $autoloader_handler->is_initializing();
$plugin_locator = $container->get( Plugin_Locator::class );
$plugins_handler = $container->get( Plugins_Handler::class );
$current_plugin = $plugin_locator->find_current_plugin();
$active_plugins = $plugins_handler->get_active_plugins( true, ! $was_included_by_autoloader );
$cached_plugins = $plugins_handler->get_cached_plugins();
$all_plugins = array_merge( $active_plugins, $cached_plugins );
$all_plugins[] = $current_plugin;
$all_plugins = array_values( array_unique( $all_plugins ) );
$guard = $container->get( Latest_Autoloader_Guard::class );
if ( $guard->should_stop_init( $current_plugin, $all_plugins, $was_included_by_autoloader ) ) {
return;
}
$autoloader_handler->activate_autoloader( $all_plugins );
$hook_manager = $container->get( Hook_Manager::class );
$hook_manager->add_action( 'shutdown', new Shutdown_Handler( $plugins_handler, $cached_plugins, $was_included_by_autoloader ) );
$hook_manager->add_action( 'plugins_loaded', array( $guard, 'check_for_conflicting_autoloaders' ), 1 );
}
}
