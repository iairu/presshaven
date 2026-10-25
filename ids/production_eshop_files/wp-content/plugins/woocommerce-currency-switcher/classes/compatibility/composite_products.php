<?php

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * WooCommerce Composite Products on a cached site ("I am using cache plugin on my site").
 *
 * Composite builds the option lists, the component prices and the composite total in JavaScript
 * from data embedded in the page: data-price_data, data-options_data and wc_composite_params.
 * On a page taken from a page cache that data is in the currency the page was cached in.
 * When it is not the visitor currency, js/compatibility/composite_products.js asks for the same
 * form rendered in the visitor currency, moves its data into the form on the page and restarts
 * the composite script through Composite's own initializer.
 *
 * It also shows the currency code where Composite formats prices itself (dropdown option labels
 * and the composite total), when the FOX price format contains __CODE__.
 */
class WOOCS_Composite_Products_Compatibility {

	public function __construct() {
		add_action( 'wp_ajax_woocs_get_composite_form_data', array( $this, 'get_form_data' ) );
		add_action( 'wp_ajax_nopriv_woocs_get_composite_form_data', array( $this, 'get_form_data' ) );
		// Composite enqueues its own script from this action, so the form is on the page.
		add_action( 'woocommerce_composite_add_to_cart', array( $this, 'enqueue_script' ), 20 );

		// Currency code in prices Composite formats itself, see get_price_format()
		add_filter( 'woocommerce_composited_product_price_string_inner', array( $this, 'option_price_string' ), 10, 2 );
		add_filter( 'woocommerce_composite_front_end_params', array( $this, 'front_end_params' ), 9999 );
	}

	/**
	 * The FOX customer price format, or '' when it has no __CODE__ (then nothing is changed).
	 */
	private function get_price_format() {
		$format = get_option( 'woocs_customer_price_format', '__PRICE__' );
		return ( is_string( $format ) && false !== strpos( $format, '__CODE__' ) && false !== strpos( $format, '__PRICE__' ) ) ? $format : '';
	}

	/**
	 * Dropdown option label, e.g. "Carry Bag – $40.00": plain text, so the code is added as text,
	 * in the place the FOX format puts it.
	 */
	public function option_price_string( $string, $formatted_price ) {
		global $WOOCS;

		$format = $this->get_price_format();
		if ( ! $format || '' === (string) $formatted_price || false === strpos( $string, $formatted_price ) ) {
			return $string;
		}

		$priced = str_replace( array( '__PRICE__', '__CODE__' ), array( $formatted_price, $WOOCS->current_currency ), wp_strip_all_tags( $format ) );
		$pos    = strpos( $string, $formatted_price );

		return substr_replace( $string, $priced, $pos, strlen( $formatted_price ) );
	}

	/**
	 * The composite total is formatted by Composite's JS with i18n_price_format ("%p%s" by default).
	 * The original string is kept in woocs_i18n_price_format, so the form refresh can build it again
	 * for the visitor currency on a page cached in another one.
	 */
	public function front_end_params( $params ) {
		if ( ! is_array( $params ) || ! isset( $params['i18n_price_format'] ) ) {
			return $params;
		}

		$params['woocs_i18n_price_format'] = $params['i18n_price_format'];
		$params['i18n_price_format']       = $this->total_price_format( $params['i18n_price_format'] );

		return $params;
	}

	private function total_price_format( $base ) {
		global $WOOCS;

		$format = $this->get_price_format();
		$base   = (string) $base;
		// %p%s: price followed by the tax suffix, which FOX formats as one piece too
		$needle = false !== strpos( $base, '%p%s' ) ? '%p%s' : '%p';
		$pos    = strpos( $base, $needle );
		if ( ! $format || false === $pos ) {
			return $base;
		}

		// the same code markup as in WOOCS::woocommerce_price_html()
		$priced = str_replace( array( '__PRICE__', '__CODE__' ), array( $needle, '<span class="woocs_price_code">' . esc_html( $WOOCS->current_currency ) . '</span>' ), $format );

		return substr_replace( $base, $priced, $pos, strlen( $needle ) );
	}

	public function enqueue_script() {
		global $WOOCS;

		if ( ! $WOOCS->shop_is_cached || $WOOCS->is_uncacheable_request() ) {
			return;
		}

		// phpcs:ignore WordPress.WP.EnqueuedResourceParameters.NotInFooter
		wp_enqueue_script( 'woocs-composite-products', WOOCS_LINK . 'js/compatibility/composite_products.js', array( 'jquery', 'woocommerce-currency-switcher', 'wc-add-to-cart-composite' ), WOOCS_VERSION, true );
	}

	public function get_form_data() {
		global $WOOCS;

		$WOOCS->init_geo_currency();

		// Same convention as woocs_get_products_price_html: an empty answer means
		// the page is already in the visitor currency.
		if ( isset( $_REQUEST['current_currency'] ) && $_REQUEST['current_currency'] === $WOOCS->current_currency ) {
			wp_send_json( array() );
		}

		$ids = array();
		if ( isset( $_REQUEST['composite_ids'] ) && is_array( $_REQUEST['composite_ids'] ) ) {
			$ids = array_slice( array_unique( array_map( 'intval', $_REQUEST['composite_ids'] ) ), 0, 20 );
		}

		$forms = array();
		foreach ( $ids as $id ) {
			$product = wc_get_product( $id );
			if ( ! is_object( $product ) || ! $product->is_type( 'composite' ) || 'publish' !== $product->get_status() || post_password_required( $id ) ) {
				continue;
			}

			$forms[ $id ] = $this->render_form( $product );
		}

		// The money format Composite formats its totals with (WC_CP_Display, wc_composite_params).
		$params = array(
			'currency_symbol'              => get_woocommerce_currency_symbol(),
			'currency_position'            => esc_attr( stripslashes( get_option( 'woocommerce_currency_pos' ) ) ),
			'currency_format_num_decimals' => wc_get_price_decimals(),
			'currency_format_decimal_sep'  => wc_get_price_decimal_separator(),
			'currency_format_thousand_sep' => wc_get_price_thousand_separator(),
		);
		// rebuilt for the visitor currency from the original string the page sends back
		if ( ! empty( $_REQUEST['i18n_price_format'] ) && is_string( $_REQUEST['i18n_price_format'] ) ) {
			$params['i18n_price_format'] = $this->total_price_format( wp_kses_post( wp_unslash( $_REQUEST['i18n_price_format'] ) ) );
		}

		wp_send_json(
			array(
				'current_currency' => $WOOCS->current_currency,
				'forms'            => $forms,
				'params'           => $params,
			)
		);
	}

	private function render_form( $product ) {
		global $post;

		$post = get_post( $product->get_id() ); // phpcs:ignore WordPress.WP.GlobalVariablesOverride.Prohibited
		setup_postdata( $post );
		$GLOBALS['product'] = $product;

		ob_start();
		if ( function_exists( 'wc_cp_add_to_cart' ) ) {
			wc_cp_add_to_cart();
		} else {
			do_action( 'woocommerce_composite_add_to_cart' );
		}
		$html = ob_get_clean();

		wp_reset_postdata();

		return $html;
	}
}
