<?php
if (!defined('ABSPATH')) exit;
class PHP_Autoloader {
public function register_autoloader( $version_loader ) {
$this->unregister_autoloader();
global $jetpack_autoloader_loader;
$jetpack_autoloader_loader = $version_loader;
spl_autoload_register( array( self::class, 'load_class' ), true, true );
}
public function unregister_autoloader() {
$autoload_chain = spl_autoload_functions();
if ( ! $autoload_chain ) {
return;
}
foreach ( $autoload_chain as $autoloader ) {
$namespace_check = null;
if ( is_string( $autoloader ) ) {
$namespace_check = $autoloader;
} elseif ( is_array( $autoloader ) && is_string( $autoloader[0] ) ) {
$namespace_check = $autoloader[0];
} else {
continue;
}
if ( 'Automattic\\Jetpack\\Autoloader\\jp' === substr( $namespace_check, 0, 32 ) ) {
spl_autoload_unregister( $autoloader );
}
}
global $jetpack_autoloader_loader;
$jetpack_autoloader_loader = null;
}
public static function load_class( $class_name ) {
global $jetpack_autoloader_loader;
if ( ! isset( $jetpack_autoloader_loader ) ) {
return false;
}
$file = $jetpack_autoloader_loader->find_class_file( $class_name );
if ( ! isset( $file ) ) {
return false;
}
if ( defined( 'JETPACK_AUTOLOAD_DEBUG_EARLY_LOADS' ) && JETPACK_AUTOLOAD_DEBUG_EARLY_LOADS &&
( strpos( $file, '/vendor/' ) !== false || strpos( $file, '/jetpack_vendor/' ) !== false ) &&
is_callable( 'did_action' ) && ! did_action( 'plugins_loaded' )
) {
$msg = "Jetpack Autoloader: Autoloading `$class_name` before the plugins_loaded hook may cause strange and confusing problems. " . wp_debug_backtrace_summary( '', 1 );
wp_trigger_error( '', $msg );
}
require $file;
return true;
}
}
