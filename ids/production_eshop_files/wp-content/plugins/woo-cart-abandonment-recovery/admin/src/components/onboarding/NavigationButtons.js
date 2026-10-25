import { Button, Loader } from '@bsf/force-ui';
import { __ } from '@wordpress/i18n';
import { ChevronLeftIcon, ChevronRightIcon } from '@heroicons/react/24/outline';

import { useOnboardingNavigation } from './hooks';

/**
 * Keep the focused field focused while a footer button is pressed.
 *
 * Blur validation (User Details) inserts its message between mousedown and
 * mouseup, which moves the button out from under the pointer and swallows
 * the click. Suppressing the default mousedown behaviour stops that, so the
 * layout holds still until the click has landed — the click handler still
 * validates everything itself, so nothing is skipped.
 *
 * @param {MouseEvent} event Mousedown on the footer.
 */
const keepFocusOnMouseDown = ( event ) => event.preventDefault();

/**
 * @param {Object}   props
 * @param {boolean}  [props.nextFullWidth] Render a single full-width primary button instead of
 *                                         the Back/Next pair. For entry screens that have
 *                                         nothing to go back to.
 * @param {string}   [props.nextLabel]     Label for the primary button (full-width or not).
 * @param {Function} [props.onNext]        Override Next's default `navigateToNextRoute` — for
 *                                         a step that has to save something first.
 * @param {boolean}  [props.nextLoading]   Put Next in its loading state and disable Back
 *                                         alongside it, while `onNext`'s own save is running.
 * @param {boolean}  [props.showSkip]      Render a ghost Skip button before the primary button.
 * @param {Function} [props.onSkip]        Handler for Skip.
 */
const NavigationButtons = ( {
	nextFullWidth = false,
	nextLabel,
	onNext,
	nextLoading = false,
	showSkip = false,
	onSkip,
} = {} ) => {
	const { getCurrentStepNumber, navigateToNextRoute, navigateToPreviousRoute } =
		useOnboardingNavigation();

	if ( nextFullWidth ) {
		return (
			<Button
				className="w-full"
				variant="primary"
				size="md"
				icon={
					nextLoading ? (
						<Loader
							className="text-flamingo-400 p-0"
							icon={ null }
							size="sm"
							variant="primary"
						/>
					) : undefined
				}
				iconPosition="right"
				onClick={ onNext || navigateToNextRoute }
				disabled={ nextLoading }
			>
				{ nextLabel || __( 'Next', 'woo-cart-abandonment-recovery' ) }
			</Button>
		);
	}

	return (
		// eslint-disable-next-line jsx-a11y/no-static-element-interactions -- mousedown here only suppresses default focus behaviour, it isn't a click target.
		<div
			className="flex justify-between items-center gap-6"
			onMouseDown={ keepFocusOnMouseDown }
		>
			<Button
				icon={ <ChevronLeftIcon className="h-6 w-6" /> }
				onClick={ navigateToPreviousRoute }
				disabled={ 1 === getCurrentStepNumber() || nextLoading }
				variant="outline"
			>
				{ __( 'Back', 'woo-cart-abandonment-recovery' ) }
			</Button>

			<div className="flex justify-end items-center gap-3 ml-auto">
				{ showSkip && (
					<Button
						variant="ghost"
						size="md"
						className="text-text-secondary hover:text-text-primary"
						onClick={ onSkip }
						disabled={ nextLoading }
					>
						{ __( 'Skip', 'woo-cart-abandonment-recovery' ) }
					</Button>
				) }
				<Button
					icon={
						nextLoading ? (
							<Loader
								className="text-flamingo-400 p-0"
								icon={ null }
								size="sm"
								variant="primary"
							/>
						) : (
							<ChevronRightIcon className="h-6 w-6" />
						)
					}
					iconPosition="right"
					onClick={ onNext || navigateToNextRoute }
					variant="primary"
					disabled={ nextLoading }
				>
					{ nextLabel || __( 'Next', 'woo-cart-abandonment-recovery' ) }
				</Button>
			</div>
		</div>
	);
};

export default NavigationButtons;
