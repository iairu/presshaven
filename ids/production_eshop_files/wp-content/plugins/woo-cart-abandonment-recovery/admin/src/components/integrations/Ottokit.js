/* eslint-disable indent */
import { useEffect, useRef, useState } from 'react';
import { Button, Title, Loader } from '@bsf/force-ui';
import { CheckIcon, PlusIcon } from '@heroicons/react/24/outline';
import { __ } from '@wordpress/i18n';
import apiFetch from '@wordpress/api-fetch';

import SectionWrapper from '../common/SectionWrapper';
import LoadFailedBlock from '@Components/common/LoadFailedBlock';
import InstallationMessage from '@Images/installation-message.svg';
import { cn } from '@Utils/helper';

const OTTOKIT_EMBED_URL = 'https://app.suretriggers.com/js/v2/embed.js';

const Ottokit = () => {
	const [ ottokitStatus, setOttokitStatus ] = useState(
		cart_abandonment_admin.extend_plugins?.find(
			( plugin ) => 'suretriggers' === plugin.slug
		)?.status ?? 'not-installed'
	);
	const [ buttonProcessing, SetButtonProcessing ] = useState( false );
	const [ embedFailed, setEmbedFailed ] = useState( false );
	const [ embedAttempt, setEmbedAttempt ] = useState( 0 );

	// Which step failed last, so the button can offer the same step again.
	const failedStep = useRef( 'install' );

	useEffect( () => {
		if ( 'active' !== cart_abandonment_admin?.ottokit?.status ) {
			return;
		}

		if ( ! cart_abandonment_admin?.ottokit?.is_ottokit_connected ) {
			window.location.href =
				cart_abandonment_admin?.ottokit?.ottokit_redirect_url;
			return;
		}

		const config = cart_abandonment_admin?.ottokit?.config;
		const init = () => {
			if (
				window.SureTriggers &&
				document.getElementById( 'wcar-iframe-wrapper' )
			) {
				window.SureTriggers.init( config );
			}
		};

		// The embed script is only needed here, so it loads with this tab, not with every page.
		if ( window.SureTriggers ) {
			init();
			return;
		}

		// Leaving the tab and coming back before the script arrives must not load it twice.
		let script = document.querySelector(
			`script[src="${ OTTOKIT_EMBED_URL }"]`
		);
		if ( ! script ) {
			script = document.createElement( 'script' );
			script.src = OTTOKIT_EMBED_URL;
			script.async = true;
			// A failed load is dropped, so the next visit to this tab tries again. A script that
			// loads but never sets up `SureTriggers` (it threw, or was stubbed out) counts as failed.
			const dropScript = () => script.remove();
			script.addEventListener( 'error', dropScript );
			script.addEventListener( 'load', () => {
				if ( ! window.SureTriggers ) {
					dropScript();
				}
			} );
			document.body.appendChild( script );
		}
		const onEmbedError = () => setEmbedFailed( true );
		const onEmbedLoad = () =>
			window.SureTriggers ? init() : setEmbedFailed( true );
		script.addEventListener( 'load', onEmbedLoad );
		script.addEventListener( 'error', onEmbedError );

		return () => {
			script.removeEventListener( 'load', onEmbedLoad );
			script.removeEventListener( 'error', onEmbedError );
		};
	}, [ embedAttempt ] );

	const retryEmbed = () => {
		setEmbedFailed( false );
		setEmbedAttempt( ( attempt ) => attempt + 1 );
	};

	const getOttokitCta = function ( status ) {
		let statusText = '';

		switch ( status ) {
			case 'inactive':
				statusText = __( 'Activate', 'woo-cart-abandonment-recovery' );
				break;
			case 'installing':
				statusText = __(
					'Installing…',
					'woo-cart-abandonment-recovery'
				);
				break;
			case 'activating':
				statusText = __(
					'Activating…',
					'woo-cart-abandonment-recovery'
				);
				break;
			case 'fail':
				statusText = __( 'Try again', 'woo-cart-abandonment-recovery' );
				break;
			case 'reload':
				statusText = __( 'Reloading', 'woo-cart-abandonment-recovery' );
				break;
			default:
				statusText = __(
					'Install & Activate',
					'woo-cart-abandonment-recovery'
				);
		}

		return statusText;
	};

	const handleInstallActivateOttokit = function ( e ) {
		e.preventDefault();

		let step = '';
		if ( 'fail' === ottokitStatus ) {
			step = failedStep.current;
		} else if ( 'not-installed' === ottokitStatus ) {
			step = 'install';
		} else if ( 'inactive' === ottokitStatus ) {
			step = 'activate';
		}

		if ( 'install' === step ) {
			setOttokitStatus( 'installing' );
			SetButtonProcessing( true );

			const formData = new window.FormData();

			formData.append( 'action', 'cart_abandonment_install_plugin' );
			formData.append( 'slug', 'suretriggers' );
			formData.append(
				'_ajax_nonce',
				cart_abandonment_admin.plugin_installer_nonce
			);

			apiFetch( {
				url: cart_abandonment_admin.ajax_url,
				method: 'POST',
				body: formData,
			} )
				.then( ( res ) => {
					if ( res.success ) {
						activate_plugin( 'suretriggers/suretriggers.php' );
					} else {
						failedStep.current = 'install';
						SetButtonProcessing( false );
						setOttokitStatus( 'fail' );
					}
				} )
				.catch( () => {
					failedStep.current = 'install';
					SetButtonProcessing( false );
					setOttokitStatus( 'fail' );
				} );
		} else if ( 'activate' === step ) {
			activate_plugin( 'suretriggers/suretriggers.php' );
		}
	};

	const activate_plugin = ( slug ) => {
		setOttokitStatus( 'activating' );
		SetButtonProcessing( true );
		const formData = new window.FormData();
		formData.append( 'action', 'cart_abandonment_activate_plugin' );
		formData.append( 'init', slug );
		formData.append(
			'security',
			cart_abandonment_admin.plugin_activation_nonce
		);
		apiFetch( {
			url: cart_abandonment_admin.ajax_url,
			method: 'POST',
			body: formData,
		} )
			.then( ( response ) => {
				SetButtonProcessing( false );
				if ( response && response.success ) {
					setOttokitStatus( 'reload' );
					setTimeout( () => {
						window.location.reload();
					}, 2000 );
				} else {
					failedStep.current = 'activate';
					setOttokitStatus( 'fail' );
				}
			} )
			.catch( () => {
				failedStep.current = 'activate';
				SetButtonProcessing( false );
				setOttokitStatus( 'fail' );
			} );
	};

	return (
		<div>
			<SectionWrapper>
				{ 'active' === ottokitStatus && embedFailed ? (
					<LoadFailedBlock
						title={ __(
							'OttoKit could not be loaded',
							'woo-cart-abandonment-recovery'
						) }
						onRetry={ retryEmbed }
					/>
				) : 'active' === ottokitStatus ? (
					<div
						className="h-[75vh] w-full"
						id="wcar-iframe-wrapper"
					></div>
				) : (
					<div className="p-2 sm:p-4 flex flex-col md:flex-row md:justify-between items-center gap-6">
						<div className="shrink-0">
							<img
								src={ InstallationMessage }
								width="320"
								height="320"
								className="h-40 w-40 sm:h-56 sm:w-56 md:h-80 md:w-80 max-w-full object-contain"
								alt=""
							/>
						</div>
						<div className="flex flex-col gap-2">
							<Title
								size="sm"
								tag="h2"
								title={ __(
									'Automate Cart Recovery with OttoKit',
									'woo-cart-abandonment-recovery'
								) }
								className="[&_h2]:text-gray-900"
							/>
							<p className="m-0 text-base font-normal text-gray-500">
								{ __(
									'Supercharge your recovery process by connecting WooCommerce Cart Abandonment Recovery with OttoKit. Get real-time alerts, automate actions, and keep your team in the loop instantly.',
									'woo-cart-abandonment-recovery'
								) }
							</p>
							<ul className="m-0 p-0 list-none flex flex-col gap-2">
								<li className="flex items-start gap-2">
									<CheckIcon
										className="mt-1 h-4 w-4 shrink-0 text-flamingo-400"
										aria-hidden="true"
									/>
									<span className="text-gray-500 text-base font-normal">
										{ __(
											'Connect with tools you already use like Slack, Telegram, WhatsApp, Google Sheets, and more.',
											'woo-cart-abandonment-recovery'
										) }
									</span>
								</li>
								<li className="flex items-start gap-2">
									<CheckIcon
										className="mt-1 h-4 w-4 shrink-0 text-flamingo-400"
										aria-hidden="true"
									/>
									<span className="text-gray-500 text-base font-normal">
										{ __(
											'Engage customers on channels they use like SMS, WhatsApp, or Facebook Messenger.',
											'woo-cart-abandonment-recovery'
										) }
									</span>
								</li>
								<li className="flex items-start gap-2">
									<CheckIcon
										className="mt-1 h-4 w-4 shrink-0 text-flamingo-400"
										aria-hidden="true"
									/>
									<span className="text-gray-500 text-base font-normal">
										{ __(
											'Automatically resend failed emails or trigger alerts to your team.',
											'woo-cart-abandonment-recovery'
										) }
									</span>
								</li>
							</ul>
							<div className="mt-4">
								<Button
									icon={
										buttonProcessing ? (
											<Loader
												className="text-white"
												size="md"
												variant="primary"
											/>
										) : (
											'reload' !== ottokitStatus && (
												<PlusIcon aria-hidden="true" />
											)
										)
									}
									iconPosition="left"
									size="md"
									tag="button"
									type="button"
									variant="primary"
									className="w-full sm:w-auto [@media(pointer:coarse)]:min-h-11"
									onClick={ handleInstallActivateOttokit }
									disabled={ buttonProcessing }
								>
									{ getOttokitCta( ottokitStatus ) }
								</Button>
								<p
									className={ cn(
										'm-0 mt-2 text-sm',
										'fail' === ottokitStatus
											? 'text-support-error'
											: 'sr-only'
									) }
									role="status"
								>
									{ 'fail' === ottokitStatus &&
										__(
											'OttoKit could not be set up. Check your connection and try again.',
											'woo-cart-abandonment-recovery'
										) }
								</p>
							</div>
						</div>
					</div>
				) }
			</SectionWrapper>
		</div>
	);
};

export default Ottokit;
