import { Component } from '@wordpress/element';
import { Button } from '@bsf/force-ui';
import { __ } from '@wordpress/i18n';

/**
 * Catches a render error in any onboarding step.
 *
 * Without this a throw anywhere in the wizard leaves the merchant on a blank
 * white admin page with no way out.
 */
class OnboardingErrorBoundary extends Component {
	constructor( props ) {
		super( props );
		this.state = { hasError: false };
	}

	static getDerivedStateFromError() {
		return { hasError: true };
	}

	componentDidCatch( error ) {
		// eslint-disable-next-line no-console
		console.error( 'Cart Abandonment Recovery onboarding failed to render:', error );
	}

	render() {
		if ( ! this.state.hasError ) {
			return this.props.children;
		}

		return (
			<div className="bg-primary-background w-full min-h-screen pb-16">
				<div className="md:w-[36rem] box-border mx-auto p-5 sm:p-8 mt-6 md:mt-10 border border-solid border-border-subtle bg-background-primary rounded-xl shadow-sm flex flex-col gap-4">
					<h1 className="m-0 text-xl font-semibold text-text-primary">
						{ __(
							'The setup wizard hit a problem',
							'woo-cart-abandonment-recovery'
						) }
					</h1>
					<p className="m-0 text-sm text-text-secondary">
						{ __(
							'Nothing has been changed on your store. You can configure everything from the settings screen instead, or reload to try the wizard again.',
							'woo-cart-abandonment-recovery'
						) }
					</p>
					<div className="flex flex-col sm:flex-row gap-3">
						<Button
							variant="primary"
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
						<Button
							variant="outline"
							size="sm"
							onClick={ () => window.location.reload() }
						>
							{ __(
								'Reload And Retry',
								'woo-cart-abandonment-recovery'
							) }
						</Button>
					</div>
				</div>
			</div>
		);
	}
}

export default OnboardingErrorBoundary;
