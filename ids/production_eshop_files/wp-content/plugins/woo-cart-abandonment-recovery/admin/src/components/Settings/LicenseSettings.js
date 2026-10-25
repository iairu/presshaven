import { useEffect, useRef, useState } from '@wordpress/element';
import { Title, Button, Input, Label, Container, Loader } from '@bsf/force-ui';
import { CheckCircleIcon, KeyIcon } from '@heroicons/react/24/outline';
import { __, sprintf } from '@wordpress/i18n';
import parse from 'html-react-parser';

import apiFetch from '@wordpress/api-fetch';
import ConfirmDialog from '@Components/common/ConfirmDialog';
import { useStateValue, ActionTypes } from '@Store';

const GET_LICENSE_KEY_URL = 'https://my.cartflows.com/account/api-keys/';

// The license server answers with markup; show only its words, never its tags or links.
const toPlainText = ( message ) =>
	new window.DOMParser().parseFromString( String( message ), 'text/html' )
		.body.textContent;

function LicenseSettings() {
	const [ state, dispatch ] = useStateValue();
	const isLicenseActivated = state?.licenseStatus === '1';

	const [ licenseKey, setLicenseKey ] = useState( '' );
	const [ licenseErrors, setLicenseErrors ] = useState( false );
	const [ isProcessing, setIsProcessing ] = useState( false );
	const [ confirmingDeactivate, setConfirmingDeactivate ] = useState( false );

	const inputRef = useRef( null );

	useEffect( () => {
		if ( inputRef.current && ! isLicenseActivated ) {
			inputRef.current.focus();
		}
	}, [ isLicenseActivated ] );

	/**
	 * Ajax call to activate or deactivate the WCAR Pro license key.
	 *
	 * @param {boolean} isDeactivating True to deactivate the active license, false to activate the typed key.
	 */
	const sendLicenseRequest = ( isDeactivating ) => {
		setLicenseErrors( false );
		setIsProcessing( true );

		const nonces = cart_abandonment_admin?.pro_nonces || {};
		const formData = new window.FormData();

		formData.append(
			'action',
			isDeactivating ? 'wcar_deactivate_license' : 'wcar_activate_license'
		);
		formData.append( 'license_key', licenseKey );
		formData.append(
			'security',
			isDeactivating
				? nonces.deactivate_license_nonce
				: nonces.activate_license_nonce
		);

		apiFetch( {
			url: cart_abandonment_admin.ajax_url,
			method: 'POST',
			body: formData,
		} )
			.then( ( respData ) => {
				if ( respData.success ) {
					dispatch( {
						type: ActionTypes.UPDATE_LICENSE_STATUS,
						payload: isDeactivating ? '' : '1',
					} );
					// Pro features and the top bar read the status the page loaded with.
					window.location.reload();
					return;
				}

				const msg = respData.data?.error || respData.data || '';
				setLicenseErrors(
					msg ||
						__(
							'Unknown error occurred while activating the license.',
							'woo-cart-abandonment-recovery'
						)
				);
				setIsProcessing( false );
				setConfirmingDeactivate( false );
			} )
			.catch( () => {
				setLicenseErrors(
					__(
						'A network error occurred. Please try again.',
						'woo-cart-abandonment-recovery'
					)
				);
				setIsProcessing( false );
				setConfirmingDeactivate( false );
			} );
	};

	const handleSubmit = ( event ) => {
		event.preventDefault();

		if ( isProcessing ) {
			return;
		}

		if ( isLicenseActivated ) {
			// Deactivating ends updates and support for this site, so it asks first.
			setConfirmingDeactivate( true );
			return;
		}

		if ( '' === licenseKey.trim() ) {
			setLicenseErrors(
				__(
					'Please enter a valid license key!',
					'woo-cart-abandonment-recovery'
				)
			);
			return;
		}

		sendLicenseRequest( false );
	};

	const getButtonLabel = () => {
		if ( isProcessing ) {
			return isLicenseActivated
				? __( 'Deactivating…', 'woo-cart-abandonment-recovery' )
				: __( 'Activating…', 'woo-cart-abandonment-recovery' );
		}

		return isLicenseActivated
			? __( 'Deactivate License', 'woo-cart-abandonment-recovery' )
			: __( 'Activate License', 'woo-cart-abandonment-recovery' );
	};

	return (
		<>
			<Title
				description=""
				icon={ null }
				size="md"
				tag="h2"
				title={ __( 'My Account', 'woo-cart-abandonment-recovery' ) }
				className="mb-6 [&_h2]:text-gray-900 text-xl"
			/>
			<div className="h-auto bg-white rounded-xl shadow-sm">
				<form onSubmit={ handleSubmit } noValidate>
					<Container
						containerType="flex"
						direction="column"
						className="p-6"
					>
						<Container.Item>
							<Label
								className="font-semibold mb-1"
								htmlFor="wcar-license-key"
								size="md"
							>
								{ __(
									'License Key',
									'woo-cart-abandonment-recovery'
								) }
							</Label>
							<p className="font-normal text-sm text-gray-600 m-0 mb-4">
								{ isLicenseActivated &&
									__(
										'Your license is active on this site. Professional support and automatic updates for Cart Abandonment Recovery Pro are enabled.',
										'woo-cart-abandonment-recovery'
									) }
								{ ! isLicenseActivated &&
									parse(
										sprintf(
											// translators: %1$s: link html start, %2$s: link html end
											__(
												"Enter your valid license key below to activate Cart Abandonment Recovery Pro. If you don't have a license key yet, you can get it from %1$shere%2$s.",
												'woo-cart-abandonment-recovery'
											),
											`<a href="${ GET_LICENSE_KEY_URL }" class="text-flamingo-400 hover:text-flamingo-500 no-underline" target="_blank" rel="noopener noreferrer">`,
											'</a>'
										)
									) }
							</p>
						</Container.Item>
						<Container.Item className="w-full relative flex gap-4 flex-col sm:flex-row">
							<div className="flex-grow relative">
								{ isLicenseActivated ? (
									<Input
										id="wcar-license-key"
										type="text"
										size="md"
										className="wcar-license-key [&_input]:text-support-success [&_input]:disabled:text-support-success [&_input]:disabled:bg-gray-50"
										prefix={
											<CheckCircleIcon
												className="h-5 w-5 text-support-success"
												aria-hidden="true"
											/>
										}
										value={ __(
											'Your license key is activated',
											'woo-cart-abandonment-recovery'
										) }
										aria-label={ __(
											'License key status',
											'woo-cart-abandonment-recovery'
										) }
										disabled
										readOnly
									/>
								) : (
									<Input
										id="wcar-license-key"
										type="text"
										size="md"
										prefix={
											<KeyIcon
												className="h-5 w-5 text-gray-400"
												aria-hidden="true"
											/>
										}
										className={ `h-full w-full wcar-license-key focus:[&>input]:ring-focus ${
											licenseErrors
												? '!border-red-300 focus:border-red-500 !shadow-none !outline-0 !outline-none'
												: ''
										}` }
										name="wcar_license_key"
										value={ licenseKey }
										onChange={ ( value ) =>
											setLicenseKey( value )
										}
										placeholder={ __(
											'Paste your license key here',
											'woo-cart-abandonment-recovery'
										) }
										aria-label={ __(
											'License key input',
											'woo-cart-abandonment-recovery'
										) }
										aria-invalid={ !! licenseErrors }
										aria-describedby={
											licenseErrors
												? 'wcar-license-error'
												: undefined
										}
										autoComplete="off"
										ref={ inputRef }
									/>
								) }
							</div>
							<div>
								<Button
									type="submit"
									variant={
										isLicenseActivated
											? 'outline'
											: 'primary'
									}
									destructive={ isLicenseActivated }
									className="w-full"
									disabled={ isProcessing }
									icon={
										isProcessing && (
											<Loader
												className="bg-transparent"
												icon={ null }
												size="sm"
												variant={
													isLicenseActivated
														? 'primary'
														: 'secondary'
												}
											/>
										)
									}
									iconPosition="right"
								>
									{ getButtonLabel() }
								</Button>
							</div>
						</Container.Item>
						{ licenseErrors && (
							<Container.Item>
								<div
									id="wcar-license-error"
									className="license-errors text-sm text-red-600 mt-2"
									role="alert"
								>
									{ toPlainText( licenseErrors ) }
								</div>
							</Container.Item>
						) }
					</Container>
				</form>
			</div>
			<ConfirmDialog
				open={ confirmingDeactivate }
				setOpen={ setConfirmingDeactivate }
				title={ __(
					'Deactivate this license?',
					'woo-cart-abandonment-recovery'
				) }
				description={ __(
					'This site will stop receiving automatic updates and support for Cart Abandonment Recovery Pro until a license is activated again.',
					'woo-cart-abandonment-recovery'
				) }
				confirmLabel={ __(
					'Deactivate License',
					'woo-cart-abandonment-recovery'
				) }
				onConfirm={ () => sendLicenseRequest( true ) }
				isConfirming={ isProcessing }
				isDestructive
			/>
		</>
	);
}

export default LicenseSettings;
