import { Button } from '@bsf/force-ui';
import { __ } from '@wordpress/i18n';
import {
	TrashIcon,
	PencilIcon,
	DocumentDuplicateIcon,
} from '@heroicons/react/24/outline';

import AppTooltip from '@Components/common/AppTooltip';

const TOUCH_TARGET =
	'[@media(pointer:coarse)]:min-h-11 [@media(pointer:coarse)]:min-w-11';

const RowAction = ( { label, icon, hoverClass, ...props } ) => (
	<AppTooltip content={ label }>
		<Button
			variant="ghost"
			size="xs"
			icon={ icon }
			className={ `text-gray-500 ${ hoverClass } ${ TOUCH_TARGET }` }
			aria-label={ label }
			{ ...props }
		/>
	</AppTooltip>
);

const TemplateRowActions = ( {
	onEdit,
	onDuplicate,
	onDelete,
	isDuplicating = false,
} ) => (
	<div className="flex items-center justify-end gap-2">
		<RowAction
			label={ __( 'Edit', 'woo-cart-abandonment-recovery' ) }
			icon={ <PencilIcon className="h-6 w-6" aria-hidden="true" /> }
			hoverClass="hover:text-flamingo-400"
			onClick={ onEdit }
		/>
		<RowAction
			label={ __( 'Duplicate', 'woo-cart-abandonment-recovery' ) }
			icon={
				<DocumentDuplicateIcon
					className="h-6 w-6"
					aria-hidden="true"
				/>
			}
			hoverClass="hover:text-flamingo-400"
			disabled={ isDuplicating }
			onClick={ onDuplicate }
		/>
		<RowAction
			label={ __( 'Delete', 'woo-cart-abandonment-recovery' ) }
			icon={ <TrashIcon className="h-6 w-6" aria-hidden="true" /> }
			hoverClass="hover:text-red-600"
			onClick={ onDelete }
		/>
	</div>
);

export default TemplateRowActions;
