import { useEffect, useRef, useState } from '@wordpress/element';
import { Topbar, ProgressSteps, Label, Button } from '@bsf/force-ui';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { __, sprintf } from '@wordpress/i18n';
import apiFetch from '@wordpress/api-fetch';

import WcarLogo from '@Images/wcar-icon.svg';
import ConfirmDialog from '@Components/common/ConfirmDialog';
import { useOnboardingNavigation } from './hooks';
import { OnboardingProvider, useOnboardingContext } from './OnboardingContext';
import { writePersistedState } from './Persist';
import OnboardingErrorBoundary from './ErrorBoundary';
import ONBOARDING_ROUTES_CONFIG from './onboardingRoutesConfig';
import Welcome from './screens/Welcome';

const TOTAL_STEPS = ONBOARDING_ROUTES_CONFIG.length;

const NavBar = ( { currentStep, currentStepNumber, isLastStep } ) => {
	const { state, markOnboardingComplete } = useOnboardingContext();
	const [ showExitConfirm, setShowExitConfirm ] = useState( false );
	const [ isExiting, setIsExiting ] = useState( false );

	// Full reload to the dashboard so it re-localizes onboarding_completed/skipped/resume_step.
	const redirectToDashboard = () => {
		window.location.href = cart_abandonment_admin.admin_url;
	};

	// Records where they left off, so the dashboard can offer "Resume Setup" at the
	// right step. Never called from the last step: onboarding is already complete by
	// then, and this would wrongly mark a finished setup as skipped.
	const handleExit = () => {
		setIsExiting( true );

		// Flush past the debounce: this navigates away from the page, and whatever
		// was typed in the last fraction of a second is still worth having when the
		// merchant resumes.
		writePersistedState( state );

		apiFetch( {
			url: cart_abandonment_admin.onboarding.exitUrl,
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify( {
				exit_step: currentStep?.analyticsSlug,
			} ),
		} )
			.catch( () => {} ) // Best-effort: the dashboard redirect below happens regardless.
			.finally( redirectToDashboard );
	};

	const exitButtonLabel = __(
		'Exit Guided Setup',
		'woo-cart-abandonment-recovery'
	);

	// Belt and suspenders: completeOnboarding() already clears the snapshot on
	// success, so this is normally a no-op — but it means Done never leaves a
	// stale snapshot behind regardless of how the merchant got here.
	const handleExitFromDone = () => {
		markOnboardingComplete();
		redirectToDashboard();
	};

	if ( isLastStep ) {
		return (
			<Topbar className="p-5 bg-primary-background">
				<TopbarColumns
					currentStepNumber={ currentStepNumber }
					isLastStep
				>
					<Button
						icon={ <XMarkIcon className="h-4 w-4" /> }
						size="xs"
						variant="ghost"
						iconPosition="right"
						onClick={ handleExitFromDone }
					>
						{ exitButtonLabel }
					</Button>
				</TopbarColumns>
			</Topbar>
		);
	}

	return (
		<Topbar className="p-5 bg-primary-background">
			<TopbarColumns
				currentStepNumber={ currentStepNumber }
				isLastStep={ false }
			>
				<ConfirmDialog
					open={ showExitConfirm }
					setOpen={ setShowExitConfirm }
					trigger={
						<Button
							icon={ <XMarkIcon className="h-4 w-4" /> }
							size="xs"
							variant="ghost"
							iconPosition="right"
						>
							{ exitButtonLabel }
						</Button>
					}
					title={ __(
						'Exit the setup?',
						'woo-cart-abandonment-recovery'
					) }
					description={ __(
						'Answers from steps you already moved past are saved. You can pick up where you left off any time from Dashboard → Quick Access → Resume Setup.',
						'woo-cart-abandonment-recovery'
					) }
					cancelLabel={ __(
						'Continue Setup',
						'woo-cart-abandonment-recovery'
					) }
					confirmLabel={ __(
						'Exit Setup',
						'woo-cart-abandonment-recovery'
					) }
					onConfirm={ handleExit }
					isConfirming={ isExiting }
				/>
			</TopbarColumns>
		</Topbar>
	);
};

