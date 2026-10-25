import { useEffect, useState } from 'react';
import { Drawer, toast } from '@bsf/force-ui';
import { __ } from '@wordpress/i18n';
import parse from 'html-react-parser';

import { doApiFetch } from '@Store';

import SmsTemplatesDrawerBody from './SmsTemplatesDrawerBody';
import TemplateDrawerHeader from '../shared/TemplateDrawerHeader';
import TemplateDrawerShell, {
	useTemplateDrawer,
} from '../shared/TemplateDrawerShell';
import {
	focusFirstInvalid,
	getRuleEngineError,
	isFormDirty,
} from '../shared/templateDrawerUtils';

const NEW_TEMPLATE_STATE = {
	template_name: '',
	sms_body: `Hi {{customer.firstname}}! You left {{cart.product.names}} in your cart. Complete your order before it’s gone: {{cart.checkout_url}}`,
	sms_frequency: 10,
	sms_frequency_unit: 'MINUTE',
	is_activated: false,
	override_global_coupon: false,
	discount_type: 'percent',
	coupon_amount: '',
	coupon_expiry_date: 1,
	coupon_expiry_unit: 'days',
	auto_coupon: false,
	free_shipping_coupon: false,
	individual_use_only: false,
	exclude_product_ids: '',
	enable_sms_rule_engine: false,
	sms_rule_engine: [],
};

