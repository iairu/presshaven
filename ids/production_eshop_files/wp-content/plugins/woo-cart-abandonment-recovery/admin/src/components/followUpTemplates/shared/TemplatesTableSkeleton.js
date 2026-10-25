import { Table } from '@bsf/force-ui';
import { __ } from '@wordpress/i18n';

import FeatureBadge from '@Components/common/FeatureBadge';
import SkeletonLoader from '@Components/common/skeletons/SkeletonLoader';
import {
	ActionPlaceholders,
	CheckboxCell,
	SkeletonRows,
	SkeletonTableFrame,
	TextBar,
} from '@Components/common/skeletons/TableSkeletonParts';

import { TEMPLATES_TABLE_CLASS } from './utils';

// A default install ships three templates per channel, so that is what the skeleton stands in for.
const SKELETON_ROWS = 3;

// Height of a loaded row. The last one is half a pixel shorter because it has no divider below.
const ROW_HEIGHT = 'h-[59px]';
const LAST_ROW_HEIGHT = 'h-[58.5px]';

// Stand-ins for the data. Each is laid out invisibly at the width of a typical value, so the
// columns come out the width they will have once the list loads.
const SAMPLE_NAME = 'Sample Email Template 3';
const SAMPLE_TRIGGER = '30 Minutes';
const SAMPLE_COUNT = '288';
const SAMPLE_RATE = '34.09%';

/**
 * Loading state of a template list: the table itself, with grey bars where the data goes.
 *
 * The header repeats the real one and the cells reserve the room real values take, so the
 * layout holds still when the list arrives.
 *
 * @param {Object}   props
 * @param {string[]} props.metricLabels Headings of the metric columns, in order. The first is
 *                                      a count (Sent), the rest are rates.
 * @param {boolean}  props.showBadge    Whether the metric headings carry the Pro badge.
 * @return {JSX.Element} The skeleton table.
 */
const TemplatesTableSkeleton = ( { metricLabels, showBadge = false } ) => (
	<SkeletonTableFrame
		label={ __( 'Loading templates…', 'woo-cart-abandonment-recovery' ) }
		className={ TEMPLATES_TABLE_CLASS }
	>
		<Table.Head>
			<CheckboxCell as="th" />
			<Table.HeadCell>
				{ __( 'Template Name', 'woo-cart-abandonment-recovery' ) }
			</Table.HeadCell>
			<Table.HeadCell>
				{ __( 'Trigger After', 'woo-cart-abandonment-recovery' ) }
			</Table.HeadCell>
			{ metricLabels.map( ( label ) => (
				<Table.HeadCell key={ label }>
					<div className="flex items-center justify-center gap-1.5">
						{ label }
						{ showBadge && (
							<FeatureBadge
								feature={ __(
									'PRO',
									'woo-cart-abandonment-recovery'
								) }
							/>
						) }
					</div>
				</Table.HeadCell>
			) ) }
			<Table.HeadCell>
				{ __( 'Status', 'woo-cart-abandonment-recovery' ) }
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
						<TextBar sample={ SAMPLE_TRIGGER } />
					</Table.Cell>
					{ metricLabels.map( ( label, index ) => (
						<Table.Cell key={ label } className="text-center">
							<TextBar
								sample={ index === 0 ? SAMPLE_COUNT : SAMPLE_RATE }
							/>
						</Table.Cell>
					) ) }
					<Table.Cell>
						<SkeletonLoader
							height="24px"
							width="44px"
							className="rounded-full"
						/>
					</Table.Cell>
					<Table.Cell>
						<ActionPlaceholders count={ 3 } />
					</Table.Cell>
				</>
			) }
		/>
	</SkeletonTableFrame>
);

export default TemplatesTableSkeleton;
