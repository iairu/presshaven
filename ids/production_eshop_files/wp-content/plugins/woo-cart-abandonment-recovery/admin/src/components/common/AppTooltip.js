import { Tooltip } from '@bsf/force-ui';
import PropTypes from 'prop-types';

const AppTooltip = ( {
	content,
	position = 'top',
	children,
	className = '',
	triggers,
} ) => {
	return (
		<Tooltip
			arrow
			content={ content }
			placement={ position }
			variant="dark"
			className={ className }
			tooltipPortalId="wcar-admin-app"
			triggers={ triggers }
		>
			{ children }
		</Tooltip>
	);
};

AppTooltip.propTypes = {
	content: PropTypes.node.isRequired,
	position: PropTypes.oneOf( [ 'top', 'bottom', 'left', 'right' ] ),
	children: PropTypes.node.isRequired,
	className: PropTypes.string,
	// Events that open the tooltip. Pass `[ 'hover', 'focus' ]` for text that is not a button.
	triggers: PropTypes.arrayOf( PropTypes.oneOf( [ 'click', 'hover', 'focus' ] ) ),
};

export default AppTooltip;
