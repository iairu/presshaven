import { useMemo } from '@wordpress/element';
import { __ } from '@wordpress/i18n';

import ActivityLogPageShell from '@Components/activityLog/ActivityLogPageShell';
import ActivityLogTab from '@Components/activityLog/ActivityLogTab';
import useActivityLogData from '@Components/activityLog/useActivityLogData';
import { getDummyActivityRows } from '@Components/activityLog/dummyRows';

const ActivityLog = () => {
	const state = useActivityLogData( 'activity' );
	const dummyRows = useMemo( () => getDummyActivityRows(), [] );
	const tableRows = state.isBlocked ? dummyRows : state.items;

	return (
		<ActivityLogPageShell
			title={ __( 'Activity Log', 'woo-cart-abandonment-recovery' ) }
			type="activity"
			state={ state }
			tableRows={ tableRows }
			canExport={ true }
			upgradeDescription={ __(
				'Track every email, SMS, and WhatsApp event with Pro.',
				'woo-cart-abandonment-recovery'
			) }
			upgradeCampaign="activity-log"
		>
			<ActivityLogTab rows={ tableRows } state={ state } />
		</ActivityLogPageShell>
	);
};

export default ActivityLog;
