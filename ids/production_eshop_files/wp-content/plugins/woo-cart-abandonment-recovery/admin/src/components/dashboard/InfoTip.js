import PropTypes from 'prop-types';

import AppTooltip from '@Components/common/AppTooltip';

/**
 * Icon that explains itself on hover and on keyboard focus.
 *
 * The trigger is a real button so keyboard users can reach it, and the same
 * text is its accessible name so screen readers announce it without the tooltip.
 * On touch devices an invisible pseudo-element grows the hit area to 44px.
 *
 * @param {Object} props          - Component props.
 * @param {string} props.content  - Explanation shown in the tooltip and announced by screen readers.
 * @param {Node}   props.children - The icon.
 * @return {JSX.Element} Focusable tooltip trigger.
 */
const InfoTip = ( { content, children } ) => (
	<AppTooltip content={ content } position="top">
		<button
			type="button"
			aria-label={ content }
			className="relative inline-flex items-center justify-center p-0 m-0 bg-transparent border-0 rounded cursor-help focus:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 [@media(pointer:coarse)]:before:content-[''] [@media(pointer:coarse)]:before:absolute [@media(pointer:coarse)]:before:-inset-[15px]"
		>
			{ children }
		</button>
	</AppTooltip>
);

InfoTip.propTypes = {
	content: PropTypes.string.isRequired,
	children: PropTypes.node.isRequired,
};

export default InfoTip;
