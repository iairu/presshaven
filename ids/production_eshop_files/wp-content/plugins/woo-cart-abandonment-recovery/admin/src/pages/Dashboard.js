import { useEffect, useState } from 'react';
import { useStateValue, doApiFetch } from '@Store';
import { getDefaultDateRange, toDateParam } from '@Utils/helper';

// Import dashboard components
import Overview from '@Components/dashboard/Overview';
import RecentEmailLogs from '@Components/dashboard/RecentEmailLogs';
import ProductReport from '@Components/dashboard/ProductReport';
import AddonsPlugins from '@Components/dashboard/AddonsPlugins';
import QuickAccess from '@Components/dashboard/QuickAccess';

const isSameDay = ( a, b ) => a?.toDateString() === b?.toDateString();

const Dashboard = () => {
	// Safe state access with default values
	const [ state, dispatch ] = useStateValue();
	const dashboardData = state?.dashboardData || null;
	const [ isDashboardLoading, setIsDashboardLoading ] = useState( false );

	const [ selectedRange, setSelectedRange ] = useState( getDefaultDateRange );

	// The filter counts as cleared once the range is back to the default 7 days.
	const defaultRange = getDefaultDateRange();
	const isDefaultRange =
		isSameDay( selectedRange?.from, defaultRange.from ) &&
		isSameDay( selectedRange?.to, defaultRange.to );

	useEffect( () => {
		// A later range change (or unmount) marks this request as stale so a slow
		// response can never overwrite newer data.
		let isStale = false;

		const fetchDashboardData = async () => {
			setIsDashboardLoading( true );

			// Fallback to default range if cleared
			let from = selectedRange.from;
			let to = selectedRange.to;
			if ( ! from || ! to ) {
				const def = getDefaultDateRange();
				from = def.from;
				to = def.to;
			}

			try {
				await doApiFetch(
					'/wcar/api/admin/dashboard',
					{
						date_range: {
							from: toDateParam( from ),
							to: toDateParam( to ),
						},
					},
					'POST',
					// onSuccess.
					( response ) => {
						if ( isStale ) {
							return;
						}
						dispatch( {
							type: 'FETCH_DASHBOARD_DATA_SUCCESS',
							dashboardData: response,
						} );
						setIsDashboardLoading( false );
					},
					// onError.
					() => {
						if ( ! isStale ) {
							setIsDashboardLoading( false );
						}
					}
				);
			} catch ( error ) {
				// doApiFetch already reported the failure through onError.
			}
		};

		fetchDashboardData();

		return () => {
			isStale = true;
		};
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [ selectedRange ] );

	return (
		<div className="p-4 md:p-8 flex flex-col gap-6 md:gap-8">
			{ /* Overview Section */ }
			<Overview
				dashboardData={ dashboardData }
				isDashboardLoading={ isDashboardLoading }
				selectedRange={ selectedRange }
				handleDateRangeChange={ setSelectedRange }
				isFiltered={ ! isDefaultRange }
				onClearFilter={ () => setSelectedRange( getDefaultDateRange() ) }
			/>

			{ /* Recent Email Logs Section */ }
			<RecentEmailLogs
				dashboardData={ dashboardData }
				isDashboardLoading={ isDashboardLoading }
			/>

			{ /* Product Report Section */ }
			<ProductReport
				dashboardData={ dashboardData }
				isDashboardLoading={ isDashboardLoading }
			/>

			{ /* Promotional row: full-width rows keep the page free of gaps. */ }
			<div className="grid grid-cols-1 lg:grid-cols-5 gap-6 md:gap-8">
				{ /* Extend Website Section */ }
				<AddonsPlugins className="lg:col-span-3" />

				{ /* Quick Access Section */ }
				<QuickAccess className="lg:col-span-2" />
			</div>
		</div>
	);
};

export default Dashboard;
