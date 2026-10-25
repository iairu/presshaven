import { useState } from 'react';
import { createInterpolateElement } from '@wordpress/element';
import { Checkbox, Input } from '@bsf/force-ui';
import { __ } from '@wordpress/i18n';

import Header from '@Components/onboarding/Header';
import NavigationButtons from '@Components/onboarding/NavigationButtons';
import { useOnboardingContext } from '../OnboardingContext';
import { useOnboardingNavigation } from '../hooks';

// Same pattern used by EmailField/TestEmail elsewhere in this app, so an address
// accepted on one screen isn't rejected on another.
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * The fields this screen validates, in the order they are read.
 *
 * The order matters twice over: it decides which field the form jumps to when
 * more than one is invalid, and it has to match the visual order for that jump
 * to feel like it goes backwards to the problem.
 */
const FIELDS = {
	user_detail_firstname: {
		id: 'wcar-onboarding-first-name',
		validate: ( value ) => {
			if ( ! value || '' === value.trim() ) {
				return __(
					'Enter your first name.',
					'woo-cart-abandonment-recovery'
				);
			}
			return '';
		},
	},
	user_detail_lastname: {
		id: 'wcar-onboarding-last-name',
		validate: ( value ) => {
			if ( ! value || '' === value.trim() ) {
				return __(
					'Enter your last name.',
					'woo-cart-abandonment-recovery'
				);
			}
			return '';
		},
	},
	user_detail_email: {
		id: 'wcar-onboarding-email',
		validate: ( value ) => {
			if ( ! value || '' === value.trim() ) {
				return __(
					'Enter an email address.',
					'woo-cart-abandonment-recovery'
				);
			}

			if ( ! EMAIL_PATTERN.test( value ) ) {
				return __(
					"That doesn't look like a valid email address.",
					'woo-cart-abandonment-recovery'
				);
			}

			return '';
		},
	},
};

/**
 * Consent copy with the policy link inline, so the sentence reads as one.
 *
 * Force UI's Label lays its children out with `flex items-center`, so the text
 * and the link would become two side-by-side columns. The wrapper keeps them a
 * single flex item so the sentence flows.
 */
const USAGE_TRACKING_DESCRIPTION = (
	<span className="block">
		{ createInterpolateElement(
			__(
				"We don't collect any personal information, just basic details like your PHP version, admin language, and which features you use. <a>Learn more about what we collect and why.</a>",
				'woo-cart-abandonment-recovery'
			),
			{
				a: (
					// eslint-disable-next-line jsx-a11y/anchor-has-content
					<a
						className="text-field-helper underline hover:text-primary-600"
						href="https://my.cartflows.com/usage-tracking/?utm_source=dashboard&utm_medium=woo-cart-abandonment-recovery&utm_campaign=docs"
						target="_blank"
						rel="noreferrer"
					/>
				),
			}
		) }
	</span>
);

/**
 * Validation copy, at the same size as the field it belongs to.
 *
 * The message takes its own space and pushes what follows down, rather than
 * sitting in a reserved slot that pads the form out even when it is valid.
 *
 * The `id` is what makes the message reachable a second time: `role="alert"`
 * announces it once when it appears, and after that a screen reader only finds
 * it again through the input's `aria-describedby`.
 *
 * @param {Object} props
 * @param {string} props.id      Element id the input points at via aria-describedby.
 * @param {string} props.message Error to show, or an empty string for none.
 */
const FieldError = ( { id, message } ) =>
	message ? (
		<span
			id={ id }
			className="block pt-1 text-sm leading-5 text-support-error"
			role="alert"
		>
			{ message }
		</span>
	) : null;

/**
 * The accessibility props a field needs to describe its own error state.
 *
 * @param {string} field   Key in FIELDS.
 * @param {string} message Current error for that field, if any.
 * @return {Object} Props to spread onto the Input.
 */
const errorProps = ( field, message ) => ( {
	'aria-invalid': !! message,
	'aria-describedby': message ? `${ FIELDS[ field ].id }-error` : undefined,
} );

