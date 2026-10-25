<?php
if (!defined('ABSPATH')) exit;
if ( ! function_exists( 'action_scheduler_register_3_dot_9_dot_3' ) && function_exists( 'add_action' ) ) {
if ( ! class_exists( 'ActionScheduler_Versions', false ) ) {
require_once __DIR__ . '/classes/ActionScheduler_Versions.php';
add_action( 'plugins_loaded', array( 'ActionScheduler_Versions', 'initialize_latest_version' ), 1, 0 );
}
add_action( 'plugins_loaded', 'action_scheduler_register_3_dot_9_dot_3', 0, 0 );
function action_scheduler_register_3_dot_9_dot_3() {
$versions = ActionScheduler_Versions::instance();
$versions->register( '3.9.3', 'action_scheduler_initialize_3_dot_9_dot_3' );
}
function action_scheduler_initialize_3_dot_9_dot_3() {
if ( ! class_exists( 'ActionScheduler', false ) ) {
require_once __DIR__ . '/classes/abstracts/ActionScheduler.php';
ActionScheduler::init( __FILE__ );
}
}
if ( did_action( 'plugins_loaded' ) && ! doing_action( 'plugins_loaded' ) && ! class_exists( 'ActionScheduler', false ) ) {
action_scheduler_initialize_3_dot_9_dot_3();
do_action( 'action_scheduler_pre_theme_init' );
ActionScheduler_Versions::initialize_latest_version();
}
}
