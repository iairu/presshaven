import { useState, useEffect } from 'react';
import { Input, Button, Loader, toast } from '@bsf/force-ui';
import { __, sprintf } from '@wordpress/i18n';

import { useStateValue } from '@Store';
import useDebounceDispatch from '@Utils/debounceDispatch';
import FieldWrapper from '@Components/common/FieldWrapper';
import { useFieldA11y } from '@Components/common/fieldA11y';

const WebhookURLField = ( { title, description, name, value, onSaved } ) => {
	const [ state, dispatch ] = useStateValue();
	const settingsData = state.settingsData || {};
	const settingsValues = settingsData.values || {};
	const initial = settingsValues[ name ] ?? value;
	const [ url, setUrl ] = useState( initial || '' );
	const [ isTriggered, setIsTriggered ] = useState( false );
	const debouncedUpdate = useDebounceDispatch(
		dispatch,
		name,
		onSaved,
		400,
		true
	);

	const a11y = useFieldA11y( { description } );

	useEffect( () => {
		setUrl( initial || '' );
	}, [ initial ] );

	function handleInputChange( val ) {
		setUrl( val );
		debouncedUpdate( String( val ) );
	}

	function handleTrigger() {
		if ( url === '' ) {
			toast.error(
				__( 'Enter Webhook URL', 'woo-cart-abandonment-recovery' )
			);
			return;
		}
		setIsTriggered( true );
		const details = window.wcf_ca_details || {};
		const sampleData = {
			first_name: details.name || '',
			last_name: details.surname || '',
			email: details.email || '',
			phone: details.phone || '',
			order_status: 'abandoned',
			checkout_url:
				window.location.origin + '/checkout/?wcf_ac_token=something',
			coupon_code: 'abcgefgh',
			product_names: 'Product1, Product2 & Product3',
			cart_total: ( details.woo_currency_symbol || '' ) + '20',
			product_table: `<table align="left" cellpadding="10" cellspacing="0" style="float: none; border: 1px solid #e5e5e5;">
			<tr align="center">
				<th style="color: #636363; border: 1px solid #e5e5e5;">Item</th>
				<th style="color: #636363; border: 1px solid #e5e5e5;">Name</th>
				<th style="color: #636363; border: 1px solid #e5e5e5;">Quantity</th>
				<th style="color: #636363; border: 1px solid #e5e5e5;">Price</th>
				<th style="color: #636363; border: 1px solid #e5e5e5;">Line Subtotal</th>
			</tr>
			<tr style="color: #636363; border: 1px solid #e5e5e5;" align="center">
				<td style="color: #636363; border: 1px solid #e5e5e5;"><img class="demo_img" style="height: 42px; width: 42px;" src="#"></td>
				<td style="color: #636363; border: 1px solid #e5e5e5;">Product1</td>
				<td style="color: #636363; border: 1px solid #e5e5e5;">1</td>
				<td style="color: #636363; border: 1px solid #e5e5e5;">&pound;85.00</td>
				<td style="color: #636363; border: 1px solid #e5e5e5;">&pound;85.00</td>
			</tr>
		</table>`,
		};

		const formData = new FormData();
		for ( const key in sampleData ) {
			formData.append( key, sampleData[ key ] );
		}

		fetch( url, {
			method: 'POST',
			body: formData,
		} )
			.then( ( response ) => {
				if ( response.ok ) {
					toast.success(
						__(
							'Webhook trigger successful',
							'woo-cart-abandonment-recovery'
						)
					);
				} else {
					toast.error(
						__(
							'Webhook trigger failed',
							'woo-cart-abandonment-recovery'
						),
						{
							description: sprintf(
								// translators: %d: HTTP status code returned by the webhook URL.
								__(
									'The webhook URL answered with status %d.',
									'woo-cart-abandonment-recovery'
								),
								response.status
							),
						}
					);
				}
			} )
			.catch( () => {
				toast.error(
					__(
						'Webhook trigger failed',
						'woo-cart-abandonment-recovery'
					),
					{
						description: __(
							'The URL could not be reached, or it does not accept requests from this page.',
							'woo-cart-abandonment-recovery'
						),
					}
				);
			} )
			.finally( () => {
				setIsTriggered( false );
			} );
	}

	return (
		<FieldWrapper
			title={ title }
			description={ description }
			fieldId={ a11y.id }
			type="block"
		>
			<div className="flex flex-wrap gap-2 items-center">
				<div className="flex-1 min-w-48">
					<Input
						{ ...a11y.controlProps }
						type="url"
						size="md"
						name={ name }
						value={ url }
						onChange={ handleInputChange }
						placeholder={ __(
							'Enter the Webhook URL',
							'woo-cart-abandonment-recovery'
						) }
					/>
				</div>
				<Button
					className="px-4 bg-primary-25 text-primary-600 outline-primary-300 hover:bg-primary-25 hover:outline-primary-300"
					size="md"
					tag="button"
					type="button"
					variant="outline"
					onClick={ handleTrigger }
					disabled={ isTriggered }
					icon={
						isTriggered && (
							<Loader
								className="text-primary-600"
								size="md"
								variant="primary"
							/>
						)
					}
					iconPosition="left"
				>
					{ __( 'Trigger Sample', 'woo-cart-abandonment-recovery' ) }
				</Button>
			</div>
		</FieldWrapper>
	);
};

export default WebhookURLField;
