<?php
namespace Action_Scheduler\WP_CLI\Action;
if (!defined('ABSPATH')) exit;
use function \WP_CLI\Utils\get_flag_value;
class Next_Command extends \ActionScheduler_WPCLI_Command {
public function execute() {
$hook = $this->args[0];
$group = get_flag_value( $this->assoc_args, 'group', '' );
$callback_args = get_flag_value( $this->assoc_args, 'args', null );
$raw = (bool) get_flag_value( $this->assoc_args, 'raw', false );
if ( ! empty( $callback_args ) ) {
$callback_args = json_decode( $callback_args, true );
}
if ( $raw ) {
\WP_CLI::line( as_next_scheduled_action( $hook, $callback_args, $group ) );
return;
}
$params = array(
'hook' => $hook,
'orderby' => 'date',
'order' => 'ASC',
'group' => $group,
);
if ( is_array( $callback_args ) ) {
$params['args'] = $callback_args;
}
$params['status'] = \ActionScheduler_Store::STATUS_RUNNING;
\WP_CLI::debug( 'ActionScheduler()::store()->query_action( ' . var_export( $params, true ) . ' )' );
$store = \ActionScheduler::store();
$action_id = $store->query_action( $params );
if ( $action_id ) {
echo $action_id;
return;
}
$params['status'] = \ActionScheduler_Store::STATUS_PENDING;
\WP_CLI::debug( 'ActionScheduler()::store()->query_action( ' . var_export( $params, true ) . ' )' );
$action_id = $store->query_action( $params );
if ( $action_id ) {
echo $action_id;
return;
}
\WP_CLI::warning( 'No matching next action.' );
}
}
