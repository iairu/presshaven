<?php
namespace Automattic\Jetpack\Autoloader\jpbd85136368c3501bec76a9a8dd9738ea\al5_0_23;
if (!defined('ABSPATH')) exit;
use Automattic\Jetpack\Autoloader\AutoloadGenerator;
class Autoloader_Handler {
private $php_autoloader;
private $hook_manager;
private $manifest_reader;
private $version_selector;
public function __construct( $php_autoloader, $hook_manager, $manifest_reader, $version_selector ) {
$this->php_autoloader = $php_autoloader;
$this->hook_manager = $hook_manager;
$this->manifest_reader = $manifest_reader;
$this->version_selector = $version_selector;
}
public function is_initializing() {
global $jetpack_autoloader_latest_version;
if ( ! isset( $jetpack_autoloader_latest_version ) ) {
return false;
}
global $jetpack_packages_classmap;
if ( empty( $jetpack_packages_classmap ) ) {
return true;
}
$replacing_version = $jetpack_packages_classmap[ AutoloadGenerator::class ]['version'];
if ( $this->version_selector->is_dev_version( $replacing_version ) || version_compare( $replacing_version, '2.4.0.0', '>=' ) ) {
global $jetpack_autoloader_loader;
if ( ! isset( $jetpack_autoloader_loader ) ) {
return true;
}
}
return false;
}
public function activate_autoloader( $plugins ) {
global $jetpack_packages_psr4;
$jetpack_packages_psr4 = array();
$this->manifest_reader->read_manifests( $plugins, 'vendor/composer/jetpack_autoload_psr4.php', $jetpack_packages_psr4 );
global $jetpack_packages_classmap;
$jetpack_packages_classmap = array();
$this->manifest_reader->read_manifests( $plugins, 'vendor/composer/jetpack_autoload_classmap.php', $jetpack_packages_classmap );
global $jetpack_packages_filemap;
$jetpack_packages_filemap = array();
$this->manifest_reader->read_manifests( $plugins, 'vendor/composer/jetpack_autoload_filemap.php', $jetpack_packages_filemap );
$loader = new Version_Loader(
$this->version_selector,
$jetpack_packages_classmap,
$jetpack_packages_psr4,
$jetpack_packages_filemap
);
$this->php_autoloader->register_autoloader( $loader );
$loader->load_filemap();
}
public function reset_autoloader() {
$this->php_autoloader->unregister_autoloader();
$this->hook_manager->reset();
global $jetpack_autoloader_latest_version;
$jetpack_autoloader_latest_version = null;
global $jetpack_packages_classmap;
$jetpack_packages_classmap = array();
global $jetpack_packages_psr4;
$jetpack_packages_psr4 = array();
global $jetpack_packages_filemap;
$jetpack_packages_filemap = array();
}
}
