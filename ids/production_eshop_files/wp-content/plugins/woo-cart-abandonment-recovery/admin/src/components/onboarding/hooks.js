import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import apiFetch from '@wordpress/api-fetch';
import { __ } from '@wordpress/i18n';
import { useStateValue, doApiFetch } from '@Store';
import ConditionsHelper from '@Utils/conditions';
import ONBOARDING_ROUTES_CONFIG from './onboardingRoutesConfig';

/**
 * This hook will return functions that will handle the navigation of the onboarding process.
 * It will be used to handle the back and continue buttons.
 */
export const useOnboardingNavigation = () => {
	const navigate = useNavigate();
	const urlParams = new URLSearchParams( useLocation().search );
	const currentRoute = urlParams.get( 'step' ) || 'welcome';
	const BASE_PATH =
		'?page=woo-cart-abandonment-recovery&path=onboarding&step=';

	const getNextRoute = ( currentPath ) => {
		const currentIndex = ONBOARDING_ROUTES_CONFIG.findIndex(
			( route ) => route.url === currentPath
		);

		return ONBOARDING_ROUTES_CONFIG[ currentIndex + 1 ].url;
	};

	const getPreviousRoute = ( currentPath ) => {
		const currentIndex = ONBOARDING_ROUTES_CONFIG.findIndex(
			( route ) => route.url === currentPath
		);

		return ONBOARDING_ROUTES_CONFIG[ currentIndex - 1 ].url;
	};

	const navigateToNextRoute = ( { replace = false } = {} ) => {
		const nextRoute = getNextRoute( currentRoute );
		navigate(
			{
				search: BASE_PATH + nextRoute,
			},
			{ replace }
		);
	};

	const navigateToPreviousRoute = () => {
		const previousRoute = getPreviousRoute( currentRoute );
		navigate( {
			search: BASE_PATH + previousRoute,
		} );
	};

	const getCurrentStepNumber = () => {
		const currentIndex = ONBOARDING_ROUTES_CONFIG.findIndex(
			( route ) => route.url === currentRoute
		);

		return currentIndex + 1;
	};

	const getCurrentStep = () => {
		return ONBOARDING_ROUTES_CONFIG.find(
			( route ) => route.url === currentRoute
		);
	};

	// Persists onboarding state (user details, plugin selections) and marks onboarding complete.
	const completeOnboarding = ( state ) =>
		apiFetch( {
			url: cart_abandonment_admin.onboarding.ajaxUrl,
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
			},
			body: JSON.stringify( state ),
		} );

	return {
		getNextRoute,
		getPreviousRoute,
		navigateToNextRoute,
		navigateToPreviousRoute,
		getCurrentStepNumber,
		getCurrentStep,
		completeOnboarding,
	};
};

/**
 * Local, unsaved answers for one onboarding settings step.
 *
 * Recovery Settings and Follow Up Channels both render fields the main Settings screen
 * already knows how to autosave on every change. The wizard doesn't want that: a merchant
 * moving through six steps shouldn't trigger a silent request (and a toast) per toggle. This
 * collects what they touch on the current step and hands back one `saveAndAdvance` to fire
 * when they press Next, so the step has one loading state and one point of failure instead
 * of several.
 *
 * @param {string} stepSlug Key into `cart_abandonment_admin.settings_fields.onboarding`.
 * @return {Object} Field config for the step, a `valueFor`/`handleChange` pair for
 *                   RenderFields, and `saveAndAdvance` to hand to NavigationButtons' `onNext`.
 */
