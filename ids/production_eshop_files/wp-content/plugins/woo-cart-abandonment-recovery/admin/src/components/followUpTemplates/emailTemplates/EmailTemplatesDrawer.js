import { useEffect, useState } from 'react';
import { Drawer, toast } from '@bsf/force-ui';
import { __ } from '@wordpress/i18n';
import parse from 'html-react-parser';

import { doApiFetch } from '@Store';

import SettingsDrawerBody from '@Components/followUpTemplates/emailTemplates//EmailTemplatesDrawerBody';
import { useProAccess } from '@Components/pro/useProAccess';
import TemplateDrawerHeader from '../shared/TemplateDrawerHeader';
import TemplateDrawerShell, {
	DRAWER_TRANSITION_S,
	useTemplateDrawer,
} from '../shared/TemplateDrawerShell';
import {
	focusFirstInvalid,
	getRuleEngineError,
	isFormDirty,
} from '../shared/templateDrawerUtils';

const DEFAULT_VISIBLE_COLUMNS = [
	'image',
	'name',
	'quantity',
	'price',
	'subtotal',
];

const DEFAULT_EMAIL_BODY = `<p>Hi {{customer.firstname}}!</p>
<p>We're having trouble processing your recent purchase. Would you mind completing it?</p>
<p>Here's a link to continue where you left off: </p>
<p><a href="{{cart.checkout_url}}" target="_blank" rel="noopener"> Continue Your Purchase Now </a></p>
<p>Kindly,<br>
{{admin.firstname}}<br>
{{admin.company}}<br>
{{cart.unsubscribe}}</p>`;

const NEW_TEMPLATE_STATE = {
	template_name: '',
	email_subject: '',
	email_body: DEFAULT_EMAIL_BODY,
	email_frequency: 10,
	email_frequency_unit: 'MINUTE',
	is_activated: false,
	override_global_coupon: false,
	discount_type: 'percent',
	coupon_amount: '',
	coupon_expiry_date: 1,
	coupon_expiry_unit: 'days',
	use_woo_email_style: false,
	auto_coupon: false,
	free_shipping_coupon: false,
	individual_use_only: false,
	modify_product_table: false,
	product_image_size: 'medium',
	show_prices_with_tax: false,
	visible_columns: DEFAULT_VISIBLE_COLUMNS,
	admin_email_copy_status: false,
	admin_email_copy_type: 'bcc',
	admin_email_copy_address: '',
	enable_email_rule_engine: false,
	email_rule_engine: [],
	exclude_product_ids: [],
};

// TinyMCE is the heaviest thing the drawer does, so it boots once the slide-in has finished
// instead of competing with the animation for the main thread.
const EDITOR_INIT_DELAY_MS = Math.round( DRAWER_TRANSITION_S * 1000 ) + 50;

/**
 * Form state for the drawer: the template being edited, or the defaults for a new one.
 *
 * @param {Object|null} template Template to edit, or null to create one.
 * @return {Object} Initial form state.
 */
const getInitialFormState = ( template ) => {
	if ( ! template ) {
		return NEW_TEMPLATE_STATE;
	}

	let visibleColumns = DEFAULT_VISIBLE_COLUMNS;
	if ( Array.isArray( template.visible_columns ) ) {
		visibleColumns = template.visible_columns.length
			? template.visible_columns
			: DEFAULT_VISIBLE_COLUMNS;
	} else if ( typeof template.visible_columns === 'string' ) {
		const parsed = template.visible_columns.split( ',' ).filter( Boolean );
		visibleColumns = parsed.length ? parsed : DEFAULT_VISIBLE_COLUMNS;
	}

	return { ...template, visible_columns: visibleColumns };
};

