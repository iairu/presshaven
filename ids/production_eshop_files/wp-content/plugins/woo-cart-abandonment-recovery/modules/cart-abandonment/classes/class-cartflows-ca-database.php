<?php
/**
 * Cart Abandonment DB
 *
 * @package Woocommerce-Cart-Abandonment-Recovery
 * @since   1.0.0
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Exit if accessed directly.
}

/**
 * Cart Abandonment DB class
 *
 * @since 1.0.0
 */
class Cartflows_Ca_Database {
	/**
	 * Member Variable
	 *
	 * @var object instance
	 */
	private static $instance;

	/**
	 * Parent charset/collate clause, keyed by table name.
	 *
	 * @var array<string, string>
	 */
	private static $parent_charset_collate = [];

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
	 *  Create tables
	 */
	public function create_tables(): void {
		$this->create_cart_abandonment_table();
		$this->create_cart_abandonment_template_table();
		$this->create_email_templates_meta_table();
		$this->create_email_history_table();
		$this->create_oos_notifications_table();
		$this->check_if_all_table_created();
	}

	/**
	 *  Check if tables created.
	 */
	public function check_if_all_table_created(): void {

		global $wpdb;

		$required_tables = [
			CARTFLOWS_CA_CART_ABANDONMENT_TABLE,
			CARTFLOWS_CA_EMAIL_TEMPLATE_TABLE,
			CARTFLOWS_CA_EMAIL_HISTORY_TABLE,
			CARTFLOWS_CA_EMAIL_TEMPLATE_META_TABLE,
		];

		delete_option( 'wcf_ca_all_db_tables_created' );

		foreach ( $required_tables as $table ) {
			$is_table_exist = $wpdb->get_var( $wpdb->prepare( 'SHOW TABLES LIKE %s', $wpdb->prefix . $table ) ); // db call ok; no-cache ok.
			if ( empty( $is_table_exist ) ) {
				update_option( 'wcf_ca_all_db_tables_created', 'no' );
				break;
			}
		}
	}
	/**
	 *  Create Email templates meta table.
	 */
	public function create_email_templates_meta_table(): void {
		global $wpdb;

		$wpdb->hide_errors();

		$email_template_meta_db       = $wpdb->prefix . CARTFLOWS_CA_EMAIL_TEMPLATE_META_TABLE;
		$cart_abandonment_template_db = $wpdb->prefix . CARTFLOWS_CA_EMAIL_TEMPLATE_TABLE;
		$charset_collate              = $wpdb->get_charset_collate();

		// Email templates meta table db sql command.
		$sql = "CREATE TABLE IF NOT EXISTS {$email_template_meta_db} (
		`id` BIGINT(20) NOT NULL AUTO_INCREMENT,
		`email_template_id` BIGINT(20) NOT NULL,
		`meta_key` varchar(255) NOT NULL,
		`meta_value` longtext NOT NULL,
		PRIMARY KEY (`id`),
		FOREIGN KEY ( `email_template_id` )  REFERENCES {$cart_abandonment_template_db}(`id`) ON DELETE CASCADE
		) {$charset_collate};\n";

