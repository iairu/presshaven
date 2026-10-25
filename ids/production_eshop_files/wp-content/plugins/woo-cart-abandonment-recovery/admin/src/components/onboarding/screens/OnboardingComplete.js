import { Button, Label } from '@bsf/force-ui';
import { __ } from '@wordpress/i18n';
import {
	CheckIcon,
	ArrowRightIcon,
	ArrowTopRightOnSquareIcon,
} from '@heroicons/react/24/outline';

import Header from '@Components/onboarding/Header';

const UNLOCKED = [
	{
		heading: __(
			'Recover lost sales automatically',
			'woo-cart-abandonment-recovery'
		),
		description: __(
			'by reminding shoppers to complete their purchase.',
			'woo-cart-abandonment-recovery'
		),
	},
	{
		heading: __( 'Increase conversions', 'woo-cart-abandonment-recovery' ),
		description: __(
			'with timely follow-ups via Emails.',
			'woo-cart-abandonment-recovery'
		),
	},
	{
		heading: __(
			'Turn abandoned carts into revenue',
			'woo-cart-abandonment-recovery'
		),
		description: __(
			'without any manual effort.',
			'woo-cart-abandonment-recovery'
		),
	},
];

const NEXT_STEPS = [
	{
		label: __(
			'Customize your follow-up email templates',
			'woo-cart-abandonment-recovery'
		),
		path: 'follow-up-templates',
	},
	{
		label: __(
			'Review your recovery settings',
			'woo-cart-abandonment-recovery'
		),
		path: 'settings',
	},
	{
		label: __(
			'See how your follow-ups are performing',
			'woo-cart-abandonment-recovery'
		),
		path: 'follow-up',
	},
];

const OnboardingComplete = () => {
	// Full reload so the dashboard re-localizes with the completed onboarding flag.
	const redirectToDashboard = () => {
		window.location.href = cart_abandonment_admin.admin_url;
	};

	const nextStepsLabel =
		1 === NEXT_STEPS.length
			? __( 'Recommended Next Step:', 'woo-cart-abandonment-recovery' )
			: __( 'Recommended Next Steps:', 'woo-cart-abandonment-recovery' );

	return (
		<>
			<Header
				size="lg"
				heading={ __(
					"You're Good to Go! 🚀",
					'woo-cart-abandonment-recovery'
				) }
				subHeading={ __(
					'Great job! With Cart Abandonment Recovery active, your store is ready to start recovering the lost revenue automatically.',
					'woo-cart-abandonment-recovery'
				) }
			/>

			<div className="flex flex-col gap-2">
				<Label tag="span" className="text-text-primary font-semibold block">
					{ __(
						'Here’s What Cart Abandonment Recovery Will Do for You Now:',
						'woo-cart-abandonment-recovery'
					) }
				</Label>
				<ul className="list-none pl-0 m-0 space-y-2">
					{ UNLOCKED.map( ( item ) => (
						<li
							key={ item.heading }
							className="flex items-start gap-2 text-sm text-text-secondary"
						>
							<CheckIcon
								className="size-4 text-flamingo-500 shrink-0 mt-0.5"
								aria-hidden="true"
							/>
							<span>
								<strong className="text-text-primary">
									{ item.heading }
								</strong>{ ' ' }
								{ item.description }
							</span>
						</li>
					) ) }
				</ul>
			</div>

			<div className="flex flex-col gap-2">
				<Label tag="span" className="text-text-primary font-semibold block">
					{ nextStepsLabel }
				</Label>
				<ul className="list-none pl-0 m-0 space-y-2">
					{ NEXT_STEPS.map( ( item ) => (
						<li
							key={ item.path }
							className="flex items-center gap-1.5 text-sm"
						>
							<ArrowRightIcon
								className="size-4 text-icon-interactive shrink-0"
								aria-hidden="true"
							/>
							<Button
								tag="a"
								href={
									cart_abandonment_admin.admin_url +
									`&path=${ item.path }`
								}
								variant="link"
								size="sm"
								className="text-flamingo-400 hover:text-primary-600 no-underline"
							>
								{ item.label }
							</Button>
						</li>
					) ) }
				</ul>
			</div>

			<div className="flex flex-col gap-3">
				<Button onClick={ redirectToDashboard } variant="primary">
					{ __( 'Go To Dashboard', 'woo-cart-abandonment-recovery' ) }
				</Button>
				<Button
					onClick={ () =>
						window.open(
							'https://cartflows.com/docs-category/cart-abandonment/',
							'_blank'
						)
					}
					variant="ghost"
					iconPosition="right"
					icon={
						<ArrowTopRightOnSquareIcon className="size-4 text-icon-secondary" />
					}
				>
					{ __( 'Documentation', 'woo-cart-abandonment-recovery' ) }
				</Button>
			</div>
		</>
	);
};

export default OnboardingComplete;
