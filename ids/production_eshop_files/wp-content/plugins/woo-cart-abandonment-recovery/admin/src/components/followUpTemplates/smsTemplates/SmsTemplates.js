import { useState } from 'react';
import { Table } from '@bsf/force-ui';
import { __, sprintf } from '@wordpress/i18n';
import { DevicePhoneMobileIcon } from '@heroicons/react/24/outline';

import ConfirmDialog from '@Components/common/ConfirmDialog';
import SmsTemplatesDrawer from './SmsTemplatesDrawer';
import SmsPreview from './SmsPreview';
import TemplateNameButton from '../shared/TemplateNameButton';
import TemplateRowActions from '../shared/TemplateRowActions';
import TemplateStatusSwitch from '../shared/TemplateStatusSwitch';
import TemplatesTableSkeleton from '../shared/TemplatesTableSkeleton';
import TemplatesToolbar from '../shared/TemplatesToolbar';
import {
	TemplatesEmptyState,
	TemplatesLoadError,
	TemplatesNoMatchRow,
} from '../shared/TemplatesStates';
import useTemplatesList from '../shared/useTemplatesList';
import {
	formatDuration,
	getRowClass,
	TEMPLATES_TABLE_CLASS,
} from '../shared/utils';
import { useProAccess } from '@Components/pro/useProAccess';

// Columns: checkbox, name, trigger, 4 metrics, status, actions.
const COLUMN_COUNT = 9;

const LIST_CONFIG = {
	fetchPath: '/wcar-pro/api/admin/sms-template',
	fetchMethod: 'GET',
	actions: {
		delete: {
			action: 'wcar_pro_delete_sms_template',
			nonce: 'delete_sms_template_nonce',
		},
		status: {
			action: 'wcar_pro_update_sms_template_status',
			nonce: 'update_sms_template_status_nonce',
		},
		clone: {
			action: 'wcar_pro_clone_sms_template',
			nonce: 'clone_sms_template_nonce',
		},
		restore: {
			action: 'wcar_pro_restore_sms_templates',
			nonce: 'restore_sms_templates_nonce',
		},
	},
};

const formatRate = ( rate ) => ( rate ? `${ rate }%` : '-' );

const MetricHeadCell = ( { label } ) => (
	<Table.HeadCell>
		<div className="flex items-center justify-center gap-1.5">
			{ label }
		</div>
	</Table.HeadCell>
);