		include_once ABSPATH . 'wp-admin/includes/upgrade.php';
		dbDelta( $sql );
	}

	/**
	 *  Create tables for analytics.
	 */
	public function create_cart_abandonment_table(): void {

		global $wpdb;

		$wpdb->hide_errors();

		$cart_abandonment_db = $wpdb->prefix . CARTFLOWS_CA_CART_ABANDONMENT_TABLE;
		$charset_collate     = $wpdb->get_charset_collate();

		// Cart abandonment tracking db sql command.
		$sql = "CREATE TABLE IF NOT EXISTS {$cart_abandonment_db} (
			id BIGINT(20) NOT NULL AUTO_INCREMENT,
			checkout_id BIGINT(20) UNSIGNED NOT NULL,
			email VARCHAR(100),
			cart_contents LONGTEXT,
			cart_total DECIMAL(10,2),
			session_id VARCHAR(60) NOT NULL,
			other_fields LONGTEXT,
			order_status ENUM( 'normal','abandoned','completed','lost') NOT NULL DEFAULT 'normal',
			unsubscribed  boolean DEFAULT 0,
			coupon_code VARCHAR(50),
   			time DATETIME DEFAULT NULL,
			PRIMARY KEY  (`id`, `session_id`),
			UNIQUE KEY `session_id_UNIQUE` (`session_id`)
		) {$charset_collate};\n";

		include_once ABSPATH . 'wp-admin/includes/upgrade.php';
		dbDelta( $sql );
	}

	/**
	 *  Create tables for analytics.
	 */
	public function create_cart_abandonment_template_table(): void {

		global $wpdb;

		$wpdb->hide_errors();

		$cart_abandonment_template_db = $wpdb->prefix . CARTFLOWS_CA_EMAIL_TEMPLATE_TABLE;

		$charset_collate = $wpdb->get_charset_collate();

		// Cart abandonment tracking db sql command.
		$sql = "CREATE TABLE IF NOT EXISTS {$cart_abandonment_template_db} (
			 `id` BIGINT(20) NOT NULL AUTO_INCREMENT,
             `template_name` text NOT NULL,
             `email_subject` text NOT NULL,
             `email_body` mediumtext NOT NULL,
             `is_activated` tinyint(1) NOT NULL DEFAULT '0',
             `frequency` int(11) NOT NULL,
             `frequency_unit` ENUM( 'MINUTE','HOUR','DAY') NOT NULL DEFAULT 'MINUTE',
             PRIMARY KEY (`id`)
		) {$charset_collate};\n";

		include_once ABSPATH . 'wp-admin/includes/upgrade.php';
		dbDelta( $sql );
	}

	/**
	 *  Create tables for analytics.
	 */
	public function create_email_history_table(): void {

		global $wpdb;

		$wpdb->hide_errors();

		$cart_abandonment_history_db  = $wpdb->prefix . CARTFLOWS_CA_EMAIL_HISTORY_TABLE;
		$cart_abandonment_db          = $wpdb->prefix . CARTFLOWS_CA_CART_ABANDONMENT_TABLE;
		$cart_abandonment_template_db = $wpdb->prefix . CARTFLOWS_CA_EMAIL_TEMPLATE_TABLE;

		$charset_collate = $wpdb->get_charset_collate();

		$sql = "CREATE TABLE IF NOT EXISTS {$cart_abandonment_history_db} (
			 `id` BIGINT(20) NOT NULL AUTO_INCREMENT,
			 `template_id` BIGINT(20) NOT NULL,
			 `ca_session_id` VARCHAR(60),
			 `coupon_code` VARCHAR(50),
			 `scheduled_time` DATETIME,
			 `email_sent` boolean DEFAULT 0,
			  PRIMARY KEY (`id`),
			  FOREIGN KEY ( `template_id` )  REFERENCES {$cart_abandonment_template_db}(`id`) ON DELETE CASCADE,
			  FOREIGN KEY ( `ca_session_id` )  REFERENCES {$cart_abandonment_db}(`session_id`) ON DELETE CASCADE
		) {$charset_collate};\n";

		include_once ABSPATH . 'wp-admin/includes/upgrade.php';
		dbDelta( $sql );
	}

	/**
	 * Create the out-of-stock (OOS) notification de-duplication table.
	 *
	 * Stores cart/product pairs that have already triggered an admin stock alert,
	 * ensuring each abandoned-cart product generates only one notification.
	 *
	 * A dedicated table provides database-level deduplication via a UNIQUE KEY,
	 * automatic cleanup through FK CASCADE, efficient row-based storage, and
	 * isolation from cart tracking data.
	 *
	 * Follows the existing email_history child-table pattern.
	 *
	 * @since 2.2.0
	 */
	public function create_oos_notifications_table(): void {

		global $wpdb;

		$wpdb->hide_errors();

		$oos_notifications_db = $wpdb->prefix . CARTFLOWS_CA_OUT_OF_STOCK_NOTIFICATIONS_TABLE;
		$cart_abandonment_db  = $wpdb->prefix . CARTFLOWS_CA_CART_ABANDONMENT_TABLE;

		// Load first: on its first include, schema.php overwrites $charset_collate with the site default.
		include_once ABSPATH . 'wp-admin/includes/upgrade.php';

		// Must match the parent column, or MySQL rejects the FOREIGN KEY on older installs.
		$charset_collate = $this->get_parent_charset_collate();

		$columns = '
			 `id` BIGINT(20) NOT NULL AUTO_INCREMENT,
			 `ca_session_id` VARCHAR(60) NOT NULL,
			 `product_id` BIGINT(20) NOT NULL,
			 `notified_time` DATETIME DEFAULT NULL,
			  PRIMARY KEY (`id`),
			  UNIQUE KEY `session_product` (`ca_session_id`, `product_id`)';

		// UNIQUE (ca_session_id, product_id) enforces "once per cart per product"; FK CASCADE auto-cleans rows when the parent cart is removed.
		dbDelta(
			"CREATE TABLE IF NOT EXISTS {$oos_notifications_db} ({$columns},
			  FOREIGN KEY ( `ca_session_id` )  REFERENCES {$cart_abandonment_db}(`session_id`) ON DELETE CASCADE
		) {$charset_collate};\n"
		);

		if ( ! empty( $wpdb->get_var( $wpdb->prepare( 'SHOW TABLES LIKE %s', $oos_notifications_db ) ) ) ) { // db call ok; no-cache ok.
			delete_transient( 'wcf_ca_oos_table_retry' );
			return;
		}

		// FOREIGN KEY still refused (e.g. MyISAM parent): create the table without it.
		dbDelta( "CREATE TABLE IF NOT EXISTS {$oos_notifications_db} ({$columns}\n\t\t) {$charset_collate};\n" );
	}

	/**
	 * Charset/collate clause matching cart_abandonment.session_id, falling back to the site default.
	 *
	 * @since 2.2.1
	 *
	 * @return string
	 */
	public function get_parent_charset_collate(): string {
		global $wpdb;

		$cart_abandonment_db = $wpdb->prefix . CARTFLOWS_CA_CART_ABANDONMENT_TABLE;

		if ( isset( self::$parent_charset_collate[ $cart_abandonment_db ] ) ) {
			return self::$parent_charset_collate[ $cart_abandonment_db ];
		}

		$row = $wpdb->get_row( // db call ok; no-cache ok.
			$wpdb->prepare(
				"SELECT CHARACTER_SET_NAME, COLLATION_NAME
				FROM INFORMATION_SCHEMA.COLUMNS
				WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = 'session_id'",
				$cart_abandonment_db
			)
		);

		//phpcs:disable WordPress.NamingConventions.ValidVariableName.UsedPropertyNotSnakeCase
		if ( $row && ! empty( $row->CHARACTER_SET_NAME ) && ! empty( $row->COLLATION_NAME ) ) {
			$charset = preg_replace( '/[^A-Za-z0-9_]/', '', (string) $row->CHARACTER_SET_NAME );
			$collate = preg_replace( '/[^A-Za-z0-9_]/', '', (string) $row->COLLATION_NAME );

			self::$parent_charset_collate[ $cart_abandonment_db ] = "DEFAULT CHARACTER SET {$charset} COLLATE {$collate}";
			return self::$parent_charset_collate[ $cart_abandonment_db ];
		}
		//phpcs:enable WordPress.NamingConventions.ValidVariableName.UsedPropertyNotSnakeCase

		return $wpdb->get_charset_collate();
	}

	/**
	 * Insert initial sample email templates.
	 *
	 * Uses the Cartflows_Ca_Default_Meta class for centralized
	 * template and meta defaults.
	 *
	 * @param bool $force_restore Restore forcefully.
	 * @since 1.0.0 Original method
	 * @since 1.3.3 Refactored to use default meta class
	 */
	public function template_table_seeder( $force_restore = false ): void {
		global $wpdb;
		$cart_abandonment_template_db      = $wpdb->prefix . CARTFLOWS_CA_EMAIL_TEMPLATE_TABLE;
		$cart_abandonment_template_meta_db = $wpdb->prefix . CARTFLOWS_CA_EMAIL_TEMPLATE_META_TABLE;

		// phpcs:disable WordPress.DB.PreparedSQL.InterpolatedNotPrepared
		// Can't use placeholders for table/column names, it will be wrapped by a single quote (') instead of a backquote (`).
		$email_template_count = $wpdb->get_var( "SELECT COUNT(*) FROM {$cart_abandonment_template_db}" ); // db call ok; no-cache ok.

		// Allow skipping default email templates via filter.
		$skip_default_templates = apply_filters( 'cartflows_ca_skip_default_email_templates', false, $force_restore );

		if ( ( ! $email_template_count || $force_restore ) && ! $skip_default_templates ) {

			// Get templates from the centralized default meta class.
			$email_templates = wcf_ca()->options->get_sample_email_templates();
			$meta_defaults   = wcf_ca()->options->get_email_template_meta_defaults();

			$wpdb->hide_errors();

			$template_index      = 1;
			$template_meta_index = 1;

			$is_email_template_table      = $wpdb->get_var( "SHOW TABLES LIKE '{$cart_abandonment_template_db}'" ); // db call ok; no-cache ok.
			$is_email_template_meta_table = $wpdb->get_var( "SHOW TABLES LIKE '{$cart_abandonment_template_meta_db}'" ); // db call ok; no-cache ok.

			if ( ! empty( $is_email_template_table ) && ! empty( $is_email_template_meta_table ) ) {
				foreach ( $email_templates as $email_template ) {
					$wpdb->query(
						$wpdb->prepare(
							"INSERT INTO {$cart_abandonment_template_db} (`id`, `template_name`, `email_subject`, `email_body`, `frequency`, `frequency_unit`)
					VALUES ( %d, %s, %s, %s, %d, %s )",
							$force_restore ? null : $template_index++,
							sanitize_text_field( $email_template['template_name'] ),
							sanitize_text_field( $email_template['subject'] ),
							wp_kses_post( $email_template['body'] ),
							absint( $email_template['frequency'] ),
							sanitize_text_field( $email_template['frequency_unit'] )
						)
					); // db call ok; no-cache ok.

					$email_tmpl_id = $wpdb->insert_id;

					// Use centralized meta defaults.
					foreach ( $meta_defaults as $meta_key => $meta_value ) {
						$wpdb->query(
							$wpdb->prepare(
								"INSERT INTO {$cart_abandonment_template_meta_db} ( `id`, `email_template_id`, `meta_key`, `meta_value` )
							VALUES ( %d, %d, %s, %s )",
								$force_restore ? null : $template_meta_index++,
								$email_tmpl_id,
								sanitize_text_field( $meta_key ),
								sanitize_text_field( $meta_value )
							)
						); // db call ok; no-cache ok.
					}
				}
            	// phpcs:enable WordPress.DB.PreparedSQL.InterpolatedNotPrepared
			}
		}

		/**
		 * Fires after email templates are seeded
		 *
		 * @param bool $force_restore Whether this was a forced restore
		 * @since 1.3.3
		 */
		do_action( 'wcf_ca_email_templates_seeded', $force_restore );
	}
}

Cartflows_Ca_Database::get_instance();
