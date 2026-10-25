<?php
namespace Automattic\Jetpack\Autoloader\jpbd85136368c3501bec76a9a8dd9738ea\al5_0_23;
if (!defined('ABSPATH')) exit;
class Shutdown_Handler {
private $plugins_handler;
private $cached_plugins;
private $was_included_by_autoloader;
public function __construct( $plugins_handler, $cached_plugins, $was_included_by_autoloader ) {
$this->plugins_handler = $plugins_handler;
$this->cached_plugins = $cached_plugins;
$this->was_included_by_autoloader = $was_included_by_autoloader;
}
public function __invoke() {
if ( ! did_action( 'plugins_loaded' ) ) {
if ( ! empty( $this->cached_plugins ) ) {
$this->plugins_handler->cache_plugins( array() );
}
return;
}
try {
$active_plugins = $this->plugins_handler->get_active_plugins( false, ! $this->was_included_by_autoloader );
} catch ( \Exception $ex ) {
if ( ! empty( $this->cached_plugins ) ) {
$this->plugins_handler->cache_plugins( array() );
}
return;
}
sort( $active_plugins );
if ( $this->cached_plugins === $active_plugins ) {
return;
}
$this->plugins_handler->cache_plugins( $active_plugins );
}
}
