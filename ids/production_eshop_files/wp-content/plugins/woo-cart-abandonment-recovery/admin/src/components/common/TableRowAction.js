import { Button } from '@bsf/force-ui';

import AppTooltip from '@Components/common/AppTooltip';
import { COARSE_TARGET_CLASS } from '@Components/common/tableStyles';
import { cn } from '@Utils/helper';

/**
 * One icon button of a table row, with its tooltip. The label names the button for screen readers
 * too, and the button grows to the 44px touch size on touch screens.
 *
 * @param {Object}   props
 * @param {string}   props.label       Tooltip text and accessible name.
 * @param {Node}     props.icon        The icon.
 * @param {Function} [props.onClick]   Runs on press.
 * @param {string}   [props.className] Colors for the icon.
 * @param {boolean}  [props.disabled]
 * @return {JSX.Element} The button.
 */
const TableRowAction = ( { label, icon, onClick, className, disabled = false } ) => (
	<AppTooltip content={ label } position="top">
		<Button
			variant="ghost"
			icon={ icon }
			size="xs"
			className={ cn( COARSE_TARGET_CLASS, className ) }
			aria-label={ label }
			onClick={ onClick }
			disabled={ disabled }
		/>
	</AppTooltip>
);

export default TableRowAction;
