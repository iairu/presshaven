import { Button } from '@bsf/force-ui';
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline';
import { __ } from '@wordpress/i18n';

import { EmptyBlock } from '@Components/common/empty-blocks';

/**
 * Shown in place of a list whose request failed, with a way to ask again.
 *
 * @param {Object}   props
 * @param {string}   props.title   What could not be loaded.
 * @param {Function} props.onRetry Runs when the user presses Try Again.
 * @return {JSX.Element} The message.
 */
const LoadFailedBlock = ( { title, onRetry } ) => (
	<EmptyBlock
		className="my-2"
		icon={ <ExclamationTriangleIcon className="h-12 w-12 text-yellow-500" /> }
		title={ title }
		description={ __(
			'Check your connection and try again.',
			'woo-cart-abandonment-recovery'
		) }
		action={
			<Button size="sm" variant="primary" onClick={ onRetry }>
				{ __( 'Try Again', 'woo-cart-abandonment-recovery' ) }
			</Button>
		}
	/>
);

export default LoadFailedBlock;
