<?php
/**
 * Woocommerce Cart Abandonment Recovery
 * Unscheduling the events.
 *
 * @package Woocommerce-Cart-Abandonment-Recovery
 */

if ( ! defined( 'WP_UNINSTALL_PLUGIN' ) ) {
	exit;
}

global $wpdb;

wp_clear_scheduled_hook( 'cartflows_ca_update_order_status_action' );

// Also cancel the Action Scheduler copy of the same job when available.
if ( function_exists( 'as_unschedule_all_actions' ) ) {
	as_unschedule_all_actions( 'cartflows_ca_update_order_status_action' );
}

$delete_data = get_option( 'wcf_ca_delete_plugin_data' );

if ( 'on' === $delete_data ) {

	$options = [
		'wcf_ca_status',
		'wcf_ca_gdpr_status',
		'wcf_ca_coupon_code_status',
		'wcf_ca_zapier_tracking_status',
		'wcf_ca_cut_off_time',
		'wcf_ca_cron_run_time',
		'wcf_ca_scheduler_engine',
		'wcf_ca_scheduled_interval',
		'wcf_ca_from_name',
		'wcf_ca_from_email',
		'wcf_ca_reply_email',
		'wcf_ca_discount_type',
		'wcf_ca_coupon_amount',
		'wcf_ca_zapier_cart_abandoned_webhook',
		'wcf_ca_gdpr_message',
		'wcf_ca_coupon_expiry',
		'wcf_ca_coupon_expiry_unit',
		'wcf_ca_excludes_orders',
		'wcf_ca_delete_plugin_data',
		'wcf_ca_version',
		'wcf_ca_send_recovery_report_emails_to_admin',
		'wcf_ca_admin_email',
		'wcf_ca_oos_table_version',
		'_transient_wcf_ca_table_creation_retry',
		'_transient_timeout_wcf_ca_table_creation_retry',
		'_transient_wcf_ca_oos_table_retry',
		'_transient_timeout_wcf_ca_oos_table_retry',
	];

	// Delete all options data.
	foreach ( $options as $index => $key ) {
		delete_option( $key );
	}
	//phpcs:disable WordPress.DB.DirectDatabaseQuery
	// Ignoring the direct query rule as we are dropping only our custom tables if exist.
	$wpdb->get_results( "DROP TABLE IF EXISTS {$wpdb->prefix}cartflows_ca_email_templates_meta" );

	$wpdb->get_results( "DROP TABLE IF EXISTS {$wpdb->prefix}cartflows_ca_email_history" );

	// Has a FOREIGN KEY on cart_abandonment, so drop it first.
	$wpdb->get_results( "DROP TABLE IF EXISTS {$wpdb->prefix}cartflows_ca_out_of_stock_notifications" );

	$wpdb->get_results( "DROP TABLE IF EXISTS {$wpdb->prefix}cartflows_ca_email_templates" );

	$wpdb->get_results( "DROP TABLE IF EXISTS {$wpdb->prefix}cartflows_ca_cart_abandonment" );
	//phpcs:disable WordPress.DB.DirectDatabaseQuery
}
