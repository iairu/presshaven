import { Button, DatePicker } from '@bsf/force-ui';
import { CalendarIcon } from '@heroicons/react/24/outline';
import { __, sprintf } from '@wordpress/i18n';
import { cn, formatDateRange } from '@Utils/helper';
import { useState, useEffect } from 'react';
import {
	useFloating,
	useClick,
	useDismiss,
	useRole,
	useInteractions,
	autoUpdate,
	offset,
	flip,
	shift,
	size,
	FloatingPortal,
} from '@floating-ui/react';

// Below this width the presets sidebar plus a calendar no longer fit on screen.
const NARROW_QUERY = '(max-width: 639px)';

const useIsNarrow = () => {
	const [ isNarrow, setIsNarrow ] = useState(
		() => window.matchMedia( NARROW_QUERY ).matches
	);

	useEffect( () => {
		const media = window.matchMedia( NARROW_QUERY );
		const onChange = ( event ) => setIsNarrow( event.matches );
		media.addEventListener( 'change', onChange );
		return () => media.removeEventListener( 'change', onChange );
	}, [] );

	return isNarrow;
};

/**
 * Range picker in a popover. `selectedRange` is the value the parent keeps; `placeholder` is a
 * `{ from, to }` range shown while that value is empty, and selected when the picker opens. It is
 * never passed to `setSelectedRange` until the user applies a range.
 *
 * @param {Object}                   props
 * @param {{from: ?Date, to: ?Date}} props.selectedRange        The range the parent holds, empty when none is picked.
 * @param {Function}                 props.setSelectedRange     Receives the range the user applies.
 * @param {{from: Date, to: Date}}   [props.placeholder]        Range to show and select while `selectedRange` is empty.
 * @param {string}                   [props.className]
 * @param {boolean}                  [props.disabled]
 * @param {boolean}                  [props.disableFutureDates] Block days after today, for reports that only hold past data. Leave off for upcoming items.
 * @return {JSX.Element} The trigger button and its picker.
 */
