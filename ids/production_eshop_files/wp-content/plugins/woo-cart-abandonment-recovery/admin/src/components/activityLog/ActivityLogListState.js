import { Button, Table } from '@bsf/force-ui';
import { __ } from '@wordpress/i18n';

import { EmptyBlock } from '@Components/common/empty-blocks';
import LoadFailedBlock from '@Components/common/LoadFailedBlock';
import NoResultsBlock from '@Components/common/NoResultsBlock';
import ScrollableTable from '@Components/common/ScrollableTable';
import {
	SkeletonRows,
	SkeletonTableFrame,
	TextBar,
} from '@Components/common/skeletons/TableSkeletonParts';

// Height of a loaded text row.
const ROW_HEIGHT = 'h-[53px]';

// A long list needs no more than a screenful of placeholders.
const MAX_SKELETON_ROWS = 10;

const ActivityLogSkeleton = ( { columns, rowCount, label } ) => (
	<SkeletonTableFrame
		label={ label }
		className="whitespace-nowrap max-xl:[&_th]:px-2 max-xl:[&_td]:px-2"
	>
		<Table.Head>
			{ columns.map( ( column ) => (
				<Table.HeadCell key={ column.heading }>
					{ column.heading }
				</Table.HeadCell>
			) ) }
		</Table.Head>
		<SkeletonRows
			count={ Math.min( rowCount, MAX_SKELETON_ROWS ) }
			rowHeight={ ROW_HEIGHT }
			lastRowHeight={ ROW_HEIGHT }
			renderCells={ () =>
				columns.map( ( column ) => (
					<Table.Cell key={ column.heading }>
						<TextBar sample={ column.sample } />
					</Table.Cell>
				) )
			}
		/>
	</SkeletonTableFrame>
);

/**
 * Everything that can stand in for the rows of an activity or scheduled-jobs table: the loading
 * skeleton, a failed request, no data at all, filters that match nothing, and the table itself.
 *
 * @param {Object}   props
 * @param {Object}   props.state        What `useActivityLogData` returns.
 * @param {Object[]} props.rows         The rows to show.
 * @param {Object[]} props.columns      The skeleton's columns: `{ heading, sample }`.
 * @param {string}   props.label        Names the table for assistive tech.
 * @param {string}   props.loadingLabel What a screen reader hears while it loads.
 * @param {string}   props.failedTitle  Heading of the failed-request message.
 * @param {string}   props.emptyTitle   Heading shown when there is no data at all.
 * @param {string}   props.emptyText    Description shown when there is no data at all.
 * @param {Node}     props.children     The table, given the same rows.
 * @return {JSX.Element} The state to show.
 */
const ActivityLogListState = ( {
	state,
	rows,
	columns,
	label,
	loadingLabel,
	failedTitle,
	emptyTitle,
	emptyText,
	children,
} ) => {
	const {
		isBlocked,
		isInitialLoading,
		isRefreshing,
		loadFailed,
		filtersApplied,
		itemsPerPage,
		reload,
		clearFilters,
	} = state;

	// The Pro preview shows its sample rows as they are.
	if ( isBlocked ) {
		return <ScrollableTable label={ label }>{ children }</ScrollableTable>;
	}

	if ( isInitialLoading ) {
		return (
			<ActivityLogSkeleton
				columns={ columns }
				rowCount={ itemsPerPage }
				label={ loadingLabel }
			/>
		);
	}

	if ( loadFailed ) {
		return <LoadFailedBlock title={ failedTitle } onRetry={ reload } />;
	}

	if ( ! rows.length ) {
		if ( filtersApplied ) {
			return (
				<NoResultsBlock
					title={ __(
						'Nothing matches these filters',
						'woo-cart-abandonment-recovery'
					) }
					description={ __(
						'Try a different search, channel, status or date range.',
						'woo-cart-abandonment-recovery'
					) }
					action={
						<Button
							size="sm"
							variant="outline"
							onClick={ clearFilters }
						>
							{ __(
								'Clear Filters',
								'woo-cart-abandonment-recovery'
							) }
						</Button>
					}
				/>
			);
		}
		return <EmptyBlock className="my-2" title={ emptyTitle } description={ emptyText } />;
	}

	return (
		<div
			className={ isRefreshing ? 'opacity-60 transition-opacity' : 'transition-opacity' }
			aria-busy={ isRefreshing }
		>
			<ScrollableTable label={ label }>{ children }</ScrollableTable>
		</div>
	);
};

export default ActivityLogListState;
