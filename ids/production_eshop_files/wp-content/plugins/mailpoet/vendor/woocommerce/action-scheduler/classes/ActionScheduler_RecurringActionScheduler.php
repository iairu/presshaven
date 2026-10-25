<?php
if (!defined('ABSPATH')) exit;
class ActionScheduler_RecurringActionScheduler {
private const RUN_SCHEDULED_RECURRING_ACTIONS_HOOK = 'action_scheduler_run_recurring_actions_schedule_hook';
public function init(): void {
add_action( self::RUN_SCHEDULED_RECURRING_ACTIONS_HOOK, array( $this, 'run_recurring_scheduler_hook' ) );
if ( is_admin() && ( ! defined( 'DOING_AJAX' ) || ! DOING_AJAX ) ) {
add_action( 'action_scheduler_init', array( $this, 'schedule_recurring_scheduler_hook' ) );
}
}
public function schedule_recurring_scheduler_hook(): void {
if ( false === wp_cache_get( 'as_is_ensure_recurring_actions_scheduled' ) ) {
if ( ! as_has_scheduled_action( self::RUN_SCHEDULED_RECURRING_ACTIONS_HOOK ) ) {
as_schedule_recurring_action(
time(),
DAY_IN_SECONDS,
self::RUN_SCHEDULED_RECURRING_ACTIONS_HOOK,
[],
'ActionScheduler',
true,
20
);
}
wp_cache_set( 'as_is_ensure_recurring_actions_scheduled', true, HOUR_IN_SECONDS );
}
}
public function run_recurring_scheduler_hook(): void {
do_action( 'action_scheduler_ensure_recurring_actions' );
}
}
