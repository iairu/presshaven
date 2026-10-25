<?php
/**
 * Cart Abandonment
 *
 * @package Woocommerce-Cart-Abandonment-Recovery
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Exit if accessed directly.
}

/**
 * Cart abandonment tracking class.
 *
 * Thin scheduler for the recurring "mark carts abandoned + schedule follow-up
 * emails" job. Defaults to WP-Cron for backward compatibility, and uses Action
 * Scheduler when the admin opts in or when WP-Cron is disabled at the site level
 * (DISABLE_WP_CRON) so the job still fires reliably. The fired hook name is
 * unchanged, so the handler in Cartflows_Ca_Tracking stays untouched.
 */
class Cartflows_Ca_Cron {

	/**
	 * The recurring action/event hook name shared by both engines.
	 */
	const HOOK = 'cartflows_ca_update_order_status_action';

	/**
	 * Custom WP-Cron schedule key used by the fallback engine.
	 */
	const SCHEDULE_KEY = 'wcf_ca_update_order_status_interval';

	/**
	 * Action Scheduler group, so admins can find the job under
	 * WooCommerce -> Status -> Scheduled Actions.
	 */
	const AS_GROUP = 'cartflows-ca';

	/**
	 * Option that records the interval (in seconds) the Action Scheduler job was
	 * last scheduled with, so a filter-only interval change can be detected.
	 */
	const INTERVAL_OPTION = 'wcf_ca_scheduled_interval';

	/**
	 * Member Variable
	 *
	 * @var object instance
	 */
	private static $instance;

	/**
	 *  Constructor function that initializes required actions and hooks.
	 */
	public function __construct() {

		// Register the WP-Cron interval so the fallback engine can use it.
		add_filter( 'cron_schedules', [ $this, 'add_cron_interval' ] ); //phpcs:ignore WordPress.WP.CronInterval.ChangeDetected

		// Schedule on wp_loaded (front + admin + ajax) so Action Scheduler is loaded and the job self-heals on the next request after activation/upgrade.
		add_action( 'wp_loaded', [ $this, 'maybe_schedule' ] );

		// Re-schedule when the interval or engine option changes.
		add_action( 'add_option_wcf_ca_cron_run_time', [ $this, 'reschedule' ] );
		add_action( 'update_option_wcf_ca_cron_run_time', [ $this, 'reschedule' ] );
		add_action( 'add_option_wcf_ca_scheduler_engine', [ $this, 'reschedule' ] );
		add_action( 'update_option_wcf_ca_scheduler_engine', [ $this, 'reschedule' ] );

		// Nudge admins running WP-Cron with DISABLE_WP_CRON towards Action Scheduler.
		add_action( 'admin_notices', [ $this, 'maybe_show_disable_wp_cron_notice' ] );
	}

