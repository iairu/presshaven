/* eslint-disable no-mixed-spaces-and-tabs */
import parse from 'html-react-parser';
import PropTypes from 'prop-types';
import { LineChart, Button, Text } from '@bsf/force-ui';
import {
	InformationCircleIcon,
	XMarkIcon,
	ArrowTrendingUpIcon,
	ArrowTrendingDownIcon,
} from '@heroicons/react/24/outline';
import { __, sprintf } from '@wordpress/i18n';

import DashboardCard from '@Components/dashboard/DashboardCard';
import { cn } from '@Utils/helper';
import SkeletonLoader from '@Components/common/skeletons/SkeletonLoader';
import DateRange from '@Components/fields/DateRange';
import InfoTip from '@Components/dashboard/InfoTip';

const formatXAxis = ( tick ) => {
	// Try to format as 'MMM dd' (e.g., 'Jun 20')
	if ( ! tick ) {
		return '';
	}
	const date = new Date( tick );
	if ( isNaN( date.getTime() ) ) {
		return tick;
	}
	return date.toLocaleDateString( 'en-US', {
		month: 'short',
		day: '2-digit',
	} );
};

const formatYAxis = ( value ) => {
	if ( value === null || value === undefined ) {
		return '';
	}
	if ( Math.abs( value ) >= 1.0e9 ) {
		return ( value / 1.0e9 ).toFixed( 1 ).replace( /\.0$/, '' ) + 'B';
	}
	if ( Math.abs( value ) >= 1.0e6 ) {
		return ( value / 1.0e6 ).toFixed( 1 ).replace( /\.0$/, '' ) + 'M';
	}
	if ( Math.abs( value ) >= 1.0e3 ) {
		return ( value / 1.0e3 ).toFixed( 1 ).replace( /\.0$/, '' ) + 'K';
	}
	return value.toString();
};

// One source for the chart lines and their legend swatches (hex must match the swatch class).
const CHART_SERIES = [
	{
		key: 'recoverable',
		stroke: '#F06434',
		swatch: 'bg-flamingo-400',
	},
	{
		key: 'recovered',
		stroke: '#FBBF24',
		swatch: 'bg-amber-400',
	},
];

