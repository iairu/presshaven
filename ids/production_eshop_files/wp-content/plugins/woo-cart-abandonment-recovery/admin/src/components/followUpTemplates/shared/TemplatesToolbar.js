import { Button, Input } from '@bsf/force-ui';
import { __, sprintf } from '@wordpress/i18n';
import {
	TrashIcon,
	MagnifyingGlassIcon,
	PlusIcon,
	XMarkIcon,
} from '@heroicons/react/24/outline';

import TemplatesNav from '../TemplatesNav';

const TemplatesToolbar = ( {
	currentTab,
	isLoading,
	selectedCount,
	onClearSelection,
	onBulkDelete,
	searchText,
	onSearch,
	onRestore,
	onCreate,
	isCreateDisabled = false,
} ) => (
	<div className="flex flex-col md:flex-row md:flex-wrap gap-4 justify-between relative">
		<div className="flex flex-row flex-wrap gap-4 items-center">
			<TemplatesNav currentTab={ currentTab } />
			{ ! isLoading && selectedCount > 0 && (
				<div className="flex gap-4 items-center border-0 border-solid border-gray-200 md:border-l md:pl-4">
					<Button
						variant="ghost"
						icon={
							<XMarkIcon
								className="h-6 w-6 text-gray-500"
								aria-hidden="true"
							/>
						}
						size="xs"
						className="text-icon-secondary hover:text-icon-primary [@media(pointer:coarse)]:min-h-11 [@media(pointer:coarse)]:min-w-11"
						aria-label={ __(
							'Clear selection',
							'woo-cart-abandonment-recovery'
						) }
						onClick={ onClearSelection }
					/>
					<span
						className="text-sm font-normal text-gray-500"
						role="status"
					>
						{ sprintf(
							/* translators: %d: number of selected templates */
							__( '%d Selected', 'woo-cart-abandonment-recovery' ),
							selectedCount
						) }
					</span>
					<Button
						className="[@media(pointer:coarse)]:min-h-11"
						size="sm"
						tag="button"
						type="button"
						variant="outline"
						destructive
						icon={
							<TrashIcon className="h-4 w-4" aria-hidden="true" />
						}
						iconPosition="left"
						onClick={ onBulkDelete }
					>
						{ __( 'Delete', 'woo-cart-abandonment-recovery' ) }
					</Button>
				</div>
			) }
		</div>
		<div className="flex flex-col md:flex-row md:flex-1 md:items-center md:justify-end md:min-w-[34rem] gap-4">
			<div className="w-full md:flex-1 xl:flex-none xl:w-52">
				<Input
					placeholder={ __( 'Search…', 'woo-cart-abandonment-recovery' ) }
					prefix={
						<MagnifyingGlassIcon
							className="h-6 w-6 text-gray-500"
							aria-hidden="true"
						/>
					}
					size="sm"
					type="search"
					aria-label={ __( 'Search', 'woo-cart-abandonment-recovery' ) }
					value={ searchText }
					onChange={ onSearch }
					className="w-full [&_input]:min-h-0"
					disabled={ isLoading }
				/>
			</div>
			{ onRestore && (
				<Button
					iconPosition="left"
					size="sm"
					tag="button"
					type="button"
					variant="outline"
					className="whitespace-nowrap [@media(pointer:coarse)]:min-h-11"
					disabled={ isLoading }
					onClick={ onRestore }
				>
					{ __(
						'Restore Default Templates',
						'woo-cart-abandonment-recovery'
					) }
				</Button>
			) }
			<Button
				className="whitespace-nowrap [@media(pointer:coarse)]:min-h-11"
				icon={ <PlusIcon aria-hidden="true" /> }
				iconPosition="left"
				size="sm"
				tag="button"
				type="button"
				variant="primary"
				disabled={ isLoading || isCreateDisabled }
				onClick={ onCreate }
			>
				{ __( 'Create New Template', 'woo-cart-abandonment-recovery' ) }
			</Button>
		</div>
	</div>
);

export default TemplatesToolbar;
