import { forwardRef } from '@wordpress/element';

import { cn } from '@Utils/helper';

/**
 * The first cell of a table row: text that opens the row's details.
 *
 * A real button, so it takes focus and Enter / Space without extra handlers. It reads as body
 * text and turns brand colored on hover and focus. It passes its ref and extra props on, so a
 * tooltip can wrap it; a `className` from the tooltip is added to the button's own classes, never
 * in place of them.
 *
 * @param {Object}   props
 * @param {Function} props.onClick     Opens the row.
 * @param {string}   [props.className] Extra classes, such as one a wrapping tooltip adds.
 * @param {Node}     props.children    The visible text.
 * @param {Object}   ref
 * @return {JSX.Element} The button.
 */
const TableLinkButton = ( { onClick, className, children, ...rest }, ref ) => (
	<button
		type="button"
		ref={ ref }
		onClick={ onClick }
		{ ...rest }
		className={ cn(
			'm-0 max-w-full whitespace-nowrap cursor-pointer rounded-sm border-0 bg-transparent p-0 text-left [font:inherit] text-text-primary hover:text-flamingo-400 hover:underline underline-offset-2 focus-visible:text-flamingo-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus [@media(pointer:coarse)]:min-h-11',
			className
		) }
	>
		{ children }
	</button>
);

export default forwardRef( TableLinkButton );
