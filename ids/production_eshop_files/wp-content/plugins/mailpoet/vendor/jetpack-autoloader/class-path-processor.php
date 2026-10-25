<?php
namespace Automattic\Jetpack\Autoloader\jpbd85136368c3501bec76a9a8dd9738ea\al5_0_23;
if (!defined('ABSPATH')) exit;
class Path_Processor {
public function tokenize_path_constants( $path ) {
$path = wp_normalize_path( $path );
$constants = $this->get_normalized_constants();
foreach ( $constants as $constant => $constant_path ) {
$len = strlen( $constant_path );
if ( substr( $path, 0, $len ) !== $constant_path ) {
continue;
}
return substr_replace( $path, '{{' . $constant . '}}', 0, $len );
}
return $path;
}
public function untokenize_path_constants( $tokenized_path ) {
$tokenized_path = wp_normalize_path( $tokenized_path );
$constants = $this->get_normalized_constants();
foreach ( $constants as $constant => $constant_path ) {
$constant = '{{' . $constant . '}}';
$len = strlen( $constant );
if ( substr( $tokenized_path, 0, $len ) !== $constant ) {
continue;
}
return $this->get_real_path( substr_replace( $tokenized_path, $constant_path, 0, $len ) );
}
return $tokenized_path;
}
public function find_directory_with_autoloader( $file, $directories_to_check ) {
$file = wp_normalize_path( $file );
if ( ! $this->is_absolute_path( $file ) ) {
$file = $this->find_absolute_plugin_path( $file, $directories_to_check );
if ( ! isset( $file ) ) {
return false;
}
}
$file = $this->get_real_path( $file );
$directory = @is_file( $file ) ? dirname( $file ) : $file;
if ( ! @is_file( $directory . '/vendor/composer/jetpack_autoload_classmap.php' ) ) {
return false;
}
return $directory;
}
private function get_normalized_constants() {
$raw_constants = array(
'WP_PLUGIN_DIR',
'WPMU_PLUGIN_DIR',
'WP_CONTENT_DIR',
'ABSPATH',
);
$constants = array();
foreach ( $raw_constants as $raw ) {
if ( ! defined( $raw ) ) {
continue;
}
$path = wp_normalize_path( constant( $raw ) );
if ( isset( $path ) ) {
$constants[ $raw ] = $path;
}
}
return $constants;
}
private function is_absolute_path( $path ) {
if ( empty( $path ) || 0 === strlen( $path ) || '.' === $path[0] ) {
return false;
}
if ( preg_match( '/^[a-zA-Z]:[\/\\\\]/', $path ) ) {
return true;
}
return ( '/' === $path[0] || '\\' === $path[0] );
}
private function find_absolute_plugin_path( $normalized_path, $directories_to_check ) {
if ( ! is_string( $normalized_path ) || '.php' !== substr( $normalized_path, -4 ) ) {
return null;
}
foreach ( $directories_to_check as $directory ) {
$normalized_check = wp_normalize_path( trailingslashit( $directory ) ) . $normalized_path;
if ( @is_file( $normalized_check ) ) {
return $normalized_check;
}
}
return null;
}
private function get_real_path( $path ) {
$real_path = @realpath( $path );
if ( false === $real_path ) {
$real_path = $path;
}
if ( $path !== $real_path ) {
$real_path = wp_normalize_path( $real_path );
}
return $real_path;
}
}
