<?php
/**
 * Follow Up Reports API.
 *
 * @package Woocommerce-Cart-Abandonment-Recovery
 */

namespace WCAR\Admin\Api;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Exit if accessed directly.
}

/**
 * Class FollowUp.
 */
class FollowUp extends ApiBase {
	/**
	 * Route base.
	 *
	 * @var string
	 */
	protected $rest_base = '/admin/follow-up/';

	/**
	 * Rows per page when the request does not say.
	 */
	const DEFAULT_PER_PAGE = 20;

	/**
	 * Most rows one page can hold.
	 */
	const MAX_PER_PAGE = 100;

	/**
	 * Rows loaded and formatted at a time, so an export never holds every full row, or one huge
	 * `IN()` list, in memory at once.
	 */
	const RECORD_CHUNK_SIZE = 500;

	/**
	 * Status filters the screen offers, mapped to the order statuses each one matches.
	 * `lost_orders` also takes `failed`, because both read as "Failed" in the list.
	 */
	const STATUS_FILTERS = [
		'all'              => [],
		'abandoned_orders' => [ WCF_CART_ABANDONED_ORDER ],
		'recovered_orders' => [ WCF_CART_COMPLETED_ORDER ],
		'lost_orders'      => [ WCF_CART_LOST_ORDER, WCF_CART_FAILED_ORDER ],
		'blacklisted'      => [ WCF_CART_BLACKLISTED_ORDER ],
	];

	/**
	 * Instance of the class.
	 *
	 * @var FollowUp
	 */
	private static $instance;