export const useOnboardingFieldsStep = ( stepSlug ) => {
	const [ state, dispatch ] = useStateValue();
	const settingsData = state?.settingsData || {};
	const fieldSettings = settingsData?.fields?.onboarding?.[ stepSlug ] || {};
	const settingsValues = settingsData?.values || {};
	const conditions = new ConditionsHelper();

	// Only what the merchant actually touched on this step — everything else keeps reading
	// from the live settings, so a step with no changes has nothing to save.
	const [ draft, setDraft ] = useState( {} );
	const [ isSaving, setIsSaving ] = useState( false );
	const [ saveError, setSaveError ] = useState( '' );
	// Message per field whose current value can't be saved, keyed by option name.
	const [ fieldErrors, setFieldErrors ] = useState( {} );

	const valueFor = ( data ) =>
		draft[ data.name ] ?? settingsValues[ data.name ] ?? data.value ?? '';

	// Toggles report booleans, but these answers go straight into options that the backend
	// only treats as enabled when they are exactly 'on' (a boolean would be stored as
	// 'true'/'false'), so convert them here.
	const handleChange = ( name, value ) => {
		const stored = 'boolean' === typeof value ? ( value ? 'on' : '' ) : value;
		setDraft( ( prev ) => ( { ...prev, [ name ]: stored } ) );
		setSaveError( '' );
	};

	const handleValidity = ( name, message ) =>
		setFieldErrors( ( prev ) => {
			if ( ( prev[ name ] || '' ) === message ) {
				return prev;
			}
			const next = { ...prev };
			if ( message ) {
				next[ name ] = message;
			} else {
				delete next[ name ];
			}
			return next;
		} );

	/**
	 * Save whatever changed on this step, then run `onDone`.
	 *
	 * Nothing changed is not a failure — Next still has to advance when the merchant left
	 * every field at its default.
	 *
	 * @param {Function} onDone Called once the save succeeds, or there was nothing to save.
	 */
	const saveAndAdvance = ( onDone ) => {
		// A value that can't be saved keeps the merchant here with its message showing,
		// rather than moving on with the old value behind their back.
		if ( Object.keys( fieldErrors ).length ) {
			document.querySelector( '[aria-invalid="true"]' )?.focus();
			return;
		}

		const changedOptions = Object.keys( draft );

		if ( ! changedOptions.length ) {
			onDone();
			return;
		}

		setIsSaving( true );
		setSaveError( '' );

		const save = ( name ) =>
			new Promise( ( resolve, reject ) => {
				const value = draft[ name ];
				const formData = new window.FormData();

				formData.append( 'option_name', name );
				if ( Array.isArray( value ) ) {
					value.forEach( ( v ) => formData.append( 'value[]', v ) );
				} else {
					formData.append( 'value', value );
				}
				formData.append( 'action', 'wcar_save_setting' );
				formData.append(
					'security',
					cart_abandonment_admin?.save_setting_nonce
				);

				doApiFetch(
					cart_abandonment_admin?.ajax_url,
					formData,
					'POST',
					// admin-ajax answers a refusal with HTTP 200 and success:false, which
					// apiFetch resolves normally — without this check a rejected save
					// would still advance to the next step as if it had saved.
					( response ) =>
						false === response?.success
							? reject( new Error( response?.data?.message || '' ) )
							: resolve(),
					reject,
					true,
					false
				).catch( () => {} ); // Rejection already reaches us through `reject`.
			} );

		Promise.all( changedOptions.map( save ) )
			.then( () => {
				// Mirror the saved values into global state so Back reads what was just
				// saved instead of the page-load value the cleared draft falls back to.
				changedOptions.forEach( ( name ) => {
					dispatch( {
						type: 'UPDATE_SETTINGS_DATA',
						payload: { option: name, value: draft[ name ] },
					} );
				} );
				setIsSaving( false );
				setDraft( {} );
				onDone();
			} )
			.catch( () => {
				setIsSaving( false );
				setSaveError(
					__(
						'Check your connection and try again.',
						'woo-cart-abandonment-recovery'
					)
				);
			} );
	};

	return {
		fieldSettings,
		settingsValues,
		conditions,
		valueFor,
		handleChange,
		saveAndAdvance,
		isSaving,
		saveError,
		fieldErrors,
		handleValidity,
	};
};
