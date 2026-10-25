import { __ } from '@wordpress/i18n';

import ChannelDetails from '@Components/detailedReport/ChannelDetails';

const EmailDetails = ( {
	scheduledEmails,
	isLoading,
	handleRescheduleEmails,
	buttonLoading,
	disabled,
	unsubscribed,
} ) => (
	<ChannelDetails
		title={ __( 'Email Details', 'woo-cart-abandonment-recovery' ) }
		rescheduleLabel={ __(
			'Reschedule Emails',
			'woo-cart-abandonment-recovery'
		) }
		messageHeading={ __( 'Email Subject', 'woo-cart-abandonment-recovery' ) }
		messageKey="email_subject"
		sentKey="email_sent"
		emptyDescription={ __(
			'No follow-up emails are scheduled for this cart. Use Reschedule Emails to schedule them.',
			'woo-cart-abandonment-recovery'
		) }
		rows={ scheduledEmails }
		onReschedule={ handleRescheduleEmails }
		isLoading={ isLoading }
		buttonLoading={ buttonLoading }
		disabled={ disabled }
		unsubscribed={ unsubscribed }
	/>
);

export default EmailDetails;
