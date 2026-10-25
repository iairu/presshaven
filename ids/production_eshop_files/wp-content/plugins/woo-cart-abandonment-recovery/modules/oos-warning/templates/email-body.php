<?php
/**
 * Out-of-stock admin warning — email body.
 *
 * Expects the following variables from Cartflows_Ca_Oos_Warning::get_email_content():
 *
 * @var array<int, array<string, mixed>> $affected_carts  All abandoned carts with their OOS items.
 * @var array<int, array<string, mixed>> $display_carts   Capped subset of carts actually rendered.
 * @var int                              $total_carts     Total number of affected carts.
 * @var int                              $total_products  Distinct out-of-stock products across all carts.
 * @var int                              $remaining_carts Carts not shown (total minus rendered) for the overflow note.
 * @var string                           $store_name      Site name.
 * @var string                           $store_url       Site home URL (store name links here).
 * @var string                           $dashboard_link  WCAR dashboard URL.
 *
 * @package Woocommerce-Cart-Abandonment-Recovery
 * @since   2.2.0
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Exit if accessed directly.
}

$affected_carts  = isset( $affected_carts ) && is_array( $affected_carts ) ? $affected_carts : [];
$display_carts   = isset( $display_carts ) && is_array( $display_carts ) ? $display_carts : $affected_carts;
$total_carts     = isset( $total_carts ) ? (int) $total_carts : count( $affected_carts );
$total_products  = isset( $total_products ) ? (int) $total_products : 0;
$remaining_carts = isset( $remaining_carts ) ? (int) $remaining_carts : 0;
$store_name      = isset( $store_name ) ? $store_name : get_bloginfo( 'name' );
$store_url       = isset( $store_url ) ? $store_url : home_url( '/' );
$dashboard_link  = isset( $dashboard_link ) ? $dashboard_link : admin_url( 'admin.php?page=woo-cart-abandonment-recovery' );

// Brand colour is reserved for links and the action button only; everything else is neutral.
$wcf_brand  = '#f06434';
$wcf_border = '#e5e7eb';
$wcf_text   = '#1f2937';
$wcf_muted  = '#6b7280';

// Linked store name (brand-coloured) reused in the intro and footer copy.
$store_link = '<a href="' . esc_url( $store_url ) . '" style="color:' . $wcf_brand . ';text-decoration:none;">' . esc_html( $store_name ) . '</a>';

// Brand-coloured inline link allowed inside the translated, store-name copy.
$allowed_store_link = [
	'a' => [
		'href'  => [],
		'style' => [],
	],
];

// Short summary of the digest, with correct singular/plural forms.
$products_summary = sprintf(
	/* translators: %s: number of out-of-stock products. */
	_n( '%s out-of-stock product', '%s out-of-stock products', $total_products, 'woo-cart-abandonment-recovery' ),
	number_format_i18n( $total_products )
);

