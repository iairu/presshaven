import { Pagination, Select } from '@bsf/force-ui';
import { __ } from '@wordpress/i18n';

import { generatePaginationPages } from '@Admin/utils/helper';
import { cn } from '@Utils/helper';
import { COARSE_TARGET_CLASS } from '@Components/common/tableStyles';

const PAGE_SIZES = [ 5, 10, 20, 50 ];

const DISABLED_STEP_CLASS =
	'opacity-50 cursor-not-allowed hover:bg-transparent focus:bg-transparent';

/**
 * Props for a Previous/Next button. Force UI only greys these out through the
 * `Pagination` root, so the button gets its own disabled look, a11y state and a
 * click guard.
 *
 * @param {boolean}  isDisabled Whether there is no page to step to.
 * @param {Function} onStep     Runs when an enabled button is clicked.
 * @return {Object} Props to spread on the button.
 */
export const getStepProps = ( isDisabled, onStep ) => ( {
	className: cn( COARSE_TARGET_CLASS, isDisabled && DISABLED_STEP_CLASS ),
	disabled: isDisabled,
	'aria-disabled': isDisabled,
	tabIndex: isDisabled ? -1 : undefined,
	onClick: ( event ) => {
		if ( isDisabled ) {
			event.preventDefault();
			return;
		}
		onStep();
	},
} );

/**
 * Footer of a paged report table: how many rows to show, and the page links.
 *
 * @param {Object}   props
 * @param {number}   props.itemsPerPage         Rows per page.
 * @param {Function} props.onItemsPerPageChange Gets the new size.
 * @param {number}   props.currentPage          Page shown, starting at 1.
 * @param {number}   props.totalPages           How many pages there are.
 * @param {Function} props.onPageChange         Gets the page to show.
 * @param {number[]} props.pageSizes            The row counts to offer.
 * @return {JSX.Element} The footer content.
 */
const TablePagination = ( {
	itemsPerPage,
	onItemsPerPageChange,
	currentPage,
	totalPages,
	onPageChange,
	pageSizes = PAGE_SIZES,
} ) => (
	<div className="flex items-center justify-between w-full">
		<div className="flex items-center gap-2">
			<span className="text-sm font-normal leading-5 text-text-secondary whitespace-nowrap">
				{ __( 'Items per page:', 'woo-cart-abandonment-recovery' ) }
			</span>
			<Select
				onChange={ onItemsPerPageChange }
				size="md"
				value={ itemsPerPage.toString() }
			>
				<Select.Button
					aria-label={ __(
						'Items per page',
						'woo-cart-abandonment-recovery'
					) }
				/>
				<Select.Options>
					{ pageSizes.map( ( size ) => (
						<Select.Option key={ size } value={ String( size ) }>
							{ size }
						</Select.Option>
					) ) }
				</Select.Options>
			</Select>
		</div>
		<Pagination
			className="w-fit"
			aria-label={ __( 'Pagination', 'woo-cart-abandonment-recovery' ) }
		>
			<Pagination.Content>
				<Pagination.Previous
					{ ...getStepProps( currentPage <= 1, () =>
						onPageChange( currentPage - 1 )
					) }
				/>
				{ generatePaginationPages( totalPages, currentPage ).map(
					( page, index ) =>
						page === 'ellipsis' || page === 'ellipsis-end' ? (
							<Pagination.Ellipsis key={ `ellipsis-${ index }` } />
						) : (
							<Pagination.Item
								key={ page }
								isActive={ currentPage === page }
								onClick={ () => onPageChange( page ) }
								className={ cn(
									COARSE_TARGET_CLASS,
									currentPage === page &&
										'bg-flamingo-50 text-flamingo-400'
								) }
							>
								{ page }
							</Pagination.Item>
						)
				) }
				<Pagination.Next
					{ ...getStepProps( currentPage >= totalPages, () =>
						onPageChange( currentPage + 1 )
					) }
				/>
			</Pagination.Content>
		</Pagination>
	</div>
);

export default TablePagination;
