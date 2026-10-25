import { useMemo } from '@wordpress/element';
import { __ } from '@wordpress/i18n';

import ActivityLogPageShell from '@Components/activityLog/ActivityLogPageShell';
import ScheduledJobsTab from '@Components/activityLog/ScheduledJobsTab';
import useActivityLogData from '@Components/activityLog/useActivityLogData';
import { getDummyScheduledRows } from '@Components/activityLog/dummyRows';

const ScheduledJobs = () => {
	const state = useActivityLogData( 'scheduled' );
	const dummyRows = useMemo( () => getDummyScheduledRows(), [] );
	const tableRows = state.isBlocked ? dummyRows : state.items;

	return (
		<ActivityLogPageShell
			title={ __( 'Scheduled Jobs', 'woo-cart-abandonment-recovery' ) }
			type="scheduled"
			state={ state }
			tableRows={ tableRows }
			upgradeDescription={ __(
				'Monitor upcoming email, SMS, and WhatsApp follow-ups with Pro.',
				'woo-cart-abandonment-recovery'
			) }
			upgradeCampaign="scheduled-jobs"
		>
			<ScheduledJobsTab rows={ tableRows } state={ state } />
		</ActivityLogPageShell>
	);
};

export default ScheduledJobs;