$carts_summary = sprintf(
	/* translators: %s: number of abandoned carts. */
	_n( '%s abandoned cart', '%s abandoned carts', $total_carts, 'woo-cart-abandonment-recovery' ),
	number_format_i18n( $total_carts )
);
?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
	<head>
		<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
		<meta name="viewport" content="width=device-width, initial-scale=1" />
		<title><?php echo esc_html__( 'Out-of-stock alert', 'woo-cart-abandonment-recovery' ); ?></title>
	</head>
	<body style="margin:0;padding:0;background:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;color:<?php echo esc_attr( $wcf_text ); ?>;">
		<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:24px 0;">
			<tr>
				<td align="center">
					<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:8px;border:1px solid <?php echo esc_attr( $wcf_border ); ?>;">
						<tr>
							<td style="padding:24px 32px;border-bottom:1px solid <?php echo esc_attr( $wcf_border ); ?>;">
								<h1 style="margin:0;font-size:18px;font-weight:600;color:<?php echo esc_attr( $wcf_text ); ?>;">
									<?php echo esc_html__( 'Out-of-stock products in abandoned carts', 'woo-cart-abandonment-recovery' ); ?>
								</h1>
							</td>
						</tr>
						<tr>
							<td style="padding:24px 32px;">
								<p style="margin:0 0 8px;font-size:15px;line-height:1.6;color:<?php echo esc_attr( $wcf_text ); ?>;">
									<?php
									printf(
										wp_kses(
											/* translators: %s: linked store name. */
											__( 'Some abandoned carts on %s contain products that are now out of stock. Recovery emails for these carts may point customers to items they can no longer purchase.', 'woo-cart-abandonment-recovery' ),
											$allowed_store_link
										),
										$store_link // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- Built above with esc_url() + esc_html().
									);
									?>
								</p>
								<p style="margin:0 0 20px;font-size:13px;line-height:1.6;color:<?php echo esc_attr( $wcf_muted ); ?>;">
									<?php
									echo esc_html(
										sprintf(
											/* translators: 1: count of out-of-stock products, 2: count of abandoned carts. */
											__( '%1$s across %2$s.', 'woo-cart-abandonment-recovery' ),
											$products_summary,
											$carts_summary
										)
									);
									?>
								</p>

								<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid <?php echo esc_attr( $wcf_border ); ?>;border-radius:6px;border-collapse:separate;font-size:13px;">
									<tr style="text-align:left;">
										<th style="padding:10px 16px;font-weight:600;color:<?php echo esc_attr( $wcf_muted ); ?>;border-bottom:1px solid <?php echo esc_attr( $wcf_border ); ?>;"><?php echo esc_html__( 'Customer', 'woo-cart-abandonment-recovery' ); ?></th>
										<th style="padding:10px 16px;font-weight:600;color:<?php echo esc_attr( $wcf_muted ); ?>;border-bottom:1px solid <?php echo esc_attr( $wcf_border ); ?>;"><?php echo esc_html__( 'Abandoned', 'woo-cart-abandonment-recovery' ); ?></th>
										<th style="padding:10px 16px;font-weight:600;color:<?php echo esc_attr( $wcf_muted ); ?>;border-bottom:1px solid <?php echo esc_attr( $wcf_border ); ?>;"><?php echo esc_html__( 'Out-of-stock products', 'woo-cart-abandonment-recovery' ); ?></th>
									</tr>
									<?php foreach ( $display_carts as $cart ) : ?>
										<?php $item_count = isset( $cart['items'] ) && is_array( $cart['items'] ) ? count( $cart['items'] ) : 0; ?>
										<tr>
											<td style="padding:12px 16px;vertical-align:top;border-top:1px solid <?php echo esc_attr( $wcf_border ); ?>;color:<?php echo esc_attr( $wcf_text ); ?>;">
												<span style="display:block;font-weight:600;"><?php echo esc_html( $cart['customer_name'] ); ?></span>
												<?php if ( ! empty( $cart['email'] ) ) : ?>
													<span style="display:block;color:<?php echo esc_attr( $wcf_muted ); ?>;font-size:12px;"><?php echo esc_html( $cart['email'] ); ?></span>
												<?php endif; ?>
											</td>
											<td style="padding:12px 16px;vertical-align:top;border-top:1px solid <?php echo esc_attr( $wcf_border ); ?>;color:<?php echo esc_attr( $wcf_muted ); ?>;font-size:12px;white-space:nowrap;">
												<?php echo esc_html( $cart['abandoned_on'] ); ?>
											</td>
											<td style="padding:12px 16px;vertical-align:top;border-top:1px solid <?php echo esc_attr( $wcf_border ); ?>;color:<?php echo esc_attr( $wcf_text ); ?>;">
												<?php
												$product_labels = [];
												foreach ( $cart['items'] as $item ) {
													$qty              = isset( $item['quantity'] ) ? (int) $item['quantity'] : 1;
													$label            = esc_html( $item['name'] );
													$product_labels[] = $qty > 1 ? $label . ' &times;' . absint( $qty ) : $label;
												}
												// Each label is individually escaped above; the separator and "&times;" are static.
												echo implode( ', ', $product_labels ); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- Pieces escaped above.
												?>
											</td>
										</tr>
									<?php endforeach; ?>
									<?php if ( $remaining_carts > 0 ) : ?>
										<tr>
											<td colspan="3" style="padding:12px 16px;border-top:1px solid <?php echo esc_attr( $wcf_border ); ?>;color:<?php echo esc_attr( $wcf_muted ); ?>;font-size:12px;">
												<?php
												echo esc_html(
													sprintf(
														/* translators: %s: number of additional abandoned carts not listed. */
														_n(
															'and %s more abandoned cart with out-of-stock products.',
															'and %s more abandoned carts with out-of-stock products.',
															$remaining_carts,
															'woo-cart-abandonment-recovery'
														),
														number_format_i18n( $remaining_carts )
													)
												);
												?>
											</td>
										</tr>
									<?php endif; ?>
								</table>

								<p style="margin:24px 0 0;text-align:center;">
									<a href="<?php echo esc_url( $dashboard_link ); ?>" style="display:inline-block;padding:12px 24px;background:<?php echo esc_attr( $wcf_brand ); ?>;color:#ffffff;text-decoration:none;border-radius:6px;font-size:14px;font-weight:600;">
										<?php echo esc_html__( 'Review abandoned carts', 'woo-cart-abandonment-recovery' ); ?>
									</a>
								</p>
							</td>
						</tr>
						<tr>
							<td style="padding:16px 32px;border-top:1px solid <?php echo esc_attr( $wcf_border ); ?>;color:<?php echo esc_attr( $wcf_muted ); ?>;font-size:12px;text-align:center;">
								<?php
								printf(
									wp_kses(
										/* translators: %s: linked store name. */
										__( 'You are receiving this because out-of-stock notifications are enabled for %s.', 'woo-cart-abandonment-recovery' ),
										$allowed_store_link
									),
									$store_link // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- Built above with esc_url() + esc_html().
								);
								?>
							</td>
						</tr>
					</table>
				</td>
			</tr>
		</table>
	</body>
</html>