const SmsTemplates = () => {
	const [ open, setOpen ] = useState( false );
	const [ template, setTemplate ] = useState( null );
	const { shouldBlockProFeatures } = useProAccess();
	const isFeatureBlocked = shouldBlockProFeatures();

	const list = useTemplatesList( {
		...LIST_CONFIG,
		skipFetch: isFeatureBlocked,
	} );
	const { selected, deleteModal } = list;

	const handleEdit = ( record ) => {
		setTemplate( record );
		setOpen( true );
	};

	const handleCreateNew = () => {
		setTemplate( null );
		setOpen( true );
	};

	const handleDrawerSave = ( saved ) => {
		if ( list.upsertTemplate( saved ) ) {
			setOpen( false );
			setTemplate( null );
		}
	};

	if ( isFeatureBlocked ) {
		return (
			// Show dummy data with modal overlay when pro is not active or feature is blocked
			<SmsPreview />
		);
	}

	let deleteTitle = __( 'Delete Template', 'woo-cart-abandonment-recovery' );
	let deleteDescription = __(
		'Are you sure you want to delete this template? This action cannot be undone.',
		'woo-cart-abandonment-recovery'
	);
	if ( deleteModal.type === 'single' && deleteModal.name ) {
		deleteDescription = sprintf(
			/* translators: %s: template name */
			__(
				'Are you sure you want to delete “%s”? This action cannot be undone.',
				'woo-cart-abandonment-recovery'
			),
			deleteModal.name
		);
	}
	if ( deleteModal.type === 'bulk' ) {
		deleteTitle = __(
			'Delete Selected Templates',
			'woo-cart-abandonment-recovery'
		);
		deleteDescription = sprintf(
			/* translators: %d: number of selected templates */
			__(
				'Are you sure you want to delete %d selected template(s)? This action cannot be undone.',
				'woo-cart-abandonment-recovery'
			),
			selected.length
		);
	}

	return (
		<>
			<TemplatesToolbar
				currentTab="sms"
				isLoading={ list.isLoading }
				selectedCount={ selected.length }
				onClearSelection={ list.clearSelection }
				onBulkDelete={ list.requestBulkDelete }
				searchText={ list.searchText }
				onSearch={ list.handleSearch }
				onRestore={ list.requestRestore }
				onCreate={ handleCreateNew }
			/>
			{ list.isLoading && (
				<TemplatesTableSkeleton
					metricLabels={ [
						__( 'Sent', 'woo-cart-abandonment-recovery' ),
						__( 'Click Rate', 'woo-cart-abandonment-recovery' ),
						__( 'Conversion Rate', 'woo-cart-abandonment-recovery' ),
						__( 'Unsubscribed', 'woo-cart-abandonment-recovery' ),
					] }
				/>
			) }
			{ ! list.isLoading && list.loadError && (
				<TemplatesLoadError
					description={ __(
						'Something went wrong while loading your SMS templates. Check your connection and try again.',
						'woo-cart-abandonment-recovery'
					) }
					onRetry={ list.retry }
				/>
			) }
			{ ! list.isLoading &&
				! list.loadError &&
				list.templates.length === 0 && (
				<TemplatesEmptyState
					icon={
						<DevicePhoneMobileIcon
							className="h-12 w-12 text-gray-400"
							aria-hidden="true"
						/>
					}
					title={ __(
						'No SMS templates yet',
						'woo-cart-abandonment-recovery'
					) }
					description={ __(
						'Create a template to text shoppers who leave items in their cart, or restore the defaults.',
						'woo-cart-abandonment-recovery'
					) }
				/>
			) }
			{ ! list.isLoading &&
				! list.loadError &&
				list.templates.length > 0 && (
				<Table
					checkboxSelection={ true }
					className={ TEMPLATES_TABLE_CLASS }
				>
					<Table.Head
						selected={ selected.length > 0 }
						onChangeSelection={ list.toggleSelectAll }
						indeterminate={
							selected.length > 0 &&
								selected.length < list.filteredData.length
						}
					>
						<Table.HeadCell>
							{ __(
								'Template Name',
								'woo-cart-abandonment-recovery'
							) }
						</Table.HeadCell>
						<Table.HeadCell>
							{ __(
								'Trigger After',
								'woo-cart-abandonment-recovery'
							) }
						</Table.HeadCell>
						<MetricHeadCell
							label={ __(
								'Sent',
								'woo-cart-abandonment-recovery'
							) }
						/>
						<MetricHeadCell
							label={ __(
								'Click Rate',
								'woo-cart-abandonment-recovery'
							) }
						/>
						<MetricHeadCell
							label={ __(
								'Conversion Rate',
								'woo-cart-abandonment-recovery'
							) }
						/>
						<MetricHeadCell
							label={ __(
								'Unsubscribed',
								'woo-cart-abandonment-recovery'
							) }
						/>
						<Table.HeadCell>
							{ __( 'Status', 'woo-cart-abandonment-recovery' ) }
						</Table.HeadCell>
						<Table.HeadCell className="text-right">
							{ __( 'Actions', 'woo-cart-abandonment-recovery' ) }
						</Table.HeadCell>
					</Table.Head>
					<Table.Body>
						{ list.filteredData.length > 0 ? (
							list.filteredData.map( ( item ) => (
								<Table.Row
									key={ item.id }
									data-template-id={ item.id }
									className={ getRowClass( {
										isHighlighted: list.isHighlighted( item.id ),
										isSelected: selected.includes( item.id ),
									} ) }
									value={ item }
									selected={ selected.includes( item.id ) }
									onChangeSelection={
										list.handleCheckboxChange
									}
								>
									<Table.Cell>
										<TemplateNameButton
											name={ item.template_name }
											onClick={ () =>
												handleEdit( item )
											}
										/>
									</Table.Cell>
									<Table.Cell>
										{ formatDuration(
											item.sms_frequency,
											item.sms_frequency_unit
										) }
									</Table.Cell>
									<Table.Cell
										className="text-center"
									>
										{ item?.sent || '-' }
									</Table.Cell>
									<Table.Cell
										className="text-center"
									>
										{ formatRate( item?.click_rate ) }
									</Table.Cell>
									<Table.Cell
										className="text-center"
									>
										{ formatRate( item?.conversion_rate ) }
									</Table.Cell>
									<Table.Cell
										className="text-center"
									>
										{ formatRate( item?.unsubscribe_rate ) }
									</Table.Cell>
									<Table.Cell>
										<TemplateStatusSwitch
											item={ item }
											name="wcf_activate_sms_template"
											onToggle={ list.toggleStatus }
										/>
									</Table.Cell>
									<Table.Cell>
										<TemplateRowActions
											onEdit={ () =>
												handleEdit( item )
											}
											onDuplicate={ () =>
												list.duplicate( item )
											}
											isDuplicating={
												list.duplicatingId !== null
											}
											onDelete={ () =>
												list.requestDelete( item )
											}
										/>
									</Table.Cell>
								</Table.Row>
							) )
						) : (
							<TemplatesNoMatchRow colSpan={ COLUMN_COUNT } />
						) }
					</Table.Body>
				</Table>
			) }

			<SmsTemplatesDrawer
				open={ open }
				setOpen={ setOpen }
				template={ template }
				onSave={ handleDrawerSave }
			/>
			<ConfirmDialog
				open={ deleteModal.isOpen }
				setOpen={ list.closeDeleteModal }
				onConfirm={ list.confirmDelete }
				title={ deleteTitle }
				description={ deleteDescription }
				isConfirming={ list.isDeleting }
				isDestructive
				confirmLabel={ __( 'Delete', 'woo-cart-abandonment-recovery' ) }
			/>
			<ConfirmDialog
				open={ list.isRestoreOpen }
				setOpen={ list.closeRestore }
				onConfirm={ list.confirmRestore }
				title={ __(
					'Restore Default Templates',
					'woo-cart-abandonment-recovery'
				) }
				description={ __(
					'The default SMS templates go back to their original content. Any edits you made to them are lost.',
					'woo-cart-abandonment-recovery'
				) }
				isConfirming={ list.isRestoring }
				isDestructive
				confirmLabel={ __( 'Restore', 'woo-cart-abandonment-recovery' ) }
			/>
		</>
	);
};

export default SmsTemplates;
