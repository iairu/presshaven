import { Title } from '@bsf/force-ui';
import { __, _n, sprintf } from '@wordpress/i18n';

import SectionWrapper from '@Components/common/SectionWrapper';
import { ProUpgradeCta } from '@Components/pro';
import TablePagination from '@Components/common/TablePagination';

import ActivityLogFilters from './ActivityLogFilters';

const PAGE_SIZES = [ 10, 20, 50, 100 ];

const buildExportUrl = ( baseUrl, params ) => {
	if ( ! baseUrl ) {
		return '#';
	}
	const qs = new URLSearchParams();
	Object.entries( params ).forEach( ( [ k, v ] ) => {
		if ( v !== undefined && v !== null && v !== '' ) {
			qs.append( k, v );
		}
	} );
	const sep = baseUrl.includes( '?' ) ? '&' : '?';
	const tail = qs.toString();
	return tail ? baseUrl + sep + tail : baseUrl;
};

const ActivityLogPageShell = ( {
	title,
	type,
	state,
	upgradeDescription,
	upgradeCampaign,
	canExport = false,
	tableRows,
	children,
} ) => {
	const {
		isBlocked,
		channel,
		status,
		dateRange,
		search,
		currentPage,
		itemsPerPage,
		filtersApplied,
		loadFailed,
		isInitialLoading,
		payload,
		proCfg,
		total,
		setChannel,
		setStatus,
		setDateRange,
		setSearch,
		setCurrentPage,
		setItemsPerPage,
		clearFilters,
	} = state;

	const handleExport = () => {
		if ( ! canExport || ! proCfg?.export_url ) {
			return;
		}
		const url = buildExportUrl( proCfg.export_url, {
			channel: payload.channel,
			status: payload.status,
			search: payload.search,
			date_from: payload.date_from,
			date_to: payload.date_to,
		} );
		window.open( url, '_blank' );
	};

	const totalPages = Math.max( 1, Math.ceil( total / itemsPerPage ) );

	return (
		<div className="p-4 md:p-8">
			<SectionWrapper className="flex flex-col gap-4">
				<div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
					<Title
						size="sm"
						tag="h2"
						title={ title }
						className="[&_h2]:text-gray-900 shrink-0"
					/>
					<ActivityLogFilters
						activeTab={ type }
						channel={ channel }
						status={ status }
						dateRange={ dateRange }
						search={ search }
						filtersApplied={ filtersApplied }
						onChannelChange={ setChannel }
						onStatusChange={ setStatus }
						onDateRangeChange={ setDateRange }
						onSearchChange={ setSearch }
						onClear={ clearFilters }
						onExport={ handleExport }
						disabled={ isBlocked }
						disableExport={
							! canExport || isBlocked || ! tableRows.length
						}
					/>
				</div>

				<p className="sr-only" role="status">
					{ ! isBlocked &&
						! isInitialLoading &&
						! loadFailed &&
						sprintf(
							/* translators: %d: number of rows that match the search and filters */
							_n(
								'%d result found',
								'%d results found',
								total,
								'woo-cart-abandonment-recovery'
							),
							total
						) }
				</p>

				<div className="relative">
					{ /* The sample rows behind the upgrade message are decoration, not data. */ }
					<div
						{ ...( isBlocked
							? { inert: '', 'aria-hidden': true }
							: {} ) }
					>
						{ children }
					</div>

					{ isBlocked && (
						<ProUpgradeCta
							isVisible={ true }
							highlightText={ __(
								'Unlock Pro Features',
								'woo-cart-abandonment-recovery'
							) }
							mainTitle={ __(
								'Cart Abandonment Recovery Pro is Here 🔥',
								'woo-cart-abandonment-recovery'
							) }
							description={ upgradeDescription }
							usps={ [
								__(
									'Activity Log & Scheduled Jobs',
									'woo-cart-abandonment-recovery'
								),
								__(
									'SMS + WhatsApp Followups',
									'woo-cart-abandonment-recovery'
								),
								__(
									'Smart Rules',
									'woo-cart-abandonment-recovery'
								),
								__(
									'Advanced Automations',
									'woo-cart-abandonment-recovery'
								),
								__(
									'And More…',
									'woo-cart-abandonment-recovery'
								),
							] }
							actionBtnUrlArgs={
								'utm_source=wcar-dashboard&utm_medium=free-wcar&utm_campaign=' +
							upgradeCampaign
							}
							footerMessage={ '' }
							backgroundBlur={ true }
						/>
					) }
				</div>

				{ ! isBlocked && ! loadFailed && total > 0 && (
					<TablePagination
						itemsPerPage={ itemsPerPage }
						onItemsPerPageChange={ ( value ) => {
							setItemsPerPage( Number( value ) );
							setCurrentPage( 1 );
						} }
						currentPage={ currentPage }
						totalPages={ totalPages }
						onPageChange={ setCurrentPage }
						pageSizes={ PAGE_SIZES }
					/>
				) }
			</SectionWrapper>
		</div>
	);
};

export default ActivityLogPageShell;
