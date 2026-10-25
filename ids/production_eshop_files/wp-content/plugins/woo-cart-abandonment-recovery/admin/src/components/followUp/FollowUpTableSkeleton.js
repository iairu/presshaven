import { Table } from '@bsf/force-ui';
import { __ } from '@wordpress/i18n';

import SkeletonLoader from '@Components/common/skeletons/SkeletonLoader';
import {
	ActionPlaceholders,
	CheckboxCell,
	SkeletonRows,
	SkeletonTableFrame,
	TextBar,
} from '@Components/common/skeletons/TableSkeletonParts';
import { SELECTABLE_TABLE_CLASS } from '@Components/common/tableStyles';

// A page of reports holds up to 20 rows; ten is enough to fill the screen without a long tail.
const SKELETON_ROWS = 10;

// Height of a loaded row. The last one is half a pixel shorter because it has no divider below.
const ROW_HEIGHT = 'h-[53px]';
const LAST_ROW_HEIGHT = 'h-[52.5px]';

// Stand-ins for the data. Each is laid out invisibly at the width of a typical value, so the
// columns come out the width they will have once the reports load.
const SAMPLE_NAME = 'Olivia Johnson';
const SAMPLE_EMAIL = 'olivia.haddad33@gmail.com';
const SAMPLE_TOTAL = '$25.00';
const SAMPLE_DATE = 'September 22, 2026 12:36 pm';

/**
 * Loading state of the Reports table: the table itself, with grey bars where the data goes.
 *
 * The header repeats the real one and the cells reserve the room real values take, so the
 * layout holds still when the reports arrive.
 *
 * @param {Object} props
 * @param {number} props.actionCount How many icon buttons the Actions column shows (View,
 *                                   Unsubscribe, Delete, plus Blacklist with Pro).
 * @return {JSX.Element} The skeleton table.
 */
const FollowUpTableSkeleton = ( { actionCount = 4 } ) => (
	<SkeletonTableFrame
		label={ __( 'Loading reports…', 'woo-cart-abandonment-recovery' ) }
		className={ SELECTABLE_TABLE_CLASS }
	>
		<Table.Head>
			<CheckboxCell as="th" />
			<Table.HeadCell>
				{ __( 'User Name', 'woo-cart-abandonment-recovery' ) }
			</Table.HeadCell>
			<Table.HeadCell>
				{ __( 'Email To', 'woo-cart-abandonment-recovery' ) }
			</Table.HeadCell>
			<Table.HeadCell>
				{ __( 'Cart Total', 'woo-cart-abandonment-recovery' ) }
			</Table.HeadCell>
			<Table.HeadCell>
				{ __( 'Order Status', 'woo-cart-abandonment-recovery' ) }
			</Table.HeadCell>
			<Table.HeadCell>
				{ __( 'Date & Time', 'woo-cart-abandonment-recovery' ) }
			</Table.HeadCell>
			<Table.HeadCell className="text-right">
				{ __( 'Actions', 'woo-cart-abandonment-recovery' ) }
			</Table.HeadCell>
		</Table.Head>
		<SkeletonRows
			count={ SKELETON_ROWS }
			rowHeight={ ROW_HEIGHT }
			lastRowHeight={ LAST_ROW_HEIGHT }
			renderCells={ () => (
				<>
					<CheckboxCell as="td" />
					<Table.Cell>
						<TextBar sample={ SAMPLE_NAME } />
					</Table.Cell>
					<Table.Cell>
						<TextBar sample={ SAMPLE_EMAIL } />
					</Table.Cell>
					<Table.Cell>
						<TextBar sample={ SAMPLE_TOTAL } />
					</Table.Cell>
					<Table.Cell>
						<SkeletonLoader
							height="24px"
							width="84px"
							className="rounded-full"
						/>
					</Table.Cell>
					<Table.Cell>
						<TextBar sample={ SAMPLE_DATE } />
					</Table.Cell>
					<Table.Cell>
						<ActionPlaceholders count={ actionCount } />
					</Table.Cell>
				</>
			) }
		/>
	</SkeletonTableFrame>
);

export default FollowUpTableSkeleton;
