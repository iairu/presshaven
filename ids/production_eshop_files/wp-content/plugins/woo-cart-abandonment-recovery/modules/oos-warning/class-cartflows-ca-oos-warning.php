<?php
/**
 * Out-of-stock (OOS) admin warning emails.
 *
 * Periodically re-scans stored abandoned carts and emails the store admin when a
 * product that was in stock when the cart was captured has since gone out of stock.
 * This is a warn-only feature: recovery emails are unaffected.
 *
 * @package Woocommerce-Cart-Abandonment-Recovery
 * @since   2.2.0
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Exit if accessed directly.
}

/**
 * Class Cartflows_Ca_Oos_Warning.
 *
 * @since 2.2.0
 */
class Cartflows_Ca_Oos_Warning {

	/**
	 * Action Scheduler hook that runs the recurring stock re-scan.
	 *
	 * @var string
	 */
	const SCAN_HOOK = 'cartflows_ca_check_oos_abandoned_products';

	/**
	 * Action Scheduler hook that processes a single chunk of a large scan.
	 *
	 * @var string
	 */
	const BATCH_HOOK = 'cartflows_ca_process_oos_batch';

	/**
	 * Option key for the admin toggle.
	 *
	 * @var string
	 */
	const OPTION_KEY = 'wcf_ca_send_oos_warning_emails_to_admin';

	/**
	 * Transient that accumulates affected carts across batched scan chunks.
	 *
	 * @var string
	 */
	const SCAN_BUFFER = 'wcf_ca_oos_scan_buffer';

	/**
	 * Short-lived lock that coalesces a burst of stock-status changes into one scan.
	 *
	 * @var string
	 */
	const TRIGGER_LOCK = 'wcf_ca_oos_trigger_lock';

	/**
	 * Option that records the provisioned version of the dedupe table.
	 *
	 * @var string
	 */
	const TABLE_VERSION_OPTION = 'wcf_ca_oos_table_version';

	/**
	 * Current dedupe-table schema version. Bump to force a re-provision.
	 *
	 * @var string
	 */
	const TABLE_VERSION = '1.0.0';

	/**
	 * Class instance.
	 *
	 * @access private
	 * @var Cartflows_Ca_Oos_Warning $instance instance.
	 */
	private static $instance;

	/**
	 * Constructor.
	 */
	public function __construct() {
		// Provision the dedupe table on update, without needing a reactivation.
		add_action( 'admin_init', [ $this, 'maybe_create_table' ] );

		// Keep the recurring scan in sync with the admin toggle.
		add_action( 'admin_init', [ $this, 'schedule_oos_check' ] );

		// Action Scheduler fires this hook on the recurring schedule.
		add_action( self::SCAN_HOOK, [ $this, 'run_oos_check' ] );

		// Each chunk of a large scan runs in its own Action Scheduler request.
		add_action( self::BATCH_HOOK, [ $this, 'process_oos_batch' ] );

		// A product going out of stock is the exact event this feature exists to catch.
		// React to it with a near-term scan instead of waiting for the next daily run.
		add_action( 'woocommerce_product_set_stock_status', [ $this, 'trigger_scan_on_stock_change' ], 10, 2 );
		add_action( 'woocommerce_variation_set_stock_status', [ $this, 'trigger_scan_on_stock_change' ], 10, 2 );
	}

	/**
	 * Create the dedupe table if this install has not provisioned it yet.
	 *
	 * New tables are normally created on activation or on a version-bump upgrade.
	 * This self-heal guarantees the table also appears on a plain plugin update
	 * (no reactivation, no version bump): a cheap option read short-circuits once
	 * the table is in place, and create_oos_notifications_table() is itself
	 * idempotent (CREATE TABLE IF NOT EXISTS via dbDelta).
	 *
	 * @return void
	 */
	public function maybe_create_table(): void {

		if ( version_compare( (string) get_option( self::TABLE_VERSION_OPTION, '0' ), self::TABLE_VERSION, '>=' ) ) {
			return;
		}

		if ( get_transient( 'wcf_ca_oos_table_retry' ) ) {
			return;
		}

		if ( ! class_exists( 'Cartflows_Ca_Database' ) ) {
			include_once CARTFLOWS_CA_DIR . 'modules/cart-abandonment/classes/class-cartflows-ca-database.php';
		}

		Cartflows_Ca_Database::get_instance()->create_oos_notifications_table();

		global $wpdb;
		$table  = $wpdb->prefix . CARTFLOWS_CA_OUT_OF_STOCK_NOTIFICATIONS_TABLE;
		$exists = $wpdb->get_var( $wpdb->prepare( 'SHOW TABLES LIKE %s', $table ) ); // phpcs:ignore WordPress.DB.DirectDatabaseQuery.DirectQuery, WordPress.DB.DirectDatabaseQuery.NoCaching

		// Only record success once the table is really present, so a failed
		// create is retried on the next load instead of being marked done.
		if ( ! empty( $exists ) ) {
			update_option( self::TABLE_VERSION_OPTION, self::TABLE_VERSION );
			return;
		}

		set_transient( 'wcf_ca_oos_table_retry', 1, HOUR_IN_SECONDS );
	}

