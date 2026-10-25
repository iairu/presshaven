import { cn } from '@Utils/helper';

/**
 * Classes for a Force UI table with a selection checkbox column that never wraps.
 *
 * Force UI sizes the checkbox column with `w-11` plus `px-5.5` but the cells render with
 * content-box sizing here, so the column grew to ~88px. `table-fixed` then hands the
 * checkbox column that width. Border-box keeps it at 44px; the checkbox is centered by
 * Force UI, so the padding is not needed. `:not([colspan])` spares the no-match row.
 *
 * Every column stays on every screen size, and nothing wraps. On narrow screens the table
 * scrolls sideways inside its card; below xl the cells give up some side padding to keep that
 * scroll short.
 */
export const SELECTABLE_TABLE_CLASS = cn(
	'whitespace-nowrap [&_tr>:first-child:not([colspan])]:box-border [&_tr>:first-child:not([colspan])]:w-11 [&_tr>:first-child:not([colspan])]:min-w-11 max-xl:[&_th]:px-2 max-xl:[&_td]:px-2',
	// Touch screens: the 20px checkbox grows an invisible 44px target, the size of its cell.
	"[@media(pointer:coarse)]:[&_tr>:first-child_label]:relative [@media(pointer:coarse)]:[&_tr>:first-child_label]:after:absolute [@media(pointer:coarse)]:[&_tr>:first-child_label]:after:-inset-3 [@media(pointer:coarse)]:[&_tr>:first-child_label]:after:content-['']"
);

/**
 * Lifts an icon button to the 44px touch size on touch screens and leaves it compact for a mouse.
 */
export const COARSE_TARGET_CLASS =
	'[@media(pointer:coarse)]:min-h-11 [@media(pointer:coarse)]:min-w-11';

/**
 * The outlined primary button used for actions on the report details page, such as going back or
 * scheduling a channel's follow-ups again.
 */
export const OUTLINE_PRIMARY_BUTTON_CLASS = cn(
	'whitespace-nowrap bg-primary-25 text-primary-600 outline-primary-300 hover:bg-primary-25 hover:outline-primary-300',
	COARSE_TARGET_CLASS
);

/**
 * Row classes. The transition is always on so the highlight fades out as well as in.
 *
 * Force UI paints selected and hovered rows with the same grey as the table header, so a
 * selected row gets a faint brand tint instead. The duplicate highlight is stronger and wins.
 *
 * @param {Object}  state
 * @param {boolean} state.isHighlighted Whether the row was just duplicated.
 * @param {boolean} state.isSelected    Whether the row's checkbox is ticked.
 * @return {string} Class names for Table.Row.
 */
export const getRowClass = ( { isHighlighted = false, isSelected = false } ) =>
	cn(
		'transition-colors duration-500 motion-reduce:transition-none',
		isSelected && 'bg-primary-25 hover:bg-primary-25',
		isHighlighted && 'bg-flamingo-200/40 hover:bg-flamingo-200/40'
	);
