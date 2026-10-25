<?php
if (!defined('ABSPATH')) exit;
class Base_MixpanelBase {
private $_defaults = array(
"max_batch_size" => 50,
"max_queue_size" => 1000,
"debug" => false,
"consumer" => "curl",
"host" => "api.mixpanel.com",
"events_endpoint" => "/track",
"people_endpoint" => "/engage",
"groups_endpoint" => "/groups",
"use_ssl" => true,
"error_callback" => null
);
protected $_options = array();
public function __construct($options = array()) {
$options = array_merge($this->_defaults, $options);
$this->_options = $options;
}
protected function _log($msg) {
$arr = debug_backtrace();
$class = $arr[0]['class'];
$line = $arr[0]['line'];
error_log ( "[ $class - line $line ] : " . $msg );
}
protected function _debug() {
return isset($this->_options["debug"]) && $this->_options["debug"] == true;
}
}
