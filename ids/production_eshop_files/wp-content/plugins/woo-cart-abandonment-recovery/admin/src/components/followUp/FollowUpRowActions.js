import {
	EyeIcon,
	UserMinusIcon,
	TrashIcon,
	BookmarkSlashIcon,
	NoSymbolIcon,
	ShieldCheckIcon,
} from '@heroicons/react/24/outline';
import { __ } from '@wordpress/i18n';

import TableRowAction from '@Components/common/TableRowAction';

/**
 * The Actions cell of a Follow Up Reports row.
 *
 * @param {Object}   props
 * @param {Object}   props.item          The report.
 * @param {boolean}  props.canBlacklist  Whether blacklisting is available (a Pro feature).
 * @param {Function} props.onView        Opens the report.
 * @param {Function} props.onUnsubscribe Unsubscribes the customer.
 * @param {Function} props.onBlacklist   Gets `'blacklist'` or `'whitelist'`.
 * @param {Function} props.onDelete      Asks to delete the report.
 * @return {JSX.Element} The buttons.
 */
const FollowUpRowActions = ( {
	item,
	canBlacklist,
	onView,
	onUnsubscribe,
	onBlacklist,
	onDelete,
} ) => {
	const isBlacklisted = 'Blacklisted' === item?.orderStatus;
	const isUnsubscribed = 0 !== item.unsubscribed;

	return (
		<div className="flex items-center justify-end gap-2">
			<TableRowAction
				label={ __( 'View', 'woo-cart-abandonment-recovery' ) }
				icon={ <EyeIcon className="h-6 w-6" /> }
				onClick={ onView }
				className="text-gray-500 hover:text-flamingo-400"
			/>
			{ isUnsubscribed ? (
				<TableRowAction
					label={ __( 'Unsubscribed', 'woo-cart-abandonment-recovery' ) }
					icon={ <BookmarkSlashIcon className="h-6 w-6" /> }
					className="text-gray-500 cursor-not-allowed opacity-50"
					disabled
				/>
			) : (
				<TableRowAction
					label={ __( 'Unsubscribe', 'woo-cart-abandonment-recovery' ) }
					icon={ <UserMinusIcon className="h-6 w-6" /> }
					onClick={ onUnsubscribe }
					className="text-gray-500 hover:text-flamingo-400"
				/>
			) }
			{ canBlacklist && (
				<TableRowAction
					label={
						isBlacklisted
							? __( 'Whitelist', 'woo-cart-abandonment-recovery' )
							: __( 'Blacklist', 'woo-cart-abandonment-recovery' )
					}
					icon={
						isBlacklisted ? (
							<ShieldCheckIcon className="h-6 w-6" />
						) : (
							<NoSymbolIcon className="h-6 w-6" />
						)
					}
					onClick={ () =>
						onBlacklist( isBlacklisted ? 'whitelist' : 'blacklist' )
					}
					className="text-gray-500 hover:text-flamingo-400"
				/>
			) }
			<TableRowAction
				label={ __( 'Delete', 'woo-cart-abandonment-recovery' ) }
				icon={ <TrashIcon className="h-6 w-6" /> }
				onClick={ onDelete }
				className="text-gray-500 hover:text-red-600"
			/>
		</div>
	);
};

export default FollowUpRowActions;
