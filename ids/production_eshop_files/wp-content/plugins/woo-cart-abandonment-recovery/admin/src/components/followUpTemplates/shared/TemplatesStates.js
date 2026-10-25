import { Button } from '@bsf/force-ui';
import { __ } from '@wordpress/i18n';
import {
	ArrowPathIcon,
	ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';

import { EmptyBlock } from '@Components/common/empty-blocks';

const TOUCH_TARGET = '[@media(pointer:coarse)]:min-h-11';

/**
 * First-use state: no templates exist yet. The toolbar above already carries Create and
 * Restore, so the copy points at them instead of repeating the buttons.
 *
 * @param {Object} props
 * @param {Node}   props.icon        Neutral channel icon.
 * @param {string} props.title
 * @param {string} props.description
 */
export const TemplatesEmptyState = ( { icon, title, description } ) => (
	<EmptyBlock
		className="my-2"
		icon={ icon }
		title={ title }
		description={ description }
	/>
);

/**
 * Failure state: the list request failed. Distinct from an empty account.
 *
 * @param {Object}   props
 * @param {string}   props.description
 * @param {Function} props.onRetry
 */
export const TemplatesLoadError = ( { description, onRetry } ) => (
	<div role="alert">
		<EmptyBlock
			className="my-2"
			icon={
				<ExclamationTriangleIcon
					className="h-12 w-12 text-support-error"
					aria-hidden="true"
				/>
			}
			title={ __(
				"Couldn't load templates",
				'woo-cart-abandonment-recovery'
			) }
			description={ description }
			action={
				<Button
					size="sm"
					variant="outline"
					className={ TOUCH_TARGET }
					icon={ <ArrowPathIcon aria-hidden="true" /> }
					iconPosition="left"
					onClick={ onRetry }
				>
					{ __( 'Try again', 'woo-cart-abandonment-recovery' ) }
				</Button>
			}
		/>
	</div>
);

export const TemplatesNoMatchRow = ( { colSpan } ) => (
	<tr>
		<td colSpan={ colSpan } className="p-4 w-full text-center">
			{ __(
				'No matching data available',
				'woo-cart-abandonment-recovery'
			) }
		</td>
	</tr>
);
