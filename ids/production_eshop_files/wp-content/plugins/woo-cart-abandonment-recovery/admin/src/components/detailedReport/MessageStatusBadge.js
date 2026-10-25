import { Badge } from '@bsf/force-ui';
import AppTooltip from '@Components/common/AppTooltip';
import { ExclamationCircleIcon } from '@heroicons/react/24/outline';
import { __ } from '@wordpress/i18n';

/**
 * Shared status badge for a scheduled email / SMS / WhatsApp follow-up.
 * Maps `*_sent`: 1 = Sent, 0 = Scheduled, -1/-2/-3 = Not Sent. A pending (0) row
 * on a blacklisted / unsubscribed cart is shown as skipped with the reason.
 *
 * @param {Object}        props
 * @param {number|string} props.status         The channel's `*_sent` flag.
 * @param {boolean}       [props.disabled]     Cart is blacklisted.
 * @param {string}        [props.unsubscribed] Cart's unsubscribed flag ('1' when unsubscribed).
 * @return {JSX.Element} The status badge.
 */
const MessageStatusBadge = ( { status, disabled = false, unsubscribed = '' } ) => {
	const isIneligible = disabled || '1' === String( unsubscribed );

	let skipReason = __(
		'Rule condition failed or product excluded',
		'woo-cart-abandonment-recovery'
	);
	if ( disabled ) {
		skipReason = __(
			'Recipient is blacklisted',
			'woo-cart-abandonment-recovery'
		);
	} else if ( '1' === String( unsubscribed ) ) {
		skipReason = __(
			'Recipient unsubscribed',
			'woo-cart-abandonment-recovery'
		);
	}

	let key = String( status );
	if ( '0' === key && isIneligible ) {
		key = '-2';
	}

	const config = {
		'-1': {
			label: __( 'Not Sent', 'woo-cart-abandonment-recovery' ),
			variant: 'red',
		},
		'-2': {
			label: __( 'Not Sent', 'woo-cart-abandonment-recovery' ),
			variant: 'red',
		},
		'-3': {
			label: __( 'Not Sent', 'woo-cart-abandonment-recovery' ),
			variant: 'red',
		},
		0: {
			label: __( 'Scheduled', 'woo-cart-abandonment-recovery' ),
			variant: 'yellow',
		},
		1: {
			label: __( 'Sent', 'woo-cart-abandonment-recovery' ),
			variant: 'green',
		},
	};
	const cfg = config[ key ] || config[ 0 ];

	// -3 (blacklisted) carries its own reason, so it stays correct even after
	// the cart is whitelisted.
	const tooltipReason =
		'-3' === key
			? __( 'Recipient is blacklisted', 'woo-cart-abandonment-recovery' )
			: skipReason;

	if ( '-2' === key || '-3' === key ) {
		// The reason is real content, not decoration: it is read out with the badge, and the badge
		// takes keyboard focus so the tooltip opens without a mouse.
		return (
			<AppTooltip
				content={ tooltipReason }
				position="top"
				triggers={ [ 'hover', 'focus' ] }
			>
				<span
					tabIndex={ 0 }
					className="inline-flex w-fit cursor-help rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
				>
					<Badge
						icon={ <ExclamationCircleIcon className="" /> }
						label={ cfg.label }
						size="sm"
						type="pill"
						variant={ cfg.variant }
						className="w-fit"
					/>
					<span className="sr-only">{ `: ${ tooltipReason }` }</span>
				</span>
			</AppTooltip>
		);
	}

	return (
		<Badge
			label={ cfg.label }
			size="sm"
			type="pill"
			variant={ cfg.variant }
			className="w-fit cursor-default"
		/>
	);
};

export default MessageStatusBadge;