// Lives inside the Drawer, which only mounts its content while open: the state below is
// seeded from the template on every open, so the first frame already shows the right data
// (syncing it in an effect rendered the previous template first).
const EmailTemplateForm = ( { template, onSave } ) => {
	const { canAccessProFeatures } = useProAccess();
	const { setDirty, markSaved } = useTemplateDrawer();
	const [ formState, setFormState ] = useState( () =>
		getInitialFormState( template )
	);
	// What was loaded or last saved, to tell whether closing would lose anything.
	const [ savedState, setSavedState ] = useState( formState );
	const [ isSubmitting, setIsSubmitting ] = useState( false );
	const [ errors, setErrors ] = useState( {} );

	useEffect( () => {
		setDirty( isFormDirty( formState, savedState ) );
	}, [ formState, savedState ] );

	const handleChange = ( name, value ) => {
		setFormState( ( prev ) => {
			return { ...prev, [ name ]: value };
		} );

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

		if ( ! formState.email_subject.trim() ) {
			newErrors.email_subject = __(
				'Email subject is required',
				'woo-cart-abandonment-recovery'
			);
		}

		if ( ! formState.email_body.trim() ) {
			newErrors.email_body = __(
				'Email body is required',
				'woo-cart-abandonment-recovery'
			);
		}
		if ( formState.email_frequency < 1 ) {
			newErrors.email_frequency = __(
				'Time should be minimum 1 min.',
				'woo-cart-abandonment-recovery'
			);
		}

		// Validate email rule engine
		if ( canAccessProFeatures() ) {
			const ruleEngineError = getRuleEngineError(
				formState?.enable_email_rule_engine,
				formState.email_rule_engine
			);
			if ( ruleEngineError ) {
				newErrors.email_rule_engine = ruleEngineError;
			}
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
		formData.append( 'wcf_email_subject', formState.email_subject );
		formData.append( 'wcf_email_body', formState.email_body );
		formData.append( 'wcf_email_frequency', formState.email_frequency );
		formData.append(
			'wcf_email_frequency_unit',
			formState.email_frequency_unit
		);
		formData.append(
			'wcf_activate_email_template',
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
		formData.append(
			'wcf_use_woo_email_style',
			formState.use_woo_email_style ? '1' : ''
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
			'wcf_modify_product_table',
			formState.modify_product_table ? '1' : ''
		);
		formData.append(
			'wcf_product_image_size',
			formState.product_image_size || 'medium'
		);
		formData.append(
			'wcf_show_prices_with_tax',
			formState.show_prices_with_tax ? '1' : ''
		);
		formData.append(
			'wcf_visible_columns',
			Array.isArray( formState.visible_columns )
				? formState.visible_columns.join( ',' )
				: formState.visible_columns || ''
		);
		formData.append(
			'wcf_admin_email_copy_status',
			formState.admin_email_copy_status ? '1' : ''
		);
		formData.append(
			'wcf_admin_email_copy_type',
			formState.admin_email_copy_type || 'bcc'
		);
		formData.append(
			'wcf_admin_email_copy_address',
			formState.admin_email_copy_address || ''
		);

		// Add rule engine fields
		if ( canAccessProFeatures() ) {
			formData.append(
				'wcf_enable_email_rule_engine',
				formState?.enable_email_rule_engine ? '1' : ''
			);
			formData.append(
				'wcf_email_rule_engine',
				JSON.stringify( formState?.email_rule_engine || [] )
			);
		}

		// Add template ID if editing
		if ( template?.id ) {
			formData.append( 'id', template.id );
			formData.append( 'action', 'wcar_update_email_template' );
			formData.append(
				'security',
				cart_abandonment_admin?.update_email_template_nonce
			);
		} else {
			formData.append( 'action', 'wcar_save_email_template' );
			formData.append(
				'security',
				cart_abandonment_admin?.save_email_template_nonce
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
						: __( 'New Email Template', 'woo-cart-abandonment-recovery' )
				}
				isSubmitting={ isSubmitting }
				onSave={ handleSubmit }
			/>
			<Drawer.Body className="overflow-x-hidden">
				<SettingsDrawerBody
					formState={ formState }
					handleChange={ handleChange }
					errors={ errors }
					editorInitDelay={ EDITOR_INIT_DELAY_MS }
				/>
			</Drawer.Body>
		</>
	);
};

const EmailTemplatesDrawer = ( { open, setOpen, template, onSave } ) => (
	<TemplateDrawerShell open={ open } setOpen={ setOpen }>
		<EmailTemplateForm
			key={ template?.id ?? 'new' }
			template={ template }
			onSave={ onSave }
		/>
	</TemplateDrawerShell>
);

export default EmailTemplatesDrawer;
