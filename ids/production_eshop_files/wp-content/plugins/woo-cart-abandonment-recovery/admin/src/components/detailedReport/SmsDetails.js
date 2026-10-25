import { __ } from '@wordpress/i18n';

import ChannelDetails from '@Components/detailedReport/ChannelDetails';
import { useProAccess } from '@Components/pro/useProAccess';

const SmsDetails = ( {
	scheduledSms,
	isLoading,
	handleRescheduleSms,
	buttonLoading,
	disabled,
	unsubscribed,
} ) => {
	const { shouldBlockProFeatures } = useProAccess();

	return (
		<ChannelDetails
			title={ __( 'SMS Details', 'woo-cart-abandonment-recovery' ) }
			rescheduleLabel={ __(
				'Reschedule SMS',
				'woo-cart-abandonment-recovery'
			) }
			messageHeading={ __( 'SMS Body', 'woo-cart-abandonment-recovery' ) }
			messageKey="sms_body"
			sentKey="sms_sent"
			emptyDescription={ __(
				'No follow-up SMS are scheduled for this cart. Use Reschedule SMS to schedule them.',
				'woo-cart-abandonment-recovery'
			) }
			rows={ scheduledSms }
			onReschedule={ handleRescheduleSms }
			isLoading={ isLoading }
			buttonLoading={ buttonLoading }
			disabled={ disabled }
			unsubscribed={ unsubscribed }
			isLocked={ shouldBlockProFeatures() }
			lockedMessage={ __(
				'View all scheduled SMS follow-ups in SMS details.',
				'woo-cart-abandonment-recovery'
			) }
		/>
	);
};

export default SmsDetails;
