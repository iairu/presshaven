import { __ } from '@wordpress/i18n';

import ChannelDetails from '@Components/detailedReport/ChannelDetails';
import { useProAccess } from '@Components/pro/useProAccess';

const WhatsappDetails = ( {
	scheduledMessages,
	isLoading,
	handleRescheduleMessage,
	buttonLoading,
	disabled,
	unsubscribed,
} ) => {
	const { shouldBlockProFeatures } = useProAccess();

	return (
		<ChannelDetails
			title={ __( 'WhatsApp Details', 'woo-cart-abandonment-recovery' ) }
			rescheduleLabel={ __(
				'Reschedule Messages',
				'woo-cart-abandonment-recovery'
			) }
			messageHeading={ __(
				'WhatsApp Template',
				'woo-cart-abandonment-recovery'
			) }
			messageKey="whatsapp_template"
			sentKey="message_sent"
			emptyDescription={ __(
				'No follow-up WhatsApp messages are scheduled for this cart. Use Reschedule Messages to schedule them.',
				'woo-cart-abandonment-recovery'
			) }
			rows={ scheduledMessages }
			onReschedule={ handleRescheduleMessage }
			isLoading={ isLoading }
			buttonLoading={ buttonLoading }
			disabled={ disabled }
			unsubscribed={ unsubscribed }
			isLocked={ shouldBlockProFeatures() }
			lockedMessage={ __(
				'View all scheduled WhatsApp follow-ups in WhatsApp details.',
				'woo-cart-abandonment-recovery'
			) }
		/>
	);
};

export default WhatsappDetails;
