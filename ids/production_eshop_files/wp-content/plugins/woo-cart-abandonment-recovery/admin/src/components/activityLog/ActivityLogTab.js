import { Table, Badge } from '@bsf/force-ui';
import { __ } from '@wordpress/i18n';

import TruncatedText from '@Components/common/TruncatedText';
import ActivityLogListState from './ActivityLogListState';
import {
	CHANNEL_LABEL,
	EVENT_LABEL,
	EVENT_BADGE_VARIANT,
} from './constants';

const SKELETON_COLUMNS = [
	{
		heading: __( 'Channel', 'woo-cart-abandonment-recovery' ),
		sample: 'WhatsApp',
	},
	{
		heading: __( 'Event', 'woo-cart-abandonment-recovery' ),
		sample: 'Skipped',
	},
	{
		heading: __( 'Recipient', 'woo-cart-abandonment-recovery' ),
		sample: 'olivia@example.com',
	},
	{
		heading: __( 'Template', 'woo-cart-abandonment-recovery' ),
		sample: 'Second reminder',
	},
	{
		heading: __( 'Timestamp', 'woo-cart-abandonment-recovery' ),
		sample: '2026-05-21 09:00:00',
	},
	{
		heading: __( 'Detail', 'woo-cart-abandonment-recovery' ),
		sample: 'Recipient is blacklisted',
	},
];

const ActivityLogTab = ( { rows, state } ) => (
	<ActivityLogListState
		state={ state }
		rows={ rows }
		columns={ SKELETON_COLUMNS }
		label={ __( 'Activity Log', 'woo-cart-abandonment-recovery' ) }
		loadingLabel={ __(
			'Loading activity…',
			'woo-cart-abandonment-recovery'
		) }
		failedTitle={ __(
			'Could not load the activity log',
			'woo-cart-abandonment-recovery'
		) }
		emptyTitle={ __( 'No activity yet', 'woo-cart-abandonment-recovery' ) }
		emptyText={ __(
			'Sent, failed, and skipped recovery messages will show up here.',
			'woo-cart-abandonment-recovery'
		) }
	>
		<Table
			className="whitespace-nowrap"
			aria-label={ __( 'Activity Log', 'woo-cart-abandonment-recovery' ) }
		>
			<Table.Head>
				{ SKELETON_COLUMNS.map( ( column ) => (
					<Table.HeadCell key={ column.heading }>
						{ column.heading }
					</Table.HeadCell>
				) ) }
			</Table.Head>
			<Table.Body>
				{ rows.map( ( row ) => (
					<Table.Row key={ row.id }>
						<Table.Cell>
							{ CHANNEL_LABEL[ row.channel ] || row.channel }
						</Table.Cell>
						<Table.Cell>
							<Badge
								label={
									EVENT_LABEL[ row.event ] || row.event
								}
								variant={
									EVENT_BADGE_VARIANT[ row.event ] ||
									'neutral'
								}
								size="sm"
								type="pill"
								className="w-fit"
							/>
						</Table.Cell>
						<Table.Cell>{ row.recipient || '—' }</Table.Cell>
						<Table.Cell>{ row.template_name || '—' }</Table.Cell>
						<Table.Cell className="tabular-nums">
							{ row.timestamp || '—' }
						</Table.Cell>
						<Table.Cell className="max-w-72">
							{ row.error ? (
								<TruncatedText
									text={ row.error }
									className="text-text-secondary"
								/>
							) : (
								<div className="text-text-secondary">—</div>
							) }
						</Table.Cell>
					</Table.Row>
				) ) }
			</Table.Body>
		</Table>
	</ActivityLogListState>
);

export default ActivityLogTab;