const UserDetails = () => {
	const { state, dispatch } = useOnboardingContext();
	const { navigateToNextRoute } = useOnboardingNavigation();
	const userDetails = state.userDetails;

	const [ errors, setErrors ] = useState( {} );

	const setFieldError = ( field, message ) =>
		setErrors( ( prev ) => ( { ...prev, [ field ]: message } ) );

	const handleData = ( key, value ) => {
		dispatch( {
			type: 'UPDATE_USER_DATA',
			payload: { option: key, value },
		} );
	};

	const handleChange = ( field ) => ( value ) => {
		handleData( field, value );
		setFieldError( field, '' );
	};

	const handleBlur = ( field ) => ( event ) =>
		setFieldError( field, FIELDS[ field ].validate( event?.target?.value ) );

	const handleNext = () => {
		const next = {};

		Object.keys( FIELDS ).forEach( ( field ) => {
			next[ field ] = FIELDS[ field ].validate( userDetails?.[ field ] );
		} );

		setErrors( next );

		const firstInvalid = Object.keys( FIELDS ).find(
			( field ) => next[ field ]
		);

		if ( firstInvalid ) {
			// Send the cursor to the problem rather than leaving the reader to
			// hunt for it — the footer keeps focus during the press, so this is
			// the first focus change of the click.
			document.getElementById( FIELDS[ firstInvalid ].id )?.focus();
			return;
		}

		// Skip, Back, then Continue with nothing edited: Continue is the answer.
		dispatch( { type: 'CONTINUE_USER_DETAILS' } );
		navigateToNextRoute();
	};

	const handleSkip = () => {
		dispatch( { type: 'SKIP_USER_DETAILS' } );
		navigateToNextRoute();
	};

	// Enter inside any field should advance the step. A <form> only does that on
	// its own when it has a single input or a submit button, and this one has
	// three inputs and a footer that lives outside it.
	const handleSubmit = ( event ) => {
		event.preventDefault();
		handleNext();
	};

	return (
		<>
			<Header
				heading={ __(
					'Setup Recovery Report Emails',
					'woo-cart-abandonment-recovery'
				) }
				subHeading={ __(
					'Get a quick weekly recap of your cart recovery performance, right in your inbox.',
					'woo-cart-abandonment-recovery'
				) }
			/>

			{ /* noValidate: the browser's own bubbles would pre-empt the inline
			     messages and skip the focus jump handleNext does. */ }
			<form
				noValidate
				onSubmit={ handleSubmit }
				className="flex flex-col gap-4"
			>
				<div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-4">
					<div className="flex flex-col">
						<Input
							id="wcar-onboarding-first-name"
							size="md"
							type="text"
							label={ __(
								'First Name',
								'woo-cart-abandonment-recovery'
							) }
							placeholder={ __(
								'Jane',
								'woo-cart-abandonment-recovery'
							) }
							value={ userDetails?.user_detail_firstname || '' }
							error={ !! errors.user_detail_firstname }
							required
							autoComplete="given-name"
							onChange={ handleChange( 'user_detail_firstname' ) }
							onBlur={ handleBlur( 'user_detail_firstname' ) }
							{ ...errorProps(
								'user_detail_firstname',
								errors.user_detail_firstname
							) }
						/>
						<FieldError
							id="wcar-onboarding-first-name-error"
							message={ errors.user_detail_firstname }
						/>
					</div>

					<div className="flex flex-col">
						<Input
							id="wcar-onboarding-last-name"
							size="md"
							type="text"
							label={ __(
								'Last Name',
								'woo-cart-abandonment-recovery'
							) }
							placeholder={ __(
								'Doe',
								'woo-cart-abandonment-recovery'
							) }
							value={ userDetails?.user_detail_lastname || '' }
							error={ !! errors.user_detail_lastname }
							required
							autoComplete="family-name"
							onChange={ handleChange( 'user_detail_lastname' ) }
							onBlur={ handleBlur( 'user_detail_lastname' ) }
							{ ...errorProps(
								'user_detail_lastname',
								errors.user_detail_lastname
							) }
						/>
						<FieldError
							id="wcar-onboarding-last-name-error"
							message={ errors.user_detail_lastname }
						/>
					</div>
				</div>

				<div className="flex flex-col">
					<Input
						id="wcar-onboarding-email"
						size="md"
						type="email"
						label={ __(
							'Your Email',
							'woo-cart-abandonment-recovery'
						) }
						placeholder={ __(
							'you@yourstore.com',
							'woo-cart-abandonment-recovery'
						) }
						value={ userDetails?.user_detail_email || '' }
						error={ !! errors.user_detail_email }
						required
						autoComplete="email"
						onChange={ handleChange( 'user_detail_email' ) }
						onBlur={ handleBlur( 'user_detail_email' ) }
						{ ...errorProps(
							'user_detail_email',
							errors.user_detail_email
						) }
					/>
					<FieldError
						id="wcar-onboarding-email-error"
						message={ errors.user_detail_email }
					/>
				</div>

				<div>
					<Checkbox
						id="wcar-onboarding-usage-optin"
						size="sm"
						checked={ !! userDetails?.wcar_usage_optin }
						onChange={ ( value ) =>
							handleData( 'wcar_usage_optin', value )
						}
						label={ {
							heading: __(
								'Help improve Cart Abandonment Recovery by sharing non-sensitive usage data.',
								'woo-cart-abandonment-recovery'
							),
							description: USAGE_TRACKING_DESCRIPTION,
						} }
					/>
				</div>

				{ /* Gives Enter something to submit; the visible primary lives in
				     the shared footer below, outside this form. */ }
				<button type="submit" className="sr-only" tabIndex={ -1 }>
					{ __( 'Continue', 'woo-cart-abandonment-recovery' ) }
				</button>
			</form>

			<NavigationButtons
				showSkip
				nextLabel={ __( 'Continue', 'woo-cart-abandonment-recovery' ) }
				onNext={ handleNext }
				onSkip={ handleSkip }
			/>
		</>
	);
};

export default UserDetails;
