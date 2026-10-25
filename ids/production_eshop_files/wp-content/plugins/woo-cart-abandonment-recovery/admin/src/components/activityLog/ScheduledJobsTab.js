import { Table, Badge } from '@bsf/force-ui';
import { __ } from '@wordpress/i18n';

import ActivityLogListState from './ActivityLogListState';
import {
	CHANNEL_LABEL,
	EVENT_LABEL,
	EVENT_BADGE_VARIANT,
} from './constants';

const SKELETON_COLUMNS = [
	{
		heading: __( 'Execution Time', 'woo-cart-abandonment-recovery' ),
		sample: '2026-05-22 09:30:00',
	},
	{
		heading: __( 'Recipient', 'woo-cart-abandonment-recovery' ),
		sample: 'olivia@example.com',
	},
	{
		heading: __( 'Channel', 'woo-cart-abandonment-recovery' ),
		sample: 'WhatsApp',
	},
	{
		heading: __( 'Template', 'woo-cart-abandonment-recovery' ),
		sample: 'Second reminder',
	},
	{
		heading: __( 'Status', 'woo-cart-abandonment-recovery' ),
		sample: 'Pending',
	},
];

const ScheduledJobsTab = ( { rows, state } ) => (
	<ActivityLogListState
		state={ state }
		rows={ rows }
		columns={ SKELETON_COLUMNS }
		label={ __( 'Scheduled Jobs', 'woo-cart-abandonment-recovery' ) }
		loadingLabel={ __(
			'Loading scheduled jobs…',
			'woo-cart-abandonment-recovery'
		) }
		failedTitle={ __(
			'Could not load the scheduled jobs',
			'woo-cart-abandonment-recovery'
		) }
		emptyTitle={ __(
			'No upcoming jobs',
			'woo-cart-abandonment-recovery'
		) }
		emptyText={ __(
			'Recovery messages queued to send will appear here.',
			'woo-cart-abandonment-recovery'
		) }
	>
		<Table
			className="whitespace-nowrap"
			aria-label={ __( 'Scheduled Jobs', 'woo-cart-abandonment-recovery' ) }
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
						<Table.Cell className="tabular-nums">
							{ row.execution_time || '—' }
						</Table.Cell>
						<Table.Cell>{ row.recipient || '—' }</Table.Cell>
						<Table.Cell>
							{ CHANNEL_LABEL[ row.channel ] || row.channel }
						</Table.Cell>
						<Table.Cell>{ row.template_name || '—' }</Table.Cell>
						<Table.Cell>
							<Badge
								label={
									EVENT_LABEL[ row.status ] || row.status
								}
								variant={
									EVENT_BADGE_VARIANT[ row.status ] ||
									'neutral'
								}
								size="sm"
								type="pill"
								className="w-fit"
							/>
						</Table.Cell>
					</Table.Row>
				) ) }
			</Table.Body>
		</Table>
	</ActivityLogListState>
);

export default ScheduledJobsTab;
