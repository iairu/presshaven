import { Button } from '@bsf/force-ui';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { __ } from '@wordpress/i18n';

/**
 * The "clear the filters" button, styled like the one on the dashboard Overview.
 *
 * @param {Object}   props
 * @param {Function} props.onClick Clears the filters.
 * @return {JSX.Element} The button.
 */
const ClearFiltersButton = ( { onClick } ) => (
	<Button
		variant="ghost"
		size="sm"
		destructive
		className="whitespace-nowrap [@media(pointer:coarse)]:min-h-11"
		icon={ <XMarkIcon /> }
		onClick={ onClick }
	>
		{ __( 'Clear Filters', 'woo-cart-abandonment-recovery' ) }
	</Button>
);

export default ClearFiltersButton;
