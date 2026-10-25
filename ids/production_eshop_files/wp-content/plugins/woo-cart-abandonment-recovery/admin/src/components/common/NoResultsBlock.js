import { MagnifyingGlassIcon } from '@heroicons/react/24/outline';

import { EmptyBlock } from '@Components/common/empty-blocks';

/**
 * Shown in place of a list when the search, filters or dates match nothing.
 *
 * @param {Object}  props
 * @param {string}  props.title       What was not found.
 * @param {string}  props.description Why, and what to change.
 * @param {Element} [props.action]    A control that undoes the filtering.
 * @return {JSX.Element} The message.
 */
const NoResultsBlock = ( { title, description, action } ) => (
	<EmptyBlock
		className="my-2"
		icon={ <MagnifyingGlassIcon className="h-12 w-12 text-gray-400" /> }
		title={ title }
		description={ description }
		action={ action }
	/>
);

export default NoResultsBlock;
