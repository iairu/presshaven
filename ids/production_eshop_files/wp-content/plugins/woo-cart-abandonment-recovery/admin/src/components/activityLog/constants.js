import { __ } from '@wordpress/i18n';

export const CHANNEL_OPTIONS = [
	{ id: 'all', title: __( 'All Channels', 'woo-cart-abandonment-recovery' ) },
	{ id: 'email', title: __( 'Email', 'woo-cart-abandonment-recovery' ) },
	{ id: 'sms', title: __( 'SMS', 'woo-cart-abandonment-recovery' ) },
	{
		id: 'whatsapp',
		title: __( 'WhatsApp', 'woo-cart-abandonment-recovery' ),
	},
];

export const ACTIVITY_STATUS_OPTIONS = [
	{ id: 'all', title: __( 'All Statuses', 'woo-cart-abandonment-recovery' ) },
	{ id: 'sent', title: __( 'Sent', 'woo-cart-abandonment-recovery' ) },
	{ id: 'failed', title: __( 'Failed', 'woo-cart-abandonment-recovery' ) },
	{ id: 'skipped', title: __( 'Skipped', 'woo-cart-abandonment-recovery' ) },
];

export const SCHEDULED_STATUS_OPTIONS = [
	{ id: 'all', title: __( 'All Statuses', 'woo-cart-abandonment-recovery' ) },
	{ id: 'pending', title: __( 'Pending', 'woo-cart-abandonment-recovery' ) },
];

export const EVENT_BADGE_VARIANT = {
	scheduled: 'yellow',
	sent: 'green',
	failed: 'red',
	skipped: 'neutral',
	pending: 'yellow',
};

export const CHANNEL_LABEL = {
	email: __( 'Email', 'woo-cart-abandonment-recovery' ),
	sms: __( 'SMS', 'woo-cart-abandonment-recovery' ),
	whatsapp: __( 'WhatsApp', 'woo-cart-abandonment-recovery' ),
};

export const EVENT_LABEL = {
	scheduled: __( 'Scheduled', 'woo-cart-abandonment-recovery' ),
	sent: __( 'Sent', 'woo-cart-abandonment-recovery' ),
	failed: __( 'Failed', 'woo-cart-abandonment-recovery' ),
	skipped: __( 'Skipped', 'woo-cart-abandonment-recovery' ),
	pending: __( 'Pending', 'woo-cart-abandonment-recovery' ),
};
