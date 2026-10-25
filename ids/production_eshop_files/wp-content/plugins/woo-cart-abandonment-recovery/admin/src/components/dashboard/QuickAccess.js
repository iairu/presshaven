import { Text } from '@bsf/force-ui';
import {
	QuestionMarkCircleIcon,
	ChatBubbleLeftRightIcon,
	StarIcon,
	TicketIcon,
	RocketLaunchIcon,
} from '@heroicons/react/24/outline';
import { __ } from '@wordpress/i18n';
import { Link } from 'react-router-dom';
import PropTypes from 'prop-types';

import DashboardCard from '@Components/dashboard/DashboardCard';

const ITEM_CLASS =
	'flex-1 flex items-center gap-1 p-3 bg-background-primary rounded-md shadow-sm no-underline hover:bg-background-secondary transition-colors group/quick-access focus:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1';

// Built at render time so labels are translated once locale data is loaded.
const getExternalLinks = () => [
	{
		icon: QuestionMarkCircleIcon,
		label: __( 'Help Center', 'woo-cart-abandonment-recovery' ),
		href: 'https://cartflows.com/docs-category/cart-abandonment',
	},
	{
		icon: ChatBubbleLeftRightIcon,
		label: __( 'Join the Community', 'woo-cart-abandonment-recovery' ),
		href: 'https://www.facebook.com/groups/cartflows',
	},
	{
		icon: StarIcon,
		label: __( 'Rate Us', 'woo-cart-abandonment-recovery' ),
		href: 'https://wordpress.org/support/plugin/woo-cart-abandonment-recovery/reviews/#new-post',
	},
	{
		icon: TicketIcon,
		label: __( 'Open Support Ticket', 'woo-cart-abandonment-recovery' ),
		href: 'https://cartflows.com/support',
	},
];

const { admin_url: adminUrl, onboarding: onboardingState } =
	cart_abandonment_admin;

const QuickAccess = ( { className } ) => {
	const links = getExternalLinks();
	const onboarding = onboardingState || {};

	// Prepend "Launch"/"Resume Setup" (admin-internal SPA route) only while
	// onboarding is unfinished. Once they've exited partway through, this becomes
	// "Resume Setup" and reopens the exact step the server recorded them leaving —
	// not from localStorage, so it also works from a different browser.
	if ( ! onboarding.onboarding_completed ) {
		const resumeStep = onboarding.skipped && onboarding.resume_step;

		links.unshift( {
			icon: RocketLaunchIcon,
			label: resumeStep
				? __( 'Resume Setup', 'woo-cart-abandonment-recovery' )
				: __( 'Launch Setup', 'woo-cart-abandonment-recovery' ),
			href:
				adminUrl +
				'&path=onboarding' +
				( resumeStep ? `&step=${ resumeStep }` : '' ),
			internal: true,
		} );
	}

	return (
		<DashboardCard
			title={ __( 'Quick Access', 'woo-cart-abandonment-recovery' ) }
			compact
			className={ className }
		>
			<ul className="flex-1 flex flex-col bg-field-primary-background gap-1 p-1 m-0 list-none rounded-lg">
				{ links.map( ( { icon: Icon, label, href, internal } ) => {
					const content = (
						<>
							<Icon className="size-4.5 text-icon-primary shrink-0" />
							<Text
								as="span"
								size={ 14 }
								weight={ 400 }
								className="px-1 group-hover/quick-access:text-link-primary-hover transition-colors"
							>
								{ label }
							</Text>
						</>
					);

					return (
						<li key={ href } className="flex flex-1 m-0">
							{ internal ? (
								<Link
									to={ href }
									className={ ITEM_CLASS }
								>
									{ content }
								</Link>
							) : (
								<a
									href={ href }
									target="_blank"
									rel="noreferrer"
									className={ ITEM_CLASS }
								>
									{ content }
									<span className="sr-only">
										{ __(
											'(opens in a new tab)',
											'woo-cart-abandonment-recovery'
										) }
									</span>
								</a>
							) }
						</li>
					);
				} ) }
			</ul>
		</DashboardCard>
	);
};

QuickAccess.propTypes = {
	className: PropTypes.string,
};

export default QuickAccess;
