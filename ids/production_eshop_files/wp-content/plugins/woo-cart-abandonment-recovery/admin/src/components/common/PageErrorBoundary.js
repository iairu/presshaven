import { Component } from '@wordpress/element';
import { Button } from '@bsf/force-ui';
import { __ } from '@wordpress/i18n';

import SectionWrapper from '@Components/common/SectionWrapper';

/**
 * Catches a render error in one screen, so the header and the rest of the app stay usable.
 *
 * Without this a throw anywhere in a screen unmounts the whole app and leaves a blank page.
 *
 * @param {Object} props
 * @param {string} props.resetKey Changes whenever the screen changes, which clears the error so
 *                                the next screen gets a fresh try.
 */
class PageErrorBoundary extends Component {
	constructor( props ) {
		super( props );
		this.state = { hasError: false };
	}

	static getDerivedStateFromError() {
		return { hasError: true };
	}

	componentDidUpdate( previousProps ) {
		if ( this.state.hasError && previousProps.resetKey !== this.props.resetKey ) {
			this.setState( { hasError: false } );
		}
	}

	componentDidCatch( error ) {
		// eslint-disable-next-line no-console
		console.error( 'Cart Abandonment Recovery screen failed to render:', error );
	}

	render() {
		if ( ! this.state.hasError ) {
			return this.props.children;
		}

		return (
			<div className="p-4 md:p-8">
				<SectionWrapper className="flex flex-col gap-4 items-start">
					<h1 className="m-0 text-xl font-semibold text-text-primary">
						{ __(
							'This screen hit a problem',
							'woo-cart-abandonment-recovery'
						) }
					</h1>
					<p className="m-0 text-sm text-text-secondary">
						{ __(
							'Nothing has been changed on your store. Reload to try again, or go back to the dashboard.',
							'woo-cart-abandonment-recovery'
						) }
					</p>
					<div className="flex flex-col sm:flex-row gap-3">
						<Button
							variant="primary"
							size="sm"
							onClick={ () => window.location.reload() }
						>
							{ __( 'Reload', 'woo-cart-abandonment-recovery' ) }
						</Button>
						<Button
							variant="outline"
							size="sm"
							onClick={ () => {
								window.location.href =
									cart_abandonment_admin.admin_url;
							} }
						>
							{ __(
								'Go To Dashboard',
								'woo-cart-abandonment-recovery'
							) }
						</Button>
					</div>
				</SectionWrapper>
			</div>
		);
	}
}

export default PageErrorBoundary;