const DateRange = ( {
	selectedRange,
	setSelectedRange,
	placeholder,
	className = '',
	disabled,
	disableFutureDates = false,
} ) => {
	const [ isOpen, setIsOpen ] = useState( false );
	const [ localRange, setLocalRange ] = useState( selectedRange );
	// What the button and the picker show: the value, or else the placeholder range.
	const displayRange =
		localRange?.from && localRange?.to ? localRange : placeholder;
	const isNarrow = useIsNarrow();

	// Floating UI keeps the picker anchored to the button, flips it when there
	// is no room below, and shifts it back inside the viewport.
	const { refs, floatingStyles, context } = useFloating( {
		open: isOpen,
		onOpenChange: setIsOpen,
		placement: 'bottom-end',
		whileElementsMounted: autoUpdate,
		middleware: [
			offset( 8 ),
			flip( { padding: 16 } ),
			shift( { padding: 16 } ),
			size( {
				padding: 16,
				apply( { availableWidth, elements } ) {
					elements.floating.style.maxWidth = `${ availableWidth }px`;
				},
			} ),
		],
	} );

	const click = useClick( context );
	const dismiss = useDismiss( context );
	const role = useRole( context, { role: 'dialog' } );
	const { getReferenceProps, getFloatingProps } = useInteractions( [
		click,
		dismiss,
		role,
	] );

	// Sync local state with parent
	useEffect( () => {
		setLocalRange( selectedRange );
	}, [ selectedRange ] );

	// Generate dynamic date ranges
	const getDateRanges = () => {
		const now = new Date();
		const today = new Date( now );

		// Yesterday
		const yesterday = new Date( now );
		yesterday.setDate( yesterday.getDate() - 1 );

		// This Week (Monday to Sunday)
		const thisWeekStart = new Date( now );
		const day = thisWeekStart.getDay();
		const diff = day === 0 ? 6 : day - 1; // Adjust for Monday (0 = Sunday, so Sunday - 6 = Monday)
		thisWeekStart.setDate( now.getDate() - diff );
		const thisWeekEnd = new Date( thisWeekStart );
		thisWeekEnd.setDate( thisWeekStart.getDate() + 6 );
		thisWeekEnd.setHours( 23, 59, 59, 999 );
		// Reports only hold past data, so the unfinished current week must not
		// point at a future day. Lists of upcoming items keep the full week.
		if ( disableFutureDates && thisWeekEnd > now ) {
			thisWeekEnd.setTime( now.getTime() );
		}

		// Last Week
		const lastWeekStart = new Date( thisWeekStart );
		lastWeekStart.setDate( lastWeekStart.getDate() - 7 );
		const lastWeekEnd = new Date( lastWeekStart );
		lastWeekEnd.setDate( lastWeekStart.getDate() + 6 );
		lastWeekEnd.setHours( 23, 59, 59, 999 );

		// This Month
		const thisMonthStart = new Date( now.getFullYear(), now.getMonth(), 1 );
		const thisMonthEnd = new Date( now );
		thisMonthEnd.setHours( 23, 59, 59, 999 );

		// Last Month
		const lastMonthStart = new Date(
			now.getFullYear(),
			now.getMonth() - 1,
			1
		);
		const lastMonthEnd = new Date( now.getFullYear(), now.getMonth(), 0 );
		lastMonthEnd.setHours( 23, 59, 59, 999 );

		return [
			{
				label: 'Today',
				range: {
					from: today,
					to: today,
				},
			},
			{
				label: 'Yesterday',
				range: {
					from: yesterday,
					to: yesterday,
				},
			},
			{
				label: 'This Week',
				range: {
					from: thisWeekStart,
					to: thisWeekEnd,
				},
			},
			{
				label: 'Last Week',
				range: {
					from: lastWeekStart,
					to: lastWeekEnd,
				},
			},
			{
				label: 'This Month',
				range: {
					from: thisMonthStart,
					to: thisMonthEnd,
				},
			},
			{
				label: 'Last Month',
				range: {
					from: lastMonthStart,
					to: lastMonthEnd,
				},
			},
		];
	};

	// Add a function to get formatted date range text
	const getDateRangeText = () => {
		if ( ! displayRange?.from || ! displayRange?.to ) {
			return 'mm/dd/yyyy - mm/dd/yyyy';
		}
		return formatDateRange( displayRange );
	};

	// Name the control by its purpose, then its current value.
	const getDateRangeLabel = () => {
		if ( ! displayRange?.from || ! displayRange?.to ) {
			return __( 'Select date range', 'woo-cart-abandonment-recovery' );
		}

		return sprintf(
			/* translators: %s: the selected date range, e.g. "09/23/2026 - 09/29/2026". */
			__( 'Date range: %s', 'woo-cart-abandonment-recovery' ),
			getDateRangeText()
		);
	};

	const handleApply = ( range ) => {
		// Guard against a future end date sneaking in from any source.
		const today = new Date();
		const safeRange =
			disableFutureDates && range?.to && range.to > today
				? { ...range, to: today }
				: range;

		setSelectedRange( safeRange );
		setIsOpen( false );
	};

	const handleCancel = () => {
		setIsOpen( false );
	};

	return (
		<div className="flex items-center gap-2">
			<Button
				className={ cn(
					'whitespace-nowrap font-medium text-gray-500 [@media(pointer:coarse)]:min-h-11',
					className
				) }
				aria-label={ getDateRangeLabel() }
				ref={ refs.setReference }
				icon={
					<CalendarIcon
						className="h-6 w-6 text-gray-500"
						aria-hidden="true"
					/>
				}
				iconPosition="right"
				size="sm"
				tag="button"
				type="button"
				variant="outline"
				disabled={ disabled }
				{ ...getReferenceProps() }
			>
				{ getDateRangeText() }
			</Button>
			{ isOpen && (
				<FloatingPortal
					root={ document.getElementById( 'wcar-admin-app' ) }
				>
					<div
						ref={ refs.setFloating }
						style={ floatingStyles }
						className="z-999999 rounded-lg shadow-lg overflow-x-auto"
						{ ...getFloatingProps() }
					>
						<DatePicker
							key="range"
							applyButtonText="Apply"
							cancelButtonText="Cancel"
							onApply={ handleApply }
							onCancel={ handleCancel }
							presets={ isNarrow ? undefined : getDateRanges() }
							selected={ displayRange }
							// Open on the month the range starts in, so the selection is in view.
							defaultMonth={ displayRange?.from }
							selectionType="range"
							disabled={
								disableFutureDates
									? { after: new Date() }
									: undefined
							}
							showOutsideDays
							variant={ isNarrow ? 'normal' : 'presets' }
						/>
					</div>
				</FloatingPortal>
			) }
		</div>
	);
};

export default DateRange;

