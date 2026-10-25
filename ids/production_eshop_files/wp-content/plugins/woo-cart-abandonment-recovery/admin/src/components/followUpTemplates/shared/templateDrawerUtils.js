import { __ } from '@wordpress/i18n';

const isEmptyStringOrArray = ( val ) =>
	( typeof val === 'string' && val.trim() === '' ) ||
	( Array.isArray( val ) && val.length === 0 );

// Fields that put a full-width control (a text box, a select, or a box and its button) under
// its title. The wrapper spaces a title and its control 20px apart from the lg breakpoint up,
// which suits a control beside the title but is a wide gap above one underneath it.
const STACKED_INPUT_TYPES = [
	'text',
	'subject_field',
	'email',
	'textarea',
	'textarea_dropdown',
	'test_email',
	'test_message',
	'product-search',
	'dynamic-select',
	'multi-select',
];

/**
 * Extra classes for a field's card in a template drawer.
 *
 * Field titles are 14px medium here, a step down from the settings pages, to suit the narrower
 * panel.
 *
 * @param {string} type Field type from the field definition.
 * @return {string} Classes to add to the card.
 */
export const getFieldCardClass = ( type ) =>
	[
		'[&_label]:text-sm [&_label_*]:text-sm [&_label]:font-medium',
		STACKED_INPUT_TYPES.includes( type ) && 'lg:[&>div>div]:gap-2',
	]
		.filter( Boolean )
		.join( ' ' );

/**
 * A field definition as the template drawers show it.
 *
 * The definitions come from PHP (and, for SMS and WhatsApp, from the Pro plugin), so the small
 * copy fixes that only suit the drawers are applied here instead.
 *
 * @param {string} field Field key.
 * @param {Object} data  Field definition.
 * @return {Object} The definition, with a placeholder or help text added where one was missing.
 */
export const getDrawerFieldData = ( field, data ) => {
	// Placeholders follow the subject's wording: "Enter the …".
	if ( field === 'template_name' && ! data.placeholder ) {
		return {
			...data,
			placeholder: __(
				'Enter the template name',
				'woo-cart-abandonment-recovery'
			),
		};
	}

	if ( field === 'admin_email_copy_address' && ! data.placeholder ) {
		return {
			...data,
			placeholder: __(
				'Enter the email address',
				'woo-cart-abandonment-recovery'
			),
		};
	}

	// The subject's one-line instruction reads better inside the box than above it.
	if ( field === 'email_subject' && ! data.placeholder ) {
		return {
			...data,
			desc: '',
			placeholder: data.desc
				? data.desc.replace( /\.$/, '' )
				: __(
					'Enter the email subject',
					'woo-cart-abandonment-recovery'
				),
		};
	}

	// The only field in its row with neither help text nor a one-line control to line up with.
	if ( field === 'coupon_expiry' && ! data.desc ) {
		return {
			...data,
			desc: __(
				'How long the coupon stays valid after it is created.',
				'woo-cart-abandonment-recovery'
			),
		};
	}

	return data;
};

/**
 * Shorten a template name for the drawer title.
 *
 * @param {string} text      Text to shorten.
 * @param {number} maxLength Longest length kept before the ellipsis.
 * @return {string} The text, cut with an ellipsis when it is longer than `maxLength`.
 */
export const truncateText = ( text, maxLength = 60 ) =>
	text.length > maxLength ? text.slice( 0, maxLength ) + '...' : text;

/**
 * Whether the form differs from what was last loaded or saved.
 *
 * @param {Object} current Current form state.
 * @param {Object} saved   State it started from, or was last saved as.
 * @return {boolean} True when there are unsaved changes.
 */
export const isFormDirty = ( current, saved ) =>
	JSON.stringify( current ) !== JSON.stringify( saved );

/**
 * Validation message for a template's rule engine, or null when it is off or complete.
 *
 * @param {string|boolean} enabled Value of the enable toggle.
 * @param {Array|string}   rules   Rule groups, or their JSON.
 * @return {string|null} Message to show, or null when valid.
 */
export const getRuleEngineError = ( enabled, rules ) => {
	if ( ! enabled || enabled === '0' ) {
		return null;
	}

	let groups = rules || [];
	if ( typeof groups === 'string' ) {
		try {
			groups = JSON.parse( groups );
		} catch ( e ) {
			return __(
				'Invalid JSON in rule engine',
				'woo-cart-abandonment-recovery'
			);
		}
	}

	const hasIncompleteRule = groups.some(
		( group ) =>
			group.rules &&
			group.rules.some(
				( rule ) =>
					isEmptyStringOrArray( rule.condition ) ||
					isEmptyStringOrArray( rule.value ) ||
					isEmptyStringOrArray( rule.operator )
			)
	);

	if ( groups.length === 0 || hasIncompleteRule ) {
		return __(
			'Missing fields in rule: condition, operator, or value.',
			'woo-cart-abandonment-recovery'
		);
	}

	return null;
};

/**
 * Move focus to the first field that failed validation, so a keyboard or screen reader user
 * lands on the problem instead of staying on the Save button.
 *
 * @param {Object} errors Validation messages keyed by field name.
 */
export const focusFirstInvalid = ( errors ) => {
	const panel = document.querySelector( '[role="dialog"][aria-modal="true"]' );
	if ( ! panel ) {
		return;
	}

	for ( const key of Object.keys( errors ) ) {
		if ( key === 'email_body' && window.tinymce?.get( key ) ) {
			window.tinymce.get( key ).focus();
			return;
		}

		const control = panel.querySelector( `[name="${ key }"]` );
		if ( control && control.type !== 'hidden' ) {
			control.focus();
			return;
		}
	}
};
