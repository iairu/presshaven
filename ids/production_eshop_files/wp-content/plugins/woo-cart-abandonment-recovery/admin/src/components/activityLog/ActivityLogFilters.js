import { Select, Input, Button } from '@bsf/force-ui';
import {
	MagnifyingGlassIcon,
	CloudArrowDownIcon,
} from '@heroicons/react/24/outline';
import { __ } from '@wordpress/i18n';

import ClearFiltersButton from '@Components/common/ClearFiltersButton';
import DateRange from '@Components/fields/DateRange';
import { CHANNEL_OPTIONS, ACTIVITY_STATUS_OPTIONS } from './constants';

const ActivityLogFilters = ( {
	activeTab,
	channel,
	status,
	dateRange,
	search,
	onChannelChange,
	onStatusChange,
	onDateRangeChange,
	onSearchChange,
	onClear,
	onExport,
	disableExport = false,
	filtersApplied = false,
	disabled = false,
} ) => {
	// Scheduled jobs are always pending, so a status filter is meaningless there.
	const showStatusFilter = activeTab !== 'scheduled';
	const statusOptions = ACTIVITY_STATUS_OPTIONS;

	return (
		<div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center lg:min-w-0 lg:flex-1 lg:justify-end">
			{ filtersApplied && ! disabled && (
				<ClearFiltersButton onClick={ onClear } />
			) }
			<Input
				value={ search }
				onChange={ onSearchChange }
				placeholder={ __(
					'Search recipient…',
					'woo-cart-abandonment-recovery'
				) }
				prefix={ <MagnifyingGlassIcon className="h-6 w-6 text-gray-500" /> }
				size="sm"
				type="search"
				aria-label={ __(
					'Search recipient',
					'woo-cart-abandonment-recovery'
				) }
				className="w-full sm:w-48 [&_input]:min-h-0"
				disabled={ disabled }
			/>
			<div className="w-full sm:w-auto">
				<Select
					value={ channel?.title }
					onChange={ onChannelChange }
					size="sm"
					disabled={ disabled }
				>
					<Select.Button
						className="w-full sm:w-36 text-gray-500"
						aria-label={ __(
							'Filter by channel',
							'woo-cart-abandonment-recovery'
						) }
					/>
					<Select.Options>
						{ CHANNEL_OPTIONS.map( ( option ) => (
							<Select.Option key={ option.id } value={ option }>
								{ option.title }
							</Select.Option>
						) ) }
					</Select.Options>
				</Select>
			</div>
			{ showStatusFilter && (
				<div className="w-full sm:w-auto">
					<Select
						value={ status?.title }
						onChange={ onStatusChange }
						size="sm"
						disabled={ disabled }
					>
						<Select.Button
							className="w-full sm:w-36 text-gray-500"
							aria-label={ __(
								'Filter by status',
								'woo-cart-abandonment-recovery'
							) }
						/>
						<Select.Options>
							{ statusOptions.map( ( option ) => (
								<Select.Option key={ option.id } value={ option }>
									{ option.title }
								</Select.Option>
							) ) }
						</Select.Options>
					</Select>
				</div>
			) }
			<DateRange
				selectedRange={ dateRange }
				setSelectedRange={ onDateRangeChange }
				// The log only holds what already happened. Scheduled jobs are upcoming, so they keep future days.
				disableFutureDates={ activeTab === 'activity' }
				disabled={ disabled }
			/>
			{ activeTab === 'activity' && (
				<Button
					iconPosition="left"
					size="sm"
					tag="button"
					type="button"
					variant="primary"
					onClick={ onExport }
					disabled={ disabled || disableExport }
					icon={ <CloudArrowDownIcon aria-hidden="true" /> }
				>
					{ __( 'Export', 'woo-cart-abandonment-recovery' ) }
				</Button>
			) }
		</div>
	);
};

export default ActivityLogFilters;

