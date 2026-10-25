import { __ } from '@wordpress/i18n';

import AddOns from './screens/AddOns';
import FollowUpChannels from './screens/FollowUpChannels';
import OnboardingComplete from './screens/OnboardingComplete';
import RecoverySettings from './screens/RecoverySettings';
import UserDetails from './screens/UserDetails';
import Welcome from './screens/Welcome';

/**
 * The wizard, in order.
 *
 * `width` lets each step size its card to its own content instead of every step sharing one
 * fixed width. `label` drives the stepper; `analyticsSlug` is a stable identifier for tracking
 * that stays put even if `url` (which also has to keep old bookmarks/redirects working) ever
 * changes.
 */
const ONBOARDING_ROUTES_CONFIG = [
	{
		url: 'welcome',
		index: true,
		component: <Welcome />,
		width: 'md:w-[40rem]',
		label: __( 'Welcome', 'woo-cart-abandonment-recovery' ),
		analyticsSlug: 'welcome',
	},
	{
		url: 'recovery-settings',
		component: <RecoverySettings />,
		width: 'md:w-[44rem]',
		label: __( 'Recovery', 'woo-cart-abandonment-recovery' ),
		analyticsSlug: 'recovery-settings',
	},
	{
		url: 'follow-up-channels',
		component: <FollowUpChannels />,
		width: 'md:w-[44rem]',
		label: __( 'Channels', 'woo-cart-abandonment-recovery' ),
		analyticsSlug: 'follow-up-channels',
	},
	{
		url: 'report-email',
		component: <UserDetails />,
		width: 'md:w-[47rem]',
		label: __( 'Reports', 'woo-cart-abandonment-recovery' ),
		analyticsSlug: 'report-email',
	},
	{
		url: 'addons',
		component: <AddOns />,
		width: 'md:w-[44rem]',
		label: __( 'Plugins', 'woo-cart-abandonment-recovery' ),
		analyticsSlug: 'addons',
	},
	{
		url: 'finish',
		component: <OnboardingComplete />,
		width: 'md:w-[40rem]',
		label: __( 'Done', 'woo-cart-abandonment-recovery' ),
		analyticsSlug: 'finish',
	},
];
export default ONBOARDING_ROUTES_CONFIG;