	/**
	 *  Initiator
	 */
	public static function get_instance() {
		if ( ! isset( self::$instance ) ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	/**
	 * Get the effective scheduler engine.
	 *
	 * WP-Cron is the default, so an existing site with a working WP-Cron keeps
	 * running on WP-Cron and is never silently migrated. Action Scheduler is used
	 * when the admin explicitly opts in, or - critically - when WP-Cron cannot
	 * self-trigger (DISABLE_WP_CRON), which is exactly the environment WP-Cron
	 * drifts in. If Action Scheduler is unavailable we always degrade to WP-Cron
	 * so the job is never dropped.
	 *
	 * @return string 'action_scheduler' or 'wp_cron'.
	 */
	private function get_engine() {

		$engine = get_option( 'wcf_ca_scheduler_engine', 'wp_cron' );

		// Explicit opt-in to Action Scheduler wins when it is available.
		if ( 'action_scheduler' === $engine ) {
			return $this->as_available() ? 'action_scheduler' : 'wp_cron';
		}

		// Default (WP-Cron): auto-fall back to Action Scheduler when WP-Cron is
		// disabled at the site level and Action Scheduler can take over.
		if ( defined( 'DISABLE_WP_CRON' ) && DISABLE_WP_CRON && $this->as_available() ) {
			return 'action_scheduler';
		}

		return 'wp_cron';
	}

	/**
	 * Get the recurrence interval in seconds.
	 *
	 * Honors the existing wcf_ca_cron_run_time option and the
	 * woo_ca_update_order_cron_interval filter used by power users.
	 *
	 * @return int Interval in seconds (at least one minute).
	 */
	private function get_interval() {
		$cron_time = apply_filters( 'woo_ca_update_order_cron_interval', get_option( 'wcf_ca_cron_run_time', 20 ) );
		return max( 1, intval( $cron_time ) ) * MINUTE_IN_SECONDS;
	}

	/**
	 * Whether Action Scheduler is available at runtime.
	 *
	 * @return bool
	 */
	private function as_available() {
		return function_exists( 'as_schedule_recurring_action' ) && function_exists( 'as_next_scheduled_action' ) && function_exists( 'as_unschedule_all_actions' );
	}

	/**
	 * Ensure the recurring job is scheduled on the chosen engine.
	 *
	 * Idempotent and safe to run on every request.
	 */
	public function maybe_schedule(): void {

		$interval = $this->get_interval();

		if ( 'action_scheduler' === $this->get_engine() && $this->as_available() ) {

			// Drop the legacy WP-Cron event when switching to Action Scheduler.
			if ( wp_next_scheduled( self::HOOK ) ) {
				wp_clear_scheduled_hook( self::HOOK );
			}

			$scheduled_interval = get_option( self::INTERVAL_OPTION, 0 );
			$scheduled_interval = is_numeric( $scheduled_interval ) ? (int) $scheduled_interval : 0;

			// Reschedule when not yet scheduled, or when the interval drifted - e.g. the
			// woo_ca_update_order_cron_interval filter changed without an option write.
			// Action Scheduler bakes the interval in at schedule time, unlike WP-Cron.
			if ( false === as_next_scheduled_action( self::HOOK ) || $scheduled_interval !== $interval ) {
				as_unschedule_all_actions( self::HOOK );
				// Start one interval out so a settings save does not trigger an immediate run.
				as_schedule_recurring_action( time() + $interval, $interval, self::HOOK, [], self::AS_GROUP );
				update_option( self::INTERVAL_OPTION, $interval, false );
			}

			return;
		}

		// WP-Cron path: explicit fallback, or Action Scheduler unavailable so the job is never silently dropped.
		// WP-Cron re-derives the interval from the cron_schedules filter each cycle, so no drift tracking is needed here.
		if ( $this->as_available() && false !== as_next_scheduled_action( self::HOOK ) ) {
			as_unschedule_all_actions( self::HOOK );
		}

		if ( ! wp_next_scheduled( self::HOOK ) ) {
			wp_schedule_event( time(), self::SCHEDULE_KEY, self::HOOK );
		}
	}

	/**
	 * Clear the job on both engines and re-schedule with the current settings.
	 *
	 * Hooked to the interval/engine option changes; WP-Cron does not otherwise
	 * pick up a new interval for an already-scheduled event.
	 */
	public function reschedule(): void {

		if ( wp_next_scheduled( self::HOOK ) ) {
			wp_clear_scheduled_hook( self::HOOK );
		}

		if ( $this->as_available() ) {
			as_unschedule_all_actions( self::HOOK );
		}

		$this->maybe_schedule();
	}

	/**
	 * Register the custom WP-Cron interval used by the fallback engine.
	 *
	 * @param array<string, array{interval:int, display:string}> $schedules schedules.
	 * @return array<string, array{interval:int, display:string}>
	 */
	public function add_cron_interval( $schedules ) {

		$schedules[ self::SCHEDULE_KEY ] = [
			'interval' => $this->get_interval(),
			'display'  => __( 'Cart Abandonment Recovery order-status interval', 'woo-cart-abandonment-recovery' ),
		];

		return $schedules;
	}

	/**
	 * Surface the scheduler status on the plugin page when WP-Cron is disabled.
	 *
	 * With DISABLE_WP_CRON set we either auto-fell back to Action Scheduler (show
	 * an informational notice so the behaviour is transparent) or, if Action
	 * Scheduler is unavailable, we are stuck on a WP-Cron that cannot self-trigger
	 * (show a warning that recovery emails may be delayed).
	 */
	public function maybe_show_disable_wp_cron_notice(): void {

		if ( ! current_user_can( 'manage_woocommerce' ) ) {
			return;
		}

		// Only relevant when WP-Cron cannot self-trigger.
		if ( ! ( defined( 'DISABLE_WP_CRON' ) && DISABLE_WP_CRON ) ) {
			return;
		}

		$plugin_page = defined( 'WCF_CA_PAGE_NAME' ) ? WCF_CA_PAGE_NAME : 'woo-cart-abandonment-recovery';
		$page        = Cartflows_Ca_Helper::get_instance()->sanitize_text_filter( 'page', 'GET' );

		if ( $plugin_page !== $page ) {
			return;
		}

		// WP-Cron is disabled and Action Scheduler is unavailable: the job has no reliable runner.
		if ( 'wp_cron' === $this->get_engine() ) {
			printf(
				'<div class="notice notice-warning is-dismissible"><p>%s</p></div>',
				esc_html__( 'Cart Abandonment Recovery relies on WP-Cron, but WP-Cron is disabled on this site (DISABLE_WP_CRON) and Action Scheduler is unavailable. Recovery emails may be delayed until a background scheduler is available.', 'woo-cart-abandonment-recovery' )
			);
			return;
		}

		// WP-Cron is disabled but we auto-switched to Action Scheduler; only surface this when the admin did not explicitly opt in.
		if ( 'action_scheduler' !== get_option( 'wcf_ca_scheduler_engine', 'wp_cron' ) ) {
			printf(
				'<div class="notice notice-info is-dismissible"><p>%s</p></div>',
				esc_html__( 'WP-Cron is disabled on this site (DISABLE_WP_CRON), so Cart Abandonment Recovery is automatically using Action Scheduler to keep recovery emails on time. You can change this under the "Background task scheduler" setting.', 'woo-cart-abandonment-recovery' )
			);
		}
	}
}

Cartflows_Ca_Cron::get_instance();