	/**
	 * Initiator.
	 *
	 * @return Cartflows_Ca_Oos_Warning
	 */
	public static function get_instance() {
		if ( ! isset( self::$instance ) ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	/**
	 * Whether the feature is enabled by the admin.
	 *
	 * @return bool
	 */
	public function is_enabled() {
		return 'on' === get_option( self::OPTION_KEY, 'off' );
	}

	/**
	 * Schedule / unschedule the recurring stock re-scan based on the admin toggle.
	 *
	 * Mirrors the lifecycle of the weekly recovery-report email: schedule a recurring
	 * Action Scheduler action when the feature is on, and cancel it when it is off.
	 *
	 * The trigger has to be a background re-scan (not an add-to-cart / checkout check)
	 * because WooCommerce never lets an out-of-stock product be added to a cart — a cart
	 * product can only flip to OOS *after* the cart was captured, once other shoppers buy
	 * the remaining stock. Only a scheduled re-evaluation can observe that state change.
	 *
	 * @return void
	 */
	public function schedule_oos_check(): void {

		// Action Scheduler ships with WooCommerce; bail safely if it is unavailable.
		if ( ! function_exists( 'as_schedule_recurring_action' ) || ! function_exists( 'as_next_scheduled_action' ) ) {
			return;
		}

		$is_scheduled = as_next_scheduled_action( self::SCAN_HOOK );

		if ( $this->is_enabled() && false === $is_scheduled ) {

			// Default cadence is daily — timely for inventory without flooding the inbox.
			$interval = (int) apply_filters( 'cartflows_ca_oos_check_interval', DAY_IN_SECONDS );

			// Start the first scan on the next tick (not a full interval out) so any
			// backlog of already out-of-stock carts is caught right after enabling.
			as_schedule_recurring_action( time(), $interval, self::SCAN_HOOK );

		} elseif ( ! $this->is_enabled() && false !== $is_scheduled ) {
			as_unschedule_all_actions( self::SCAN_HOOK );

			// Drop any in-flight scan chunks and their accumulated buffer.
			if ( function_exists( 'as_unschedule_all_actions' ) ) {
				as_unschedule_all_actions( self::BATCH_HOOK );
			}
			delete_transient( self::SCAN_BUFFER );
			delete_transient( self::TRIGGER_LOCK );
		}
	}

	/**
	 * Enqueue a near-term scan when a product's stock status flips to out of stock.
	 *
	 * The daily scan alone leaves a product that goes out of stock *after* its cart was
	 * abandoned unreported for up to a day. Reacting to the stock-change event closes that
	 * gap. A short transient lock coalesces bursts (bulk stock edits, a wave of orders)
	 * into a single async scan so the admin inbox is not flooded; the scan itself still
	 * dedupes per cart/product, so nothing is reported twice.
	 *
	 * @param int    $product_id Product or variation id whose stock changed (unused; the scan covers all carts).
	 * @param string $status     New stock status ( e.g. 'instock', 'outofstock', 'onbackorder' ).
	 * @return void
	 */
	public function trigger_scan_on_stock_change( $product_id, $status ): void {

		if ( 'outofstock' !== $status || ! $this->is_enabled() ) {
			return;
		}

		// Action Scheduler ships with WooCommerce; bail safely if it is unavailable.
		if ( ! function_exists( 'as_enqueue_async_action' ) ) {
			return;
		}

		// Coalesce a burst of stock changes into a single near-term scan.
		if ( get_transient( self::TRIGGER_LOCK ) ) {
			return;
		}

		$ttl = (int) apply_filters( 'cartflows_ca_oos_trigger_lock_ttl', 5 * MINUTE_IN_SECONDS );
		set_transient( self::TRIGGER_LOCK, 1, $ttl );

		as_enqueue_async_action( self::SCAN_HOOK );
	}

	/**
	 * Action Scheduler callback: kick off a fresh, batched scan of abandoned carts.
	 *
	 * The scan is chunked (see process_oos_batch) so a store with a very large
	 * abandoned-cart table cannot time out a single Action Scheduler run. This
	 * recurring callback only resets state and processes the first chunk.
	 *
	 * @return void
	 */
	public function run_oos_check(): void {

		// Master kill-switch + toggle guard.
		if ( ! $this->is_enabled() || ! apply_filters( 'cartflows_ca_send_oos_warning_email', true ) ) {
			return;
		}

		if ( empty( $this->get_recipients() ) ) {
			return;
		}

		// Defensive: a scan can run in a cron context before any admin_init.
		$this->maybe_create_table();

		// Without the dedupe table every scan would resend the same alerts.
		if ( version_compare( (string) get_option( self::TABLE_VERSION_OPTION, '0' ), self::TABLE_VERSION, '<' ) ) {
			return;
		}

		// Start a new scan from the top; clear any buffer left by an aborted run.
		delete_transient( self::SCAN_BUFFER );

		$this->process_oos_batch( 0 );
	}

	/**
	 * Process one chunk of the abandoned-cart scan, then continue or finalize.
	 *
	 * Each chunk reads a bounded LIMIT/OFFSET window, appends any newly
	 * out-of-stock carts to the scan buffer, and — if the window was full —
	 * enqueues the next chunk as its own asynchronous Action Scheduler action.
	 * The last (partial) chunk finalizes: one digest email, then dedupe rows.
	 *
	 * @param int $offset Row offset to start this chunk at.
	 * @return void
	 */
	public function process_oos_batch( $offset = 0 ): void {

		// The toggle may have been switched off between chunks.
		if ( ! $this->is_enabled() ) {
			delete_transient( self::SCAN_BUFFER );
			return;
		}

		$offset     = max( 0, (int) $offset );
		$batch_size = max( 1, (int) apply_filters( 'cartflows_ca_oos_scan_batch_size', 200 ) );

		$carts    = $this->query_abandoned_carts( $batch_size, $offset );
		$scanned  = count( $carts );
		$affected = $this->build_affected_from_rows( $carts );

		if ( ! empty( $affected ) ) {
			$buffer = get_transient( self::SCAN_BUFFER );
			$buffer = is_array( $buffer ) ? $buffer : [];
			set_transient( self::SCAN_BUFFER, array_merge( $buffer, $affected ), DAY_IN_SECONDS );
		}

		// A full window means more rows may remain — hand the next chunk to its
		// own Action Scheduler request so no single run grows without bound.
		if ( $scanned >= $batch_size && function_exists( 'as_enqueue_async_action' ) ) {
			as_enqueue_async_action( self::BATCH_HOOK, [ $offset + $batch_size ] );
			return;
		}

		$this->finalize_scan();
	}

	/**
	 * Send the accumulated digest once every chunk has been scanned.
	 *
	 * @return void
	 */
	private function finalize_scan(): void {

		$affected_carts = get_transient( self::SCAN_BUFFER );
		delete_transient( self::SCAN_BUFFER );

		if ( empty( $affected_carts ) || ! is_array( $affected_carts ) ) {
			// Nothing went out of stock since the last scan — no email is sent.
			return;
		}

		$recipients = $this->get_recipients();

		if ( empty( $recipients ) ) {
			return;
		}

		$sent = $this->send_warning_email( $affected_carts, $recipients );

		// Only record the dedupe rows once the admin has actually been notified.
		if ( $sent ) {
			foreach ( $affected_carts as $entry ) {
				$this->mark_notified( $entry['session_id'], wp_list_pluck( $entry['items'], 'id' ) );
			}
		}
	}

	/**
	 * Fetch a bounded page of abandoned-cart rows, oldest first.
	 *
	 * @param int $limit  Maximum rows to return; 0 returns all (legacy behaviour).
	 * @param int $offset Row offset to start at.
	 * @return array<int, object> Raw abandonment rows.
	 */
	public function query_abandoned_carts( $limit = 0, $offset = 0 ) {

		global $wpdb;

		$limit  = max( 0, (int) $limit );
		$offset = max( 0, (int) $offset );

		// Only abandoned carts are relevant; normal/completed/lost carts are out of scope.
		// Ordered by id so LIMIT/OFFSET paging is stable across chunks.
		if ( $limit > 0 ) {
			return $wpdb->get_results( // phpcs:ignore WordPress.DB.DirectDatabaseQuery.DirectQuery, WordPress.DB.DirectDatabaseQuery.NoCaching
				$wpdb->prepare(
					"SELECT id, session_id, email, cart_contents, other_fields, time FROM {$wpdb->prefix}cartflows_ca_cart_abandonment WHERE order_status = %s ORDER BY id ASC LIMIT %d OFFSET %d", // phpcs:ignore WordPress.DB.PreparedSQL.InterpolatedNotPrepared
					WCF_CART_ABANDONED_ORDER,
					$limit,
					$offset
				)
			);
		}

		return $wpdb->get_results( // phpcs:ignore WordPress.DB.DirectDatabaseQuery.DirectQuery, WordPress.DB.DirectDatabaseQuery.NoCaching
			$wpdb->prepare(
				"SELECT id, session_id, email, cart_contents, other_fields, time FROM {$wpdb->prefix}cartflows_ca_cart_abandonment WHERE order_status = %s ORDER BY id ASC", // phpcs:ignore WordPress.DB.PreparedSQL.InterpolatedNotPrepared
				WCF_CART_ABANDONED_ORDER
			)
		);
	}

	/**
	 * Build the list of abandoned carts that contain newly out-of-stock products.
	 *
	 * Scans the whole abandoned-cart table in one pass. The batched scan path
	 * uses query_abandoned_carts() + build_affected_from_rows() instead; this
	 * no-argument method is kept for direct/programmatic callers and tests.
	 *
	 * @return array<int, array<string, mixed>> List of carts, each with its fresh OOS items.
	 */
	public function get_affected_carts() {
		return $this->build_affected_from_rows( $this->query_abandoned_carts() );
	}

	/**
	 * Reduce raw abandonment rows to the carts with fresh out-of-stock products.
	 *
	 * @param array<int, object> $carts Raw abandonment rows.
	 * @return array<int, array<string, mixed>>
	 */
	public function build_affected_from_rows( $carts ) {

		if ( empty( $carts ) ) {
			return [];
		}

		$affected = [];

		foreach ( $carts as $cart ) {

			$oos_items = $this->get_out_of_stock_items( $cart->cart_contents );

			if ( empty( $oos_items ) ) {
				continue;
			}

			// Drop products we have already warned about for this cart (dedupe).
			$already_notified = $this->get_notified_product_ids( $cart->session_id );

			$fresh_items = array_filter(
				$oos_items,
				static function( $item ) use ( $already_notified ) {
					return ! in_array( (string) $item['id'], $already_notified, true );
				}
			);

			if ( empty( $fresh_items ) ) {
				continue;
			}

			$affected[] = [
				'session_id'    => $cart->session_id,
				'email'         => $cart->email,
				'customer_name' => $this->get_customer_name( $cart->other_fields, $cart->email ),
				'abandoned_on'  => $cart->time,
				'items'         => array_values( $fresh_items ),
			];
		}

		return $affected;
	}

	/**
	 * Resolve the out-of-stock products inside a serialized cart.
	 *
	 * Reuses the variation-aware id resolution used by the recovery-email product block:
	 * a variation has its own stock, so check the variation id when present, else the parent.
	 *
	 * @param string $cart_contents Serialized cart contents from the abandonment row.
	 * @return array<int, array<string, mixed>>
	 */
	public function get_out_of_stock_items( $cart_contents ) {

		$cart_items = maybe_unserialize( $cart_contents );

		if ( ! is_array( $cart_items ) ) {
			return [];
		}

		$items = [];

		foreach ( $cart_items as $cart_item ) {

			if ( ! is_array( $cart_item ) || ! isset( $cart_item['product_id'] ) ) {
				continue;
			}

			$variation_id = isset( $cart_item['variation_id'] ) ? (int) $cart_item['variation_id'] : 0;
			$id           = 0 !== $variation_id ? $variation_id : (int) $cart_item['product_id'];

			$product = wc_get_product( $id );

			if ( ! $product ) {
				continue;
			}

			// Let developers override what "out of stock" means (e.g. treat low stock as OOS).
			$is_oos = (bool) apply_filters( 'cartflows_ca_oos_is_product_out_of_stock', ! $product->is_in_stock(), $product, $cart_item );

			if ( ! $is_oos ) {
				continue;
			}

			$quantity   = isset( $cart_item['quantity'] ) ? (int) $cart_item['quantity'] : 1;
			$line_total = isset( $cart_item['line_total'] ) ? (float) $cart_item['line_total'] : 0;

			$items[] = [
				'id'       => $id,
				'name'     => $product->get_name(),
				'quantity' => $quantity,
				'price'    => wc_price( $line_total ),
			];
		}

		return $items;
	}

	/**
	 * Fetch the product ids already notified for a given abandoned cart.
	 *
	 * @param string $session_id Abandoned cart session id.
	 * @return string[] Product ids as strings.
	 */
	public function get_notified_product_ids( $session_id ) {

		global $wpdb;

		$product_ids = $wpdb->get_col( // phpcs:ignore WordPress.DB.DirectDatabaseQuery.DirectQuery, WordPress.DB.DirectDatabaseQuery.NoCaching
			$wpdb->prepare(
				"SELECT product_id FROM {$wpdb->prefix}cartflows_ca_out_of_stock_notifications WHERE ca_session_id = %s", // phpcs:ignore WordPress.DB.PreparedSQL.InterpolatedNotPrepared
				$session_id
			)
		);

		return array_map( 'strval', (array) $product_ids );
	}

	/**
	 * Record that the admin has been warned about specific products in a cart.
	 *
	 * Uses INSERT IGNORE against the UNIQUE (ca_session_id, product_id) key so a concurrent
	 * scan can never create a duplicate row — the dedupe guarantee is enforced by the schema.
	 *
	 * @param string $session_id  Abandoned cart session id.
	 * @param int[]  $product_ids Product ids that were reported as out of stock.
	 * @return void
	 */
	public function mark_notified( $session_id, $product_ids ): void {

		global $wpdb;

		$now = current_time( 'mysql' );

		foreach ( array_unique( $product_ids ) as $product_id ) {
			$wpdb->query( // phpcs:ignore WordPress.DB.DirectDatabaseQuery.DirectQuery, WordPress.DB.DirectDatabaseQuery.NoCaching
				$wpdb->prepare(
					"INSERT IGNORE INTO {$wpdb->prefix}cartflows_ca_out_of_stock_notifications ( ca_session_id, product_id, notified_time ) VALUES ( %s, %d, %s )", // phpcs:ignore WordPress.DB.PreparedSQL.InterpolatedNotPrepared
					$session_id,
					(int) $product_id,
					$now
				)
			);
		}
	}

	/**
	 * Derive a display name for the cart's customer.
	 *
	 * Resolution order: the stored billing/shipping name → a registered WordPress user
	 * matching the cart email → a "(Guest User)" fallback when nothing else is known.
	 *
	 * @param string $other_fields Serialized other_fields column from the abandonment row.
	 * @param string $email        Cart email, used to look up a registered user as a fallback.
	 * @return string
	 */
	public function get_customer_name( $other_fields, $email = '' ) {

		$fields = maybe_unserialize( $other_fields );

		$first = '';
		$last  = '';

		if ( is_array( $fields ) ) {
			if ( ! empty( $fields['wcf_first_name'] ) ) {
				$first = $fields['wcf_first_name'];
			} elseif ( ! empty( $fields['wcf_shipping_first_name'] ) ) {
				$first = $fields['wcf_shipping_first_name'];
			}

			if ( ! empty( $fields['wcf_last_name'] ) ) {
				$last = $fields['wcf_last_name'];
			} elseif ( ! empty( $fields['wcf_shipping_last_name'] ) ) {
				$last = $fields['wcf_shipping_last_name'];
			}
		}

		$name = trim( $first . ' ' . $last );

		if ( '' !== $name ) {
			return ucwords( $name );
		}

		// No billing/shipping name — fall back to a registered user with this email, if any.
		if ( ! empty( $email ) ) {
			$user = get_user_by( 'email', $email );
			if ( $user instanceof WP_User && '' !== trim( $user->display_name ) ) {
				return $user->display_name;
			}
		}

		return __( '(Guest User)', 'woo-cart-abandonment-recovery' );
	}

	/**
	 * Resolve the recipient list for the warning email.
	 *
	 * Reuses the existing recovery-report admin email option (newline separated),
	 * falling back to the site admin email.
	 *
	 * @return string[]
	 */
	public function get_recipients() {

		$admin_emails = get_option( 'wcf_ca_admin_email', get_option( 'admin_email' ) );

		$recipients = is_string( $admin_emails ) ? preg_split( "/[\f\r\n]+/", $admin_emails ) : (array) $admin_emails;

		$recipients = array_filter( array_map( 'sanitize_email', (array) $recipients ) );

		return (array) apply_filters( 'cartflows_ca_oos_warning_recipients', $recipients );
	}

	/**
	 * Build and send the digest warning email to each recipient.
	 *
	 * @param array<int, array<string, mixed>> $affected_carts Affected carts with their OOS items.
	 * @param string[]                         $recipients     Recipient email addresses.
	 * @return bool True if at least one email was dispatched.
	 */
	public function send_warning_email( $affected_carts, $recipients ) {

		$subject = (string) apply_filters(
			'cartflows_ca_oos_warning_email_subject',
			__( 'Out-of-stock alert: products in abandoned carts need attention', 'woo-cart-abandonment-recovery' ),
			$affected_carts
		);

		$body = (string) apply_filters(
			'cartflows_ca_oos_warning_email_content',
			$this->get_email_content( $affected_carts ),
			$affected_carts
		);

		$headers  = 'From: ' . get_bloginfo( 'name' ) . ' <' . get_option( 'admin_email' ) . '>' . "\r\n";
		$headers .= 'Content-Type: text/html; charset=UTF-8' . "\r\n";

		// Force the HTML content type for this send. The header alone is not enough:
		// wp_mail() applies the wp_mail_content_type filter last, so another plugin that
		// sets that filter globally to text/plain would otherwise strip the styling and
		// deliver the raw markup as plain text.
		add_filter( 'wp_mail_content_type', [ $this, 'set_html_content_type' ], PHP_INT_MAX );

		$sent = false;

		foreach ( $recipients as $recipient ) {
			// Ignoring the rule as third-party SMTP plugins override wp_mail and use their own mailing system.
			$dispatched = wp_mail( $recipient, $subject, stripslashes( $body ), $headers ); // phpcs:ignore WordPressVIPMinimum.Functions.RestrictedFunctions.wp_mail_wp_mail

			$sent = $sent || $dispatched;
		}

		// Restore the previous behaviour so we never affect other emails in this request.
		remove_filter( 'wp_mail_content_type', [ $this, 'set_html_content_type' ], PHP_INT_MAX );

		return $sent;
	}

	/**
	 * Force the HTML content type for the warning email send.
	 *
	 * @return string
	 */
	public function set_html_content_type() {
		return 'text/html';
	}

	/**
	 * Render the warning email body from the template.
	 *
	 * @param array<int, array<string, mixed>> $affected_carts Affected carts with their OOS items.
	 * @return string
	 */
	public function get_email_content( $affected_carts ) {

		$store_name     = get_bloginfo( 'name' );
		$store_url      = home_url( '/' );
		$dashboard_link = admin_url( 'admin.php?page=woo-cart-abandonment-recovery' );

		// Keep the digest short: render a capped list of carts and point the rest to the dashboard.
		// Without this, a store with dozens of affected carts would produce an unreadably long email.
		$max_carts = (int) apply_filters( 'cartflows_ca_oos_warning_max_carts', 10, $affected_carts );
		$max_carts = max( 1, $max_carts );

		$total_carts = count( $affected_carts );

		// Distinct products across every affected cart, for the summary line.
		$product_ids    = [];
		$affected_carts = array_values( $affected_carts );
		foreach ( $affected_carts as $cart ) {
			$items = isset( $cart['items'] ) && is_array( $cart['items'] ) ? $cart['items'] : [];
			foreach ( $items as $item ) {
				if ( isset( $item['id'] ) ) {
					$product_ids[ (string) $item['id'] ] = true;
				}
			}
		}
		$total_products = count( $product_ids );

		$display_carts   = array_slice( $affected_carts, 0, $max_carts );
		$remaining_carts = max( 0, $total_carts - count( $display_carts ) );

		ob_start();
		include CARTFLOWS_CA_DIR . 'modules/oos-warning/templates/email-body.php';
		return (string) ob_get_clean();
	}
}

Cartflows_Ca_Oos_Warning::get_instance();