const Overview = ( {
	dashboardData,
	isDashboardLoading,
	selectedRange,
	handleDateRangeChange,
	isFiltered,
	onClearFilter,
} ) => {
	// Define metrics data structure
	const iconUp = (
		<ArrowTrendingUpIcon className="h-4 w-4 stroke-[3px] text-badge-color-green" />
	);
	const iconDown = (
		<ArrowTrendingDownIcon className="h-4 w-4 stroke-[3px] text-support-error" />
	);
	const getPercentValue = ( percentString ) => {
		// Remove anything that is not a number, dot, or minus
		const value = parseFloat(
			percentString?.replace( /[^\d.-]/g, '' ).trim()
		);
		return isNaN( value ) ? 0 : value;
	};

	const getPercentChange = ( prev, curr ) => {
		if ( prev === 0 && curr === 0 ) {
			return 0;
		}
		if ( prev === 0 && curr !== 0 ) {
			return 100;
		}
		if ( prev !== 0 && curr === 0 ) {
			return -100;
		}
		// Normal percentage change
		return ( ( curr - prev ) / prev ) * 100;
	};

	const currentRecoveryRate = getPercentValue( dashboardData?.recovery_rate );
	const previousRecoveryRate = getPercentValue(
		dashboardData?.previous_period?.recovery_rate
	);
	const recoveryRateChange = getPercentChange(
		previousRecoveryRate,
		currentRecoveryRate
	);
	const trendIcon =
		( currentRecoveryRate > previousRecoveryRate && iconUp ) ||
		( currentRecoveryRate < previousRecoveryRate && iconDown ) ||
		null;
	const trendText = sprintf(
		/* translators: 1: recovery rate change percentage, 2: 'increase' or 'decrease'. */
		__(
			'%1$s%% %2$s from previous period',
			'woo-cart-abandonment-recovery'
		),
		Math.abs( recoveryRateChange ).toFixed( 2 ),
		recoveryRateChange > 0
			? __( 'increase', 'woo-cart-abandonment-recovery' )
			: __( 'decrease', 'woo-cart-abandonment-recovery' )
	);
	const metricsData = [
		{
			label: __( 'Recovered Revenue', 'woo-cart-abandonment-recovery' ),
			value: dashboardData?.recovered_revenue
				? parse( dashboardData?.recovered_revenue )
				: '0.00',
			tooltip: __(
				'The revenue that has been recovered.',
				'woo-cart-abandonment-recovery'
			),
			color:
				dashboardData?.recovered_revenue_amount > 0
					? 'text-badge-color-green'
					: '',
		},
		{
			label: __( 'Recovered Orders', 'woo-cart-abandonment-recovery' ),
			value: dashboardData?.recovered_orders || '0',
			tooltip: __(
				'The number of orders that have been recovered.',
				'woo-cart-abandonment-recovery'
			),
			color: dashboardData?.recovered_orders > 0 ? 'text-badge-color-green' : '',
		},
		{
			label: __( 'Recoverable Revenue', 'woo-cart-abandonment-recovery' ),
			value: dashboardData?.recoverable_revenue
				? parse( dashboardData?.recoverable_revenue )
				: '0.00',
			tooltip: __(
				'The revenue that can be recovered.',
				'woo-cart-abandonment-recovery'
			),
		},
		{
			label: __( 'Recoverable Orders', 'woo-cart-abandonment-recovery' ),
			value: dashboardData?.recoverable_orders || '0',
			tooltip: __(
				'The number of orders that can be recovered.',
				'woo-cart-abandonment-recovery'
			),
		},
		{
			label: __( 'Lost Orders', 'woo-cart-abandonment-recovery' ),
			value: dashboardData?.lost_orders || '0',
			tooltip: __(
				'The number of orders that have been lost.',
				'woo-cart-abandonment-recovery'
			),
		},
		{
			label: __( 'Recovery Rate', 'woo-cart-abandonment-recovery' ),
			value: dashboardData?.recovery_rate || '0.00%',
			tooltip: __(
				'The percentage of orders that have been recovered.',
				'woo-cart-abandonment-recovery'
			),
			color:
				currentRecoveryRate > previousRecoveryRate
					? 'text-badge-color-green'
					: currentRecoveryRate < previousRecoveryRate &&
					  'text-support-error',
			icon: trendIcon && (
				<InfoTip content={ trendText }>{ trendIcon }</InfoTip>
			),
		},
	];

	const chartData = dashboardData?.revenue_chart_data || [];

	return (
		<DashboardCard
			title={ __( 'Overview', 'woo-cart-abandonment-recovery' ) }
			action={
				<div className="flex items-center gap-2">
					{ isFiltered && (
						<Button
							variant="ghost"
							size="sm"
							destructive
							className="whitespace-nowrap [@media(pointer:coarse)]:min-h-11"
							icon={ <XMarkIcon /> }
							onClick={ onClearFilter }
						>
							{ __( 'Clear Filter', 'woo-cart-abandonment-recovery' ) }
						</Button>
					) }
					<DateRange
						selectedRange={ selectedRange }
						setSelectedRange={ handleDateRangeChange }
						disabled={ isDashboardLoading }
						disableFutureDates
					/>
				</div>
			}
		>
			<span className="sr-only" role="status">
				{ isDashboardLoading
					? __( 'Loading…', 'woo-cart-abandonment-recovery' )
					: '' }
			</span>
			<div className="p-1 rounded-lg flex flex-col gap-2 bg-light-background">
				<div className="grid grid-cols-1 sm:grid-cols-3 xl:grid-cols-6 gap-2">
					{ metricsData.map( ( item, index ) => (
						<div
							key={ index }
							className="p-3 rounded-md shadow-sm bg-background-primary flex-1 flex flex-col gap-2"
						>
							<Text
								as="div"
								size={ 14 }
								weight={ 500 }
								color="secondary"
								className="inline-flex items-center"
							>
								{ item.label }{ ' ' }
								<span className="ml-1 inline-flex">
									<InfoTip content={ item.tooltip }>
										<InformationCircleIcon className="size-3.5 text-icon-secondary" />
									</InfoTip>
								</span>
							</Text>
							{ isDashboardLoading ? (
								<SkeletonLoader
									height="2rem"
									className="mt-1"
								/>
							) : (
								<div
									className={ cn(
										'flex gap-1 justify-between text-3xl font-semibold text-text-primary',
										item.color
									) }
								>
									{ item.value }
									{ item.icon && <span>{ item.icon }</span> }
								</div>
							) }
						</div>
					) ) }
				</div>
				<div className="p-3 flex flex-col gap-6 rounded-md shadow-sm bg-background-primary">
					{ isDashboardLoading ? (
						<SkeletonLoader height="300px" />
					) : (
						<>
							<div className="flex gap-2">
								{ [
									__( 'Recoverable Revenue', 'woo-cart-abandonment-recovery' ),
									__( 'Recovered Revenue', 'woo-cart-abandonment-recovery' ),
								].map( ( name, i ) => (
									<div
										key={ CHART_SERIES[ i ].key }
										className="p-1 flex gap-2 items-center"
									>
										<div
											className={ cn( 'h-3 w-3', CHART_SERIES[ i ].swatch ) }
										></div>
										<span className="text-text-secondary text-sm font-medium">
											{ name }
										</span>
									</div>
								) ) }
							</div>
							<div aria-hidden="true">
								<LineChart
									data={ chartData }
									dataKeys={ CHART_SERIES.map( ( line ) => line.key ) }
									colors={ CHART_SERIES.map( ( line ) => ( {
										stroke: line.stroke,
									} ) ) }
									showXAxis={ true }
									showYAxis={ true }
									showTooltip={ true }
									showCartesianGrid={ true }
									xAxisDataKey="day"
									xAxisTickFormatter={ formatXAxis }
									yAxisTickFormatter={ formatYAxis }
									chartWidth="100%"
									chartHeight={ 300 }
									lineChartWrapperProps={ {
										margin: {
											left: -12,
											right: 0,
											top: 0,
											bottom: 0,
										},
									} }
									xAxisFontSize="sm"
									strokeDasharray="0 0"
								/>
							</div>
							<table className="sr-only">
								<caption>
									{ __(
										'Revenue by day',
										'woo-cart-abandonment-recovery'
									) }
								</caption>
								<thead>
									<tr>
										<th scope="col">
											{ __( 'Day', 'woo-cart-abandonment-recovery' ) }
										</th>
										<th scope="col">
											{ __(
												'Recoverable Revenue',
												'woo-cart-abandonment-recovery'
											) }
										</th>
										<th scope="col">
											{ __(
												'Recovered Revenue',
												'woo-cart-abandonment-recovery'
											) }
										</th>
									</tr>
								</thead>
								<tbody>
									{ chartData.map( ( row ) => (
										<tr key={ row.day }>
											<th scope="row">
												{ formatXAxis( row.day ) }
											</th>
											<td>{ row.recoverable }</td>
											<td>{ row.recovered }</td>
										</tr>
									) ) }
								</tbody>
							</table>
						</>
					) }
				</div>
			</div>
		</DashboardCard>
	);
};

Overview.propTypes = {
	dashboardData: PropTypes.object,
	isDashboardLoading: PropTypes.bool,
	selectedRange: PropTypes.shape( {
		from: PropTypes.instanceOf( Date ),
		to: PropTypes.instanceOf( Date ),
	} ),
	handleDateRangeChange: PropTypes.func.isRequired,
	isFiltered: PropTypes.bool,
	onClearFilter: PropTypes.func.isRequired,
};

export default Overview;
