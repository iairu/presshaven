import { _n, sprintf } from '@wordpress/i18n';

/**
 * Shorten long text with an ellipsis.
 *
 * @param {string} text      Text to shorten.
 * @param {number} maxLength Maximum length before truncating.
 * @return {string} Shortened text.
 */
export const truncateText = ( text = '', maxLength = 60 ) =>
	text.length > maxLength ? text.slice( 0, maxLength ) + '...' : text;

/**
 * Format a follow-up delay such as "1 Hour" or "3 Days".
 *
 * @param {number|string} value Number of units.
 * @param {string}        unit  One of MINUTE, HOUR or DAY.
 * @return {string} Translated, pluralized label.
 */
export const formatDuration = ( value, unit ) => {
	const count = parseInt( value, 10 );

	switch ( unit ) {
		case 'MINUTE':
			return sprintf(
				/* translators: %d: number of minutes */
				_n(
					'%d Minute',
					'%d Minutes',
					count,
					'woo-cart-abandonment-recovery'
				),
				count
			);
		case 'HOUR':
			return sprintf(
				/* translators: %d: number of hours */
				_n(
					'%d Hour',
					'%d Hours',
					count,
					'woo-cart-abandonment-recovery'
				),
				count
			);
		case 'DAY':
			return sprintf(
				/* translators: %d: number of days */
				_n(
					'%d Day',
					'%d Days',
					count,
					'woo-cart-abandonment-recovery'
				),
				count
			);
		default:
			return String( value );
	}
};

// The template lists share the Reports table's checkbox column and selected-row styling.
export {
	getRowClass,
	SELECTABLE_TABLE_CLASS as TEMPLATES_TABLE_CLASS,
} from '@Components/common/tableStyles';