	/**
	 * Initiator.
	 *
	 * @return FollowUp
	 */
	public static function get_instance() {
		if ( ! isset( self::$instance ) ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	/**
	 * Register API routes.
	 */
	public function register_routes(): void {
		register_rest_route(
			$this->get_api_namespace(),
			$this->rest_base,
			[
				[
					'methods'             => \WP_REST_Server::CREATABLE,
					'callback'            => [ $this, 'get_records' ],
					'permission_callback' => [ $this, 'get_permissions_check' ],
					'args'                => [
						'page'      => [
							'type'              => 'integer',
							'default'           => 1,
							'sanitize_callback' => 'absint',
						],
						'per_page'  => [
							'type'              => 'integer',
							'default'           => self::DEFAULT_PER_PAGE,
							'sanitize_callback' => 'absint',
						],
						'search'    => [
							'type'              => 'string',
							'default'           => '',
							'sanitize_callback' => 'sanitize_text_field',
						],
						'status'    => [
							'type'    => 'string',
							'default' => 'all',
							'enum'    => array_keys( self::STATUS_FILTERS ),
						],
						'date_from' => [
							'type'              => 'string',
							'default'           => '',
							'sanitize_callback' => [ $this, 'sanitize_date' ],
						],
						'date_to'   => [
							'type'              => 'string',
							'default'           => '',
							'sanitize_callback' => [ $this, 'sanitize_date' ],
						],
						'export'    => [
							'type'    => 'boolean',
							'default' => false,
						],
					],
				],
			]
		);
	}

	/**
	 * Check permissions.
	 *
	 * @param \WP_REST_Request $request Request object.
	 * @return bool|\WP_Error
	 */
	public function get_permissions_check( $request ) {
		if ( ! current_user_can( 'manage_woocommerce' ) ) {
			return new \WP_Error( 'woo_cart_abandonment_recovery_rest_cannot_view', __( 'Sorry, you don\'t have the access to perform this action.', 'woo-cart-abandonment-recovery' ), [ 'status' => rest_authorization_required_code() ] );
		}
		return true;
	}

	/**
	 * Keep a `Y-m-d` date, or drop anything else.
	 *
	 * @param mixed $value Date from the request.
	 * @return string The date, or an empty string when it is not a real `Y-m-d` date.
	 */
	public function sanitize_date( $value ) {
		$value = sanitize_text_field( (string) $value );
		$date  = \DateTime::createFromFormat( 'Y-m-d', $value );
		return ( $date && $date->format( 'Y-m-d' ) === $value ) ? $value : '';
	}

	/**
	 * Get one page of follow up records.
	 *
	 * Searching, filtering and paging all happen here, so the screen never receives more rows than
	 * it shows. `export` skips the paging and returns every match instead.
	 *
	 * @param \WP_REST_Request $request Request object.
	 * @return \WP_REST_Response
	 */
	public function get_records( $request ) {
		global $wpdb;
		$table = $wpdb->prefix . CARTFLOWS_CA_CART_ABANDONMENT_TABLE;

		$is_export = (bool) $request->get_param( 'export' );
		$page      = max( 1, (int) $request->get_param( 'page' ) );
		$per_page  = (int) $request->get_param( 'per_page' );
		$per_page  = $per_page > 0 ? min( self::MAX_PER_PAGE, $per_page ) : self::DEFAULT_PER_PAGE;
		$search    = trim( (string) $request->get_param( 'search' ) );

		// Filters the database can apply itself.
		$where  = [];
		$values = [];

		$statuses = self::STATUS_FILTERS[ $request->get_param( 'status' ) ] ?? [];
		if ( $statuses ) {
			$where[] = 'order_status IN (' . implode( ',', array_fill( 0, count( $statuses ), '%s' ) ) . ')';
			$values  = array_merge( $values, $statuses );
		}
		if ( '' !== $request->get_param( 'date_from' ) ) {
			$where[]  = 'time >= %s';
			$values[] = $request->get_param( 'date_from' ) . ' 00:00:00';
		}
		if ( '' !== $request->get_param( 'date_to' ) ) {
			$where[]  = 'time <= %s';
			$values[] = $request->get_param( 'date_to' ) . ' 23:59:59';
		}

		// The customer's name lives inside the serialized `other_fields`, with the first and last name
		// stored apart, so a search first narrows by a plain text match on each word and then settles
		// the exact hits in PHP below. There, the whole search text has to appear in one piece in the
		// email or in the customer's name.
		if ( '' !== $search ) {
			foreach ( preg_split( '/\s+/u', $search ) as $word ) {
				$like     = '%' . $wpdb->esc_like( $word ) . '%';
				$where[]  = '( email LIKE %s OR other_fields LIKE %s )';
				$values[] = $like;
				$values[] = $like;
			}
		}

		$where_sql = $where ? 'WHERE ' . implode( ' AND ', $where ) : '';

		// phpcs:disable WordPress.DB.PreparedSQL.InterpolatedNotPrepared, WordPress.DB.PreparedSQL.NotPrepared, WordPress.DB.DirectDatabaseQuery.DirectQuery, WordPress.DB.DirectDatabaseQuery.NoCaching
		$prepare = static function ( $sql ) use ( $wpdb, $values ) {
			return $values ? $wpdb->prepare( $sql, $values ) : $sql;
		};

		// An export takes every matching row; a page takes only its own slice.
		$offset = $is_export ? 0 : ( $page - 1 ) * $per_page;

		if ( '' === $search ) {
			$total = (int) $wpdb->get_var( $prepare( "SELECT COUNT(*) FROM {$table} {$where_sql}" ) );
			$ids   = $wpdb->get_col(
				$prepare( "SELECT id FROM {$table} {$where_sql} ORDER BY id DESC" ) . ( $is_export ? '' : sprintf( ' LIMIT %d OFFSET %d', $per_page, $offset ) )
			);
		} else {
			$candidates = $wpdb->get_results( $prepare( "SELECT id, email, other_fields FROM {$table} {$where_sql} ORDER BY id DESC" ) );
			$matches    = [];
			foreach ( $candidates as $candidate ) {
				if ( $this->matches_search( $candidate, $search ) ) {
					$matches[] = (int) $candidate->id;
				}
			}
			unset( $candidates );
			$total = count( $matches );
			$ids   = $is_export ? $matches : array_slice( $matches, $offset, $per_page );
		}

		$items = [];
		foreach ( array_chunk( array_map( 'absint', $ids ), self::RECORD_CHUNK_SIZE ) as $chunk ) {
			$records = $wpdb->get_results(
				$wpdb->prepare( "SELECT * FROM {$table} WHERE id IN (" . implode( ',', array_fill( 0, count( $chunk ), '%d' ) ) . ') ORDER BY id DESC', $chunk )
			);
			foreach ( $records as $record ) {
				$items[] = $this->prepare_record( $record );
			}
		}

		// Tells "nothing captured yet" apart from "nothing matches these filters".
		$has_records = $where ? (bool) $wpdb->get_var( "SELECT 1 FROM {$table} LIMIT 1" ) : $total > 0;
		// phpcs:enable

		return rest_ensure_response(
			[
				'items'       => $items,
				'total_items' => $total,
				'has_records' => $has_records,
			]
		);
	}

	/**
	 * Whether a record's customer name or email contains the search text.
	 *
	 * @param object $record Row with `email` and `other_fields`.
	 * @param string $search Search text.
	 * @return bool
	 */
	private function matches_search( $record, $search ) {
		$haystacks = [ (string) $record->email, $this->get_customer_name( maybe_unserialize( $record->other_fields ) ) ];
		foreach ( $haystacks as $haystack ) {
			// WordPress does not require the mbstring extension, so fall back to the plain match.
			$position = function_exists( 'mb_stripos' ) ? mb_stripos( $haystack, $search ) : stripos( $haystack, $search );
			if ( false !== $position ) {
				return true;
			}
		}
		return false;
	}

	/**
	 * Customer name from the saved checkout fields.
	 *
	 * @param mixed $fields Unserialized `other_fields`.
	 * @return string
	 */
	private function get_customer_name( $fields ) {
		$fields     = is_array( $fields ) ? $fields : [];
		$first_name = $fields['wcf_first_name'] ?? ( $fields['wcf_shipping_first_name'] ?? '' );
		$last_name  = $fields['wcf_last_name'] ?? ( $fields['wcf_shipping_last_name'] ?? '' );
		return trim( $first_name . ' ' . $last_name );
	}

	/**
	 * Format order status label.
	 *
	 * @param string $status Status code.
	 * @return string
	 */
	private function get_status_label( $status ) {
		switch ( $status ) {
			case WCF_CART_ABANDONED_ORDER:
				return 'Abandoned';
			case WCF_CART_COMPLETED_ORDER:
				return 'Successful';
			case WCF_CART_LOST_ORDER:
			case WCF_CART_FAILED_ORDER:
				return 'Failed';
			case WCF_CART_BLACKLISTED_ORDER:
				return 'Blacklisted';
			default:
				return 'Normal';
		}
	}

	/**
	 * Convert DB record to response format.
	 *
	 * @param object $record DB record.
	 * @return array
	 */
	private function prepare_record( $record ) {
		$fields  = maybe_unserialize( $record->other_fields );
		$name    = $this->get_customer_name( $fields );
		$country = is_array( $fields ) ? ( $fields['wcf_country'] ?? ( $fields['wcf_shipping_country'] ?? '' ) ) : '';

		$date = new \DateTime( $record->time );
		$date = $date->format( get_option( 'date_format' ) . ' ' . get_option( 'time_format' ) );

		return [
			'id'           => (int) $record->id,
			'userName'     => $name,
			'email'        => $record->email,
			'cartTotal'    => html_entity_decode( wp_strip_all_tags( wc_price( $record->cart_total ) ) ),
			'orderStatus'  => $this->get_status_label( $record->order_status ),
			'country'      => $country,
			'dateTime'     => $date,
			'unsubscribed' => (int) $record->unsubscribed,
		];
	}
}
