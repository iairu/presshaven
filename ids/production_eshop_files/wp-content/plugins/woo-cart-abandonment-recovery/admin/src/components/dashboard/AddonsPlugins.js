import { useState } from 'react';
import PropTypes from 'prop-types';
import { Text, Button, toast } from '@bsf/force-ui';
import { __ } from '@wordpress/i18n';

import DashboardCard from '@Components/dashboard/DashboardCard';
import FeatureBadge from '@Components/common/FeatureBadge';
import { doApiFetch } from '@Store';

// Short descriptions for the narrow sidebar cards; the full text from PHP is the fallback.
const SHORT_DESCRIPTIONS = {
	cartflows: __(
		'Build high-converting checkout funnels.',
		'woo-cart-abandonment-recovery'
	),
	'modern-cart': __(
		'Fast and customizable cart for your website.',
		'woo-cart-abandonment-recovery'
	),
	suretriggers: __(
		'Automate tasks between your apps.',
		'woo-cart-abandonment-recovery'
	),
	'power-coupons': __(
		'Convert more with automated coupons.',
		'woo-cart-abandonment-recovery'
	),
};

const {
	extend_plugins: addonsPlugins,
	ajax_url: ajaxUrl,
	plugin_installer_nonce: installerNonce,
	plugin_activation_nonce: activationNonce,
} = cart_abandonment_admin;

const AddonsPlugins = ( { className } ) => {
	// Which plugin is being installed or activated right now, and at which step.
	const [ busy, setBusy ] = useState( { slug: '', step: '' } );
	const clearBusy = () => setBusy( { slug: '', step: '' } );

	const getCta = function ( plugin ) {
		if ( busy.slug === plugin.slug ) {
			return 'install' === busy.step
				? __( 'Installing…', 'woo-cart-abandonment-recovery' )
				: __( 'Activating…', 'woo-cart-abandonment-recovery' );
		}

		if ( 'inactive' === plugin.status ) {
			return __( 'Activate', 'woo-cart-abandonment-recovery' );
		}

		return __( 'Install & Activate', 'woo-cart-abandonment-recovery' );
	};

	const handleInstallActivate = function ( plugin ) {
		if ( 'not-installed' === plugin.status ) {
			setBusy( { slug: plugin.slug, step: 'install' } );

			const formData = new window.FormData();

			formData.append( 'action', 'cart_abandonment_install_plugin' );
			formData.append( 'slug', plugin.slug );
			formData.append(
				'_ajax_nonce',
				installerNonce
			);

			doApiFetch(
				ajaxUrl,
				formData,
				'POST',
				( response ) => {
					if ( response.success ) {
						activate_plugin( plugin );
					} else {
						clearBusy();
						toast.error(
							__(
								'Failed to install plugin',
								'woo-cart-abandonment-recovery'
							),
							{
								description: response.data?.message || '',
							}
						);
					}
				},
				( error ) => {
					clearBusy();
					toast.error(
						__(
							'Failed to install plugin',
							'woo-cart-abandonment-recovery'
						),
						{
							description: error.data?.message || '',
						}
					);
				},
				true
			);
		} else if ( 'inactive' === plugin.status ) {
			activate_plugin( plugin );
		}
	};

	const activate_plugin = ( plugin ) => {
		setBusy( { slug: plugin.slug, step: 'activate' } );

		const formData = new window.FormData();
		formData.append( 'action', 'cart_abandonment_activate_plugin' );
		formData.append( 'init', plugin.path );
		formData.append(
			'security',
			activationNonce
		);

		doApiFetch(
			ajaxUrl,
			formData,
			'POST',
			( response ) => {
				if ( response.success ) {
					window.location.reload();
				} else {
					clearBusy();
					toast.error(
						__(
							'Failed to activate plugin',
							'woo-cart-abandonment-recovery'
						),
						{
							description: response.data?.message || '',
						}
					);
				}
			},
			( error ) => {
				clearBusy();
				toast.error(
					__(
						'Failed to activate plugin',
						'woo-cart-abandonment-recovery'
					),
					{
						description: error.data?.message || '',
					}
				);
			},
			true
		);
	};

	return (
		<DashboardCard
			title={ __( 'Extend Your Website', 'woo-cart-abandonment-recovery' ) }
			compact
			className={ className }
		>
			<div className="bg-field-primary-background rounded-lg p-1 flex-1 grid grid-cols-1 sm:grid-cols-2 gap-1">
				{ addonsPlugins.map( ( plugin ) => (
					<div
						key={ plugin.slug }
						className="bg-background-primary rounded-md shadow-sm p-2 flex flex-col gap-3"
					>
						{ /* Card header: plugin logo (left) + action (right) */ }
						<div className="flex items-center justify-between p-1">
							<img
								src={ plugin.logo }
								className="size-6 shrink-0"
								alt=""
							/>
							{ 'active' === plugin.status ? (
								<span className="text-xs font-semibold text-badge-color-green">
									{ __(
										'Activated',
										'woo-cart-abandonment-recovery'
									) }
								</span>
							) : (
								<Button
									variant="ghost"
									size="xs"
									className="px-0 text-link-primary hover:text-link-primary-hover [@media(pointer:coarse)]:min-h-11 [@media(pointer:coarse)]:px-2"
									loading={ busy.slug === plugin.slug }
									disabled={ '' !== busy.slug }
									onClick={ () => handleInstallActivate( plugin ) }
								>
									{ getCta( plugin ) }
								</Button>
							) }
						</div>

						{ /* Text block: plugin name + description */ }
						<div className="flex flex-col gap-0.5 p-1">
							<div className="flex flex-wrap items-center gap-2">
								<Text as="h3" size={ 14 } weight={ 500 } color="primary">
									{ plugin.title }
								</Text>
								{ plugin?.feature && (
									<FeatureBadge
										feature={ plugin.feature }
										size="xs"
									/>
								) }
							</div>
							<Text size={ 12 } color="tertiary">
								{ SHORT_DESCRIPTIONS[ plugin.slug ] || plugin.desc }
							</Text>
						</div>
					</div>
				) ) }
			</div>
		</DashboardCard>
	);
};

AddonsPlugins.propTypes = {
	className: PropTypes.string,
};

export default AddonsPlugins;
