import clsx from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Utility function for conditional TailwindCSS class names.
 *
 * @param {...(string|Array|Object)} classNames - Class names, arrays or condition objects.
 *
 * @return {string} return final class names string.
 */
export const cn = ( ...classNames ) => twMerge( clsx( classNames ) );

/**
 * A date as the local calendar day `YYYY-MM-DD`, which is what the server filters on.
 *
 * @param {?Date} date The date, if any.
 * @return {string} The day, or an empty string when there is no date.
 */
export const toDateParam = ( date ) => ( date ? formatLocalDate( date ) : '' );

/**
 * A date range as text, e.g. `09/29/2026 - 10/05/2026`.
 *
 * @param {{from: Date, to: Date}} range The range.
 * @return {string} The text.
 */
export const formatDateRange = ( range ) => {
	const format = ( date ) =>
		date.toLocaleDateString( 'en-US', {
			month: '2-digit',
			day: '2-digit',
			year: 'numeric',
		} );
	return `${ format( range.from ) } - ${ format( range.to ) }`;
};

/**
 * The range a report covers until the user picks one: the last 7 days, today included.
 *
 * @return {{from: Date, to: Date}} The range.
 */
export const getDefaultDateRange = () => {
	const to = new Date();
	const from = new Date();
	from.setDate( to.getDate() - 6 );
	return { from, to };
};

/**
 * Generate pagination pages array with ellipsis support
 *
 * @param {number} totalPages  - Total number of pages
 * @param {number} currentPage - Current active page
 * @return {Array} Array of page numbers and ellipsis markers
 */
export const generatePaginationPages = ( totalPages, currentPage ) => {
	const pages = [];

	if ( totalPages <= 7 ) {
		// If total pages is 7 or less, show all pages
		for ( let i = 1; i <= totalPages; i++ ) {
			pages.push( i );
		}
	} else {
		// Always show first 3 pages
		for ( let i = 1; i <= 3; i++ ) {
			pages.push( i );
		}

		// Add ellipsis if there are more pages
		if ( currentPage > 5 ) {
			pages.push( 'ellipsis' );
		}

		// Show current page and surrounding pages if not in first/last 3
		if ( currentPage > 3 && currentPage < totalPages - 2 ) {
			pages.push( currentPage );
		}

		// Add ellipsis before last 3 pages if needed
		if ( currentPage < totalPages - 4 ) {
			pages.push( 'ellipsis-end' );
		}

		// Always show last 3 pages
		for ( let i = totalPages - 2; i <= totalPages; i++ ) {
			if ( i > 3 ) {
				pages.push( i );
			}
		}
	}

	return pages;
};

/**
 * Parse a rules-engine value into a normalized array of groups.
 *
 * The stored value can come from REST as either an already-parsed array, a
 * JSON string, or a double-encoded JSON string (legacy). Returns [] on failure
 * or non-array input; callers can apply their own default-group fallback on top.
 *
 * @param {*} raw Stored rules value (string | array | other).
 * @return {Array} Parsed array of rule groups, or empty array on failure.
 */
export const parseRulesValue = ( raw ) => {
	let v = raw;
	if ( typeof v === 'string' ) {
		try {
			v = JSON.parse( v );
			if ( typeof v === 'string' ) {
				v = JSON.parse( v );
			}
		} catch ( e ) {
			return [];
		}
	}
	return Array.isArray( v ) ? v : [];
};

/**
 * Format a Date as a local `YYYY-MM-DD` string. (Avoids `toISOString()`, which
 * shifts to UTC and can make date filters off by one day.)
 *
 * @param {Date|string|number} value A Date, timestamp, or parseable date string.
 * @return {string} `YYYY-MM-DD`, or '' when the value isn't a valid date.
 */
export const formatLocalDate = ( value ) => {
	const date = value instanceof Date ? value : new Date( value );
	if ( isNaN( date.getTime() ) ) {
		return '';
	}
	const year = date.getFullYear();
	const month = String( date.getMonth() + 1 ).padStart( 2, '0' );
	const day = String( date.getDate() ).padStart( 2, '0' );
	return `${ year }-${ month }-${ day }`;
};
