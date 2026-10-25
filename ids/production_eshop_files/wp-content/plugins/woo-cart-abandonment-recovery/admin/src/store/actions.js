import apiFetch from '@wordpress/api-fetch';
import { __ } from '@wordpress/i18n';
import { toast } from '@bsf/force-ui';

/**
 * Common API fetch function to handle API requests
 *
 * @param {string}   path      - API endpoint path
 * @param {Object}   data      - Data to send in the request body
 * @param {string}   method    - HTTP method (default: 'POST')
 * @param {Function} onSuccess - Success callback function
 * @param {Function} onError   - Error callback function
 * @param {boolean}  useUrl    - Whether to use URL for the request
 * @param {boolean}  showToast - Whether to show a toast notification
 * @return {Promise} API fetch promise
 */
export async function doApiFetch(
	path,
	data = {},
	method = 'POST',
	onSuccess = () => {},
	onError = () => {},
	useUrl = false,
	showToast = false
) {
	try {
		// Prepare request options.
		const fetchOptions = {
			method,
		};

		if ( useUrl ) {
			// For regular AJAX calls
			fetchOptions.url = path;
			fetchOptions.body = data;
		} else {
			// For WordPress API calls
			fetchOptions.path = path;
			if ( data && ( method === 'POST' || method === 'PUT' ) ) {
				fetchOptions.data = data;
			}
		}

		const apiResponse = await apiFetch( fetchOptions ).then(
			( response ) => {
				if ( onSuccess ) {
					onSuccess( response );
				}
				if ( showToast ) {
					// WordPress answers a refused request with HTTP 200 and success:false.
					if ( response?.success === false ) {
						toast.error(
							__( 'Not saved', 'woo-cart-abandonment-recovery' ),
							{
								description:
									response.data?.message ||
									__(
										'The setting could not be saved. Reload the page and try again.',
										'woo-cart-abandonment-recovery'
									),
							}
						);
						return;
					}
					toast.success(
						__( 'Saved', 'woo-cart-abandonment-recovery' ),
						{
							description: __(
								'Your change has been saved.',
								'woo-cart-abandonment-recovery'
							),
						}
					);
				}
			}
		);

		return apiResponse;
	} catch ( error ) {
		console.error( 'API Error:', error );
		if ( showToast ) {
			toast.error( __( 'Request failed', 'woo-cart-abandonment-recovery' ), {
				description: __(
					'Something went wrong. Check your connection and try again.',
					'woo-cart-abandonment-recovery'
				),
			} );
		}
		if ( onError ) {
			onError( error );
		}
		throw error;
	}
}
