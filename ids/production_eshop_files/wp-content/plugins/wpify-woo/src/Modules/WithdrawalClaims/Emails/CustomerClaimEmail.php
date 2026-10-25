<?php

namespace WpifyWoo\Modules\WithdrawalClaims\Emails;

defined( 'ABSPATH' ) || exit;

use WpifyWoo\Modules\WithdrawalClaims\WithdrawalClaimsRepository;
use WpifyWooDeps\Wpify\PluginUtils\PluginUtils;

class CustomerClaimEmail extends AbstractRequestEmail {

	public function __construct( WithdrawalClaimsRepository $repository, PluginUtils $utils ) {
		$this->id             = 'wpify_woo_claim_customer';
		$this->customer_email = true;
		$this->title          = __( 'Claim — confirmation to customer', 'wpify-woo' );
		$this->description    = __( 'Confirms receipt of a claim (reklamace) request to the customer.', 'wpify-woo' );
		$this->template_html  = 'emails/customer-request-html.php';
		$this->template_plain = 'emails/customer-request-plain.php';

		parent::__construct( $repository, $utils );
	}

	public function is_customer(): bool {
		return true;
	}

	public function type(): string {
		return 'claim';
	}

	public function get_default_subject(): string {
		return __( 'Claim received — order {order_number}', 'wpify-woo' );
	}

	public function get_default_heading(): string {
		return __( 'Your claim has been received', 'wpify-woo' );
	}

	/**
	 * Claims are governed by national warranty law, not Directive (EU) 2023/2673
	 * (which covers the online withdrawal function), so the shared default text
	 * would be misleading here.
	 */
	public function get_default_intro_content(): string {
		return __( 'We have received your claim. Please keep this email as a record of its receipt.', 'wpify-woo' );
	}
}
