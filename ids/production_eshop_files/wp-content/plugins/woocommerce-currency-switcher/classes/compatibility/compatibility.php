<?php

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class WOOCS_compatibility {

	public function __construct() {
		// include_once WOOCS_PATH . 'classes/compatibility/sumo_subscriptions.php';
		if ( apply_filters( 'woocs_init_compatibility_woo_subscriptions', false ) ) {
			include_once WOOCS_PATH . 'classes/compatibility/woocommerce_subscriptions.php';
		}

		if ( class_exists( 'WC_Composite_Products' ) && apply_filters( 'woocs_init_compatibility_composite_products', true ) ) {
			include_once WOOCS_PATH . 'classes/compatibility/composite_products.php';
			new WOOCS_Composite_Products_Compatibility();
		}
	}
}
