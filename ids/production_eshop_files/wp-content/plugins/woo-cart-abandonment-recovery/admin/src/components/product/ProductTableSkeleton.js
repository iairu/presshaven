import { Table } from '@bsf/force-ui';
import { InformationCircleIcon } from '@heroicons/react/24/outline';
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

// Eight rows fill the screen without a long tail.
const SKELETON_ROWS = 8;

// Height of a loaded row: the 48px product image and the cell padding around it.
const ROW_HEIGHT = 'h-[79px]';

// Stand-ins for the data. Each is laid out invisibly at the width of a typical value, so the
// columns come out the width they will have once the products load.
const SAMPLE_NAME = 'Cotton Hoodie Blue (#13352)';
const SAMPLE_COUNT = '6 ($30.00)';

// The same box as a column heading's hint icon, so the heading keeps its width.
const HintSpace = () => (
	<span className="ml-1 inline-flex h-6 w-6 items-center justify-center">
		<InformationCircleIcon
			className="h-4 w-4 text-gray-500"
			aria-hidden="true"
		/>
	</span>
);

const Heading = ( { children, withHint = false } ) => (
	<Table.HeadCell>
		<div className="flex items-center">
			{ children }
			{ withHint && <HintSpace /> }
		</div>
	</Table.HeadCell>
);

/**
 * Loading state of the Product Reports table: the table itself, with grey bars where the data goes.
 *
 * The header repeats the real one and the cells reserve the room real values take, so the
 * layout holds still when the products arrive.
 *
 * @return {JSX.Element} The skeleton table.
 */
const ProductTableSkeleton = () => (
	<SkeletonTableFrame
		label={ __( 'Loading products…', 'woo-cart-abandonment-recovery' ) }
		className={ SELECTABLE_TABLE_CLASS }
	>
		<Table.Head>
			<CheckboxCell as="th" />
			<Heading>
				{ __( 'Product Name', 'woo-cart-abandonment-recovery' ) }
			</Heading>
			<Heading withHint>
				{ __( 'Times Abandoned', 'woo-cart-abandonment-recovery' ) }
			</Heading>
			<Heading withHint>
				{ __( 'Times Recovered', 'woo-cart-abandonment-recovery' ) }
			</Heading>
			<Table.HeadCell className="text-right">
				{ __( 'Actions', 'woo-cart-abandonment-recovery' ) }
			</Table.HeadCell>
		</Table.Head>
		<SkeletonRows
			count={ SKELETON_ROWS }
			rowHeight={ ROW_HEIGHT }
			lastRowHeight={ ROW_HEIGHT }
			renderCells={ () => (
				<>
					<CheckboxCell as="td" />
					<Table.Cell>
						<div className="flex w-fit items-center gap-2">
							<SkeletonLoader
								height="48px"
								width="48px"
								className="shrink-0"
							/>
							<TextBar sample={ SAMPLE_NAME } />
						</div>
					</Table.Cell>
					<Table.Cell>
						<TextBar sample={ SAMPLE_COUNT } />
					</Table.Cell>
					<Table.Cell>
						<TextBar sample={ SAMPLE_COUNT } />
					</Table.Cell>
					<Table.Cell>
						<ActionPlaceholders count={ 2 } />
					</Table.Cell>
				</>
			) }
		/>
	</SkeletonTableFrame>
);

export default ProductTableSkeleton;
