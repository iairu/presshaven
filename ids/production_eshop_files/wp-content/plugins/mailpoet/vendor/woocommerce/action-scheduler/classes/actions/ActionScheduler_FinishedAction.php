<?php
if (!defined('ABSPATH')) exit;
class ActionScheduler_FinishedAction extends ActionScheduler_Action {
public function execute() {
}
public function is_finished() {
return true;
}
}