/**
 * The logo/stepper/exit-slot layout, shared between the confirm-on-exit and
 * direct-exit variants of the topbar above.
 *
 * @param {Object}  props
 * @param {number}  props.currentStepNumber
 * @param {boolean} props.isLastStep
 * @param {Object}  props.children          The exit control (plain button or Dialog-wrapped).
 */
const TopbarColumns = ( { currentStepNumber, isLastStep, children } ) => (
	<>
		{ /* Equal outer columns keep the stepper on the true viewport centre. */ }
		<Topbar.Left className="flex-1">
			<Topbar.Item>
				<img
					src={ WcarLogo }
					alt="Cart Abandonment Recovery Logo"
					aria-label="Cart Abandonment Recovery Logo"
					className="h-8 w-8"
				/>
			</Topbar.Item>
		</Topbar.Left>
		<Topbar.Middle align="center" className="basis-0">
			<Topbar.Item className="lg:hidden">
				<Label size="sm" className="whitespace-nowrap font-medium">
					{ sprintf(
						/* translators: 1: current step number, 2: total steps. */
						__(
							'Step %1$d of %2$d',
							'woo-cart-abandonment-recovery'
						),
						currentStepNumber,
						TOTAL_STEPS
					) }
				</Label>
			</Topbar.Item>
			<Topbar.Item className="hidden lg:flex">
				<ProgressSteps
					completedVariant="number"
					currentStep={
						isLastStep ? TOTAL_STEPS + 1 : currentStepNumber
					}
					size="md"
					type="inline"
					variant="number"
				>
					{ ONBOARDING_ROUTES_CONFIG.map( ( route ) => (
						<ProgressSteps.Step
							key={ route.url }
							size="md"
							labelText={ route.label }
						/>
					) ) }
				</ProgressSteps>
			</Topbar.Item>
		</Topbar.Middle>
		<Topbar.Right className="flex-1 justify-end">
			<Topbar.Item>{ children }</Topbar.Item>
		</Topbar.Right>
	</>
);

const OnboardingLayoutContent = () => {
	const { getCurrentStep, getCurrentStepNumber } = useOnboardingNavigation();
	const currentStep = getCurrentStep();
	const currentStepNumber = getCurrentStepNumber();
	const isLastStep = currentStepNumber === TOTAL_STEPS;

	// Where focus goes when the step changes, so a screen reader announces the new
	// step instead of leaving focus on a button that just unmounted.
	const stepRef = useRef( null );
	// Not on first paint: the merchant has just arrived, and yanking focus into the
	// card would throw away wherever the browser (or a direct link) put it.
	const hasRendered = useRef( false );

	useEffect( () => {
		window.scrollTo( { top: 0, behavior: 'auto' } );

		if ( ! hasRendered.current ) {
			hasRendered.current = true;
			return;
		}

		stepRef.current?.focus( { preventScroll: true } );
	}, [ currentStep?.url ] );

	return (
		<div className="bg-primary-background w-full min-h-screen pb-16">
			<NavBar
				currentStep={ currentStep }
				currentStepNumber={ currentStepNumber }
				isLastStep={ isLastStep }
			/>
			<main className="px-4 md:px-0">
				<div
					className={ `relative box-border mx-auto p-5 sm:p-8 mt-6 md:mt-10 border border-solid border-border-subtle bg-background-primary rounded-xl shadow-sm flex flex-col gap-6 ${
						currentStep?.width || 'md:w-[44rem]'
					}` }
				>
					{ /* A labelled region so moving focus here on a step change
					     announces which step it is. */ }
					<div
						ref={ stepRef }
						tabIndex={ -1 }
						role="region"
						aria-label={ sprintf(
							/* translators: 1: current step number, 2: total steps, 3: step name. */
							__(
								'Step %1$d of %2$d: %3$s',
								'woo-cart-abandonment-recovery'
							),
							currentStepNumber,
							TOTAL_STEPS,
							currentStep?.label || ''
						) }
						className="outline-none flex flex-col gap-6"
					>
						{ currentStep?.component || <Welcome /> }
					</div>
				</div>
			</main>
		</div>
	);
};

const OnboardingLayout = () => {
	return (
		<OnboardingErrorBoundary>
			<OnboardingProvider>
				<OnboardingLayoutContent />
			</OnboardingProvider>
		</OnboardingErrorBoundary>
	);
};

export default OnboardingLayout;
