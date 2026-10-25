import { Table } from '@bsf/force-ui';

import { cn } from '@Utils/helper';

import SkeletonLoader from './SkeletonLoader';

/**
 * Pulsing bar the size of `sample` set in the table's text. The sample is laid out invisibly, so
 * the column comes out the width real values will give it.
 *
 * @param {Object} props
 * @param {string} props.sample Typical value for the cell.
 * @return {JSX.Element} The bar.
 */
export const TextBar = ( { sample } ) => (
	<span className="relative inline-block max-w-full align-top">
		<span className="invisible">{ sample }</span>
		<SkeletonLoader className="absolute inset-0" height="100%" />
	</span>
);

/**
 * Same box as Force UI's row checkbox cell, so the first column keeps its width.
 *
 * @param {Object} props
 * @param {string} props.as `th` or `td`.
 * @return {JSX.Element} The cell.
 */
export const CheckboxCell = ( { as: Tag } ) => (
	<Tag className="relative px-5.5 w-11 overflow-hidden">
		<div className="absolute inset-0 grid grid-cols-1 place-content-center">
			<SkeletonLoader height="16px" width="16px" className="mx-auto" />
		</div>
	</Tag>
);

/**
 * Row of icon-button placeholders for an Actions cell.
 *
 * @param {Object} props
 * @param {number} props.count How many buttons the loaded row shows.
 * @return {JSX.Element} The placeholders.
 */
export const ActionPlaceholders = ( { count } ) => (
	<div className="ml-auto flex w-fit items-center gap-2">
		{ [ ...Array( count ) ].map( ( _, index ) => (
			<SkeletonLoader key={ index } height="24px" width="24px" />
		) ) }
	</div>
);

/**
 * Wrapper every table skeleton shares: announced as one busy status, with the table itself hidden
 * from assistive tech.
 *
 * @param {Object} props
 * @param {string} props.label     Text a screen reader announces, such as "Loading reports…".
 * @param {string} props.className Classes for the table.
 * @param {Node}   props.children  The head and body.
 * @return {JSX.Element} The skeleton table.
 */
export const SkeletonTableFrame = ( { label, className, children } ) => (
	<div role="status" aria-busy="true">
		<span className="sr-only">{ label }</span>
		<Table className={ className } aria-hidden="true">
			{ children }
		</Table>
	</div>
);

/**
 * Body of `count` rows, each as tall as a loaded row.
 *
 * @param {Object}   props
 * @param {number}   props.count         How many rows.
 * @param {string}   props.rowHeight     Height class of a loaded row.
 * @param {string}   props.lastRowHeight Height class of the last row, which has no divider below it.
 * @param {Function} props.renderCells   Gets the row index and returns the row's cells.
 * @return {JSX.Element} The body.
 */
export const SkeletonRows = ( {
	count,
	rowHeight,
	lastRowHeight,
	renderCells,
} ) => (
	<Table.Body>
		{ [ ...Array( count ) ].map( ( _, row ) => (
			<Table.Row
				key={ row }
				className={ cn(
					row === count - 1 ? lastRowHeight : rowHeight
				) }
			>
				{ renderCells( row ) }
			</Table.Row>
		) ) }
	</Table.Body>
);