// Lives inside the Drawer, which only mounts its content while open: the state below is
// seeded from the template on every open, so the first frame already shows the right data.
const SmsTemplateForm = ( { template, onSave } ) => {
	const { setDirty, markSaved } = useTemplateDrawer();
	const [ formState, setFormState ] = useState(
		() => template ? { ...template } : NEW_TEMPLATE_STATE
	);
	// What was loaded or last saved, to tell whether closing would lose anything.
	const [ savedState, setSavedState ] = useState( formState );
	const [ isSubmitting, setIsSubmitting ] = useState( false );
	const [ errors, setErrors ] = useState( {} );

	useEffect( () => {
		setDirty( isFormDirty( formState, savedState ) );
	}, [ formState, savedState ] );

	const handleChange = ( name, value ) => {
		setFormState( ( prev ) => ( { ...prev, [ name ]: value } ) );

		// Clear error for this field if it exists
		if ( errors[ name ] ) {
			setErrors( { ...errors, [ name ]: null } );
		}
	};

	const validateForm = () => {
		const newErrors = {};

		if ( ! formState.template_name.trim() ) {
			newErrors.template_name = __(
				'Template name is required',
				'woo-cart-abandonment-recovery'
			);
		}

		if ( ! formState.sms_body.trim() ) {
			newErrors.sms_body = __(
				'SMS body is required',
				'woo-cart-abandonment-recovery'
			);
		} else if ( formState.sms_body.length > 160 ) {
			newErrors.sms_body = __(
				'SMS body can’t be longer than 160 characters.',
				'woo-cart-abandonment-recovery'
			);
		}

		if ( formState.sms_frequency < 1 ) {
			newErrors.sms_frequency = __(
				'Time should be minimum 1 min.',
				'woo-cart-abandonment-recovery'
			);
		}

		const ruleEngineError = getRuleEngineError(
			formState?.enable_sms_rule_engine,
			formState.sms_rule_engine
		);
		if ( ruleEngineError ) {
			newErrors.sms_rule_engine = ruleEngineError;
		}

		setErrors( newErrors );
		if ( Object.keys( newErrors ).length !== 0 ) {
			toast.error( __( 'Error!', 'woo-cart-abandonment-recovery' ), {
				description: parse( Object.values( newErrors ).join( '<br>' ) ),
			} );
			focusFirstInvalid( newErrors );
			return false;
		}

		return true;
	};

	const handleSubmit = () => {
		if ( ! validateForm() ) {
			return;
		}

		setIsSubmitting( true );

		const formData = new window.FormData();

		// Set the full option name in the form data
		formData.append( 'wcf_template_name', formState.template_name );
		formData.append( 'wcf_sms_body', formState.sms_body );
		formData.append( 'wcf_sms_frequency', formState.sms_frequency );
		formData.append(
			'wcf_sms_frequency_unit',
			formState.sms_frequency_unit
		);
		formData.append(
			'wcf_activate_sms_template',
			formState.is_activated ? '1' : ''
		);
		formData.append(
			'wcf_override_global_coupon',
			formState.override_global_coupon ? '1' : ''
		);
		formData.append( 'wcf_discount_type', formState.discount_type );
		formData.append( 'wcf_coupon_amount', formState.coupon_amount );
		formData.append(
			'wcf_coupon_expiry_date',
			formState.coupon_expiry_date
		);
		formData.append(
			'wcf_coupon_expiry_unit',
			formState.coupon_expiry_unit
		);
		formData.append(
			'wcf_exclude_product_ids',
			formState.exclude_product_ids
		);
		formData.append( 'wcf_auto_coupon', formState.auto_coupon ? '1' : '' );
		formData.append(
			'wcf_free_shipping_coupon',
			formState.free_shipping_coupon ? '1' : ''
		);
		formData.append(
			'wcf_individual_use_only',
			formState.individual_use_only ? '1' : ''
		);
		formData.append(
			'wcf_enable_sms_rule_engine',
			formState?.enable_sms_rule_engine ? '1' : ''
		);
		formData.append(
			'wcf_sms_rule_engine',
			JSON.stringify( formState?.sms_rule_engine || [] )
		);

		// Add template ID if editing
		if ( template?.id ) {
			formData.append( 'id', template.id );
			formData.append( 'action', 'wcar_pro_update_sms_template' );
			formData.append(
				'security',
				cart_abandonment_admin?.update_sms_template_nonce
			);
		} else {
			formData.append( 'action', 'wcar_pro_save_sms_template' );
			formData.append(
				'security',
				cart_abandonment_admin?.save_sms_template_nonce
			);
		}

		const ajaxUrl = cart_abandonment_admin?.ajax_url || window.ajaxurl;
		// Make API call
		doApiFetch(
			ajaxUrl,
			formData,
			'POST',
			( response ) => {
				if ( response.success ) {
					// Call the parent's onSave callback with the updated template
					setSavedState( formState );
					markSaved();
					onSave( response.data.template );
					toast.success( __( 'Success!', 'woo-cart-abandonment-recovery' ), {
						description: __(
							'Template saved successfully',
							'woo-cart-abandonment-recovery'
						),
					} );
				} else {
					toast.error( __( 'Error!', 'woo-cart-abandonment-recovery' ), {
						description:
							response.data.message ||
							__(
								'Failed to save template',
								'woo-cart-abandonment-recovery'
							),
					} );
				}
			},
			( error ) => {
				toast.error( __( 'Error!', 'woo-cart-abandonment-recovery' ), {
					description:
						error.message ||
						__(
							'Failed to save template',
							'woo-cart-abandonment-recovery'
						),
				} );
			},
			true
		)
			.catch( () => {} )
			.finally( () => {
				setIsSubmitting( false );
			} );
	};

	return (
		<>
			<TemplateDrawerHeader
				title={
					formState?.template_name
						? formState.template_name
						: __( 'New SMS Template', 'woo-cart-abandonment-recovery' )
				}
				isSubmitting={ isSubmitting }
				onSave={ handleSubmit }
			/>
			<Drawer.Body className="overflow-x-hidden">
				<SmsTemplatesDrawerBody
					formState={ formState }
					handleChange={ handleChange }
					errors={ errors }
				/>
			</Drawer.Body>
		</>
	);
};

const SmsTemplatesDrawer = ( { open, setOpen, template, onSave } ) => (
	<TemplateDrawerShell open={ open } setOpen={ setOpen }>
		<SmsTemplateForm
			key={ template?.id ?? 'new' }
			template={ template }
			onSave={ onSave }
		/>
	</TemplateDrawerShell>
);

export default SmsTemplatesDrawer;
