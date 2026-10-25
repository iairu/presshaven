import { useRef, useCallback } from 'react';
import debounce from 'lodash.debounce';
import { ActionTypes, doApiFetch, useStateValue } from '@Store';

/**
 * Custom hook to dispatch debounced setting updates.
 *
 * @param {Function} dispatch   React context dispatch method.
 * @param {string}   optionName Option key being updated.
 * @param {Function} onSuccess  Success callback function.
 * @param {number}   delay      Debounce delay in ms.
 * @param {boolean}  showToast  Whether to show toast notifications.
 * @return {Function} callback
 */
const useDebounceDispatch = (
	dispatch,
	optionName,
	onSuccess,
	delay = 400,
	showToast = false
) => {
	const [ state ] = useStateValue();

	// The debounced function outlives a render, so it reads these instead of closing over them.
	const latest = useRef( {} );
	latest.current = { dispatch, optionName, onSuccess, showToast };

	// The last value the server accepted, so a refused save can put the field back. It stays
	// undefined for an option that was never saved, which puts the field back to unset.
	const confirmed = useRef( {
		value: state?.settingsData?.values?.[ optionName ],
	} );

	// Saves are numbered so responses that come back out of order can't undo a newer save.
	const lastSent = useRef( 0 );
	const lastConfirmed = useRef( 0 );

	const debounced = useRef( null );
	if ( ! debounced.current ) {
		debounced.current = debounce( ( value ) => {
			const current = latest.current;
			lastSent.current += 1;
			const request = lastSent.current;

			// Update the state with the new value
			current.dispatch( {
				type: ActionTypes.UPDATE_SETTINGS_DATA,
				payload: {
					option: current.optionName,
					value,
				},
			} );
			const formData = new window.FormData();

			// Set the full option name in the form data
			formData.append( 'option_name', current.optionName );
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

			const ajaxUrl = cart_abandonment_admin?.ajax_url || window.ajaxurl;

			// A newer save is on its way and its own response decides what the field shows.
			const revert = () => {
				if ( request !== lastSent.current ) {
					return;
				}
				current.dispatch( {
					type: ActionTypes.UPDATE_SETTINGS_DATA,
					payload: {
						option: current.optionName,
						value: confirmed.current.value,
					},
				} );
			};

			doApiFetch(
				ajaxUrl,
				formData,
				'POST',
				( response ) => {
					if ( response?.success === false ) {
						revert();
						return;
					}
					if ( request > lastConfirmed.current ) {
						lastConfirmed.current = request;
						confirmed.current.value = value;
					}
					if ( current.onSuccess ) {
						current.onSuccess();
					}
				},
				revert,
				true,
				current.showToast
			).catch( () => {
				// doApiFetch has already reported the failure through onError.
			} );
		}, delay );
	}

	return useCallback(
		( value ) => debounced.current( value ),
		[ debounced ]
	);
};

export default useDebounceDispatch;
