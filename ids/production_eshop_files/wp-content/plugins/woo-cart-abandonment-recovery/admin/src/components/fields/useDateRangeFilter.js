import { useMemo, useState } from 'react';

import { getDefaultDateRange, toDateParam } from '@Utils/helper';

// One shared object, so clearing an already empty range does not look like a change.
const EMPTY_RANGE = { from: null, to: null };

// The picker lets a range be applied after one click, which leaves one end unset. Reports filter on
// whole days, so that click means that one day.
const completeRange = ( range ) => {
	if ( range?.from && range?.to ) {
		return range;
	}
	const day = range?.from || range?.to;
	return day ? { from: day, to: day } : EMPTY_RANGE;
};

/**
 * State for a report's date filter. `selectedRange` holds only a range the user applied, so it is
 * empty until then, and never has just one end. `defaultRange` is for a report that loads the last
 * 7 days meanwhile: pass it to `DateRange` as its placeholder, and send `activeRange` to the server.
 * A report with no default sends `selectedRange` instead, so it sends no dates until one is picked.
 *
 * @return {Object} The filter:
 *                  `defaultRange` the last 7 days as of today, which moves on when the day does;
 *                  `selectedRange` the range the user applied, empty by default;
 *                  `setSelectedRange` sets it; a range with one end set becomes that one day;
 *                  `clearRange` empties it;
 *                  `hasPickedRange` whether the user applied one;
 *                  `activeRange` the range to load: the applied one, else the default.
 */
export const useDateRangeFilter = () => {
	const today = toDateParam( new Date() );
	const defaultRange = useMemo( () => getDefaultDateRange(), [ today ] );
	const [ selectedRange, setRange ] = useState( EMPTY_RANGE );

	const setSelectedRange = ( range ) => setRange( completeRange( range ) );
	const hasPickedRange = !! selectedRange.from;
	const activeRange = hasPickedRange ? selectedRange : defaultRange;
	const clearRange = () => setRange( EMPTY_RANGE );

	return {
		defaultRange,
		selectedRange,
		setSelectedRange,
		clearRange,
		hasPickedRange,
		activeRange,
	};
};
