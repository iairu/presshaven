// Sample rows the Pro preview shows behind the upgrade message. Their dates follow the clock, so
// the activity always looks recent and the scheduled jobs always look upcoming.

// Minutes from now, as a time stamp: negative for the past.
const MINUTE_MS = 60000;
const minutesFromNow = ( minutes ) => {
	const offset = minutes * MINUTE_MS;
	return Date.now() + offset;
};

// Minutes from the first row's offset to row `index`: rows sit 35 minutes apart.
const rowOffset = ( index, first ) => {
	const gap = index * 35;
	return first + gap;
};

const pad = ( value ) => String( value ).padStart( 2, '0' );

// `YYYY-MM-DD HH:mm:ss` in local time, the shape the real rows use.
const formatStamp = ( minutes ) => {
	const date = new Date( minutesFromNow( minutes ) );
	return `${ date.getFullYear() }-${ pad( date.getMonth() + 1 ) }-${ pad(
		date.getDate()
	) } ${ pad( date.getHours() ) }:${ pad( date.getMinutes() ) }:${ pad(
		date.getSeconds()
	) }`;
};

const ACTIVITY_SAMPLES = [
	[ 'email', 'sent', 'jane@example.com', 'First reminder', null ],
	[ 'sms', 'failed', '+1 555-0100', 'Second reminder', 'Send failed' ],
	[
		'whatsapp',
		'skipped',
		'+1 555-0123',
		'Third reminder',
		'Recipient unsubscribed',
	],
	[ 'email', 'sent', 'liam@example.com', 'First reminder', null ],
	[
		'email',
		'skipped',
		'noah@example.com',
		'Second reminder',
		'Recipient is blacklisted',
	],
	[ 'sms', 'sent', '+1 555-0148', 'First reminder', null ],
	[ 'whatsapp', 'sent', '+1 555-0166', 'First reminder', null ],
	[
		'email',
		'failed',
		'olivia@example.com',
		'Third reminder',
		'Could not instantiate mail function.',
	],
	[
		'sms',
		'skipped',
		'+1 555-0189',
		'Second reminder',
		'Rule condition prevented send',
	],
	[ 'email', 'sent', 'emma@example.com', 'First reminder', null ],
	[
		'whatsapp',
		'failed',
		'+1 555-0204',
		'Second reminder',
		'WhatsApp status: failed',
	],
	[ 'email', 'sent', 'ava@example.com', 'Second reminder', null ],
	[ 'sms', 'sent', '+1 555-0231', 'Third reminder', null ],
];

const SCHEDULED_SAMPLES = [
	[ 'email', 'jane@example.com', 'First reminder' ],
	[ 'sms', '+1 555-0100', 'Second reminder' ],
	[ 'whatsapp', '+1 555-0123', 'First reminder' ],
	[ 'email', 'liam@example.com', 'Second reminder' ],
	[ 'email', 'noah@example.com', 'Third reminder' ],
	[ 'sms', '+1 555-0148', 'First reminder' ],
	[ 'whatsapp', '+1 555-0166', 'Second reminder' ],
	[ 'email', 'olivia@example.com', 'First reminder' ],
	[ 'sms', '+1 555-0189', 'Third reminder' ],
	[ 'email', 'emma@example.com', 'Second reminder' ],
	[ 'whatsapp', '+1 555-0204', 'First reminder' ],
	[ 'email', 'ava@example.com', 'Third reminder' ],
	[ 'sms', '+1 555-0231', 'Second reminder' ],
];

// Newest first, 35 minutes apart, ending a few minutes ago.
export const getDummyActivityRows = () => {
	return ACTIVITY_SAMPLES.map(
		( [ channel, event, recipient, template_name, error ], index ) => ( {
			id: `d${ index + 1 }`,
			channel,
			event,
			recipient,
			template_name,
			timestamp: formatStamp( rowOffset( index, 5 ) * -1 ),
			error,
		} )
	);
};

// Soonest first, 35 minutes apart, starting a few minutes from now.
export const getDummyScheduledRows = () => {
	return SCHEDULED_SAMPLES.map(
		( [ channel, recipient, template_name ], index ) => ( {
			id: `d${ index + 1 }`,
			channel,
			recipient,
			template_name,
			execution_time: formatStamp( rowOffset( index, 10 ) ),
			status: 'pending',
		} )
	);
};
