import { useState } from 'react';
import { Table } from '@bsf/force-ui';
import { __, sprintf } from '@wordpress/i18n';
import { EnvelopeIcon } from '@heroicons/react/24/outline';

import EmailTemplatesDrawer from '@Components/followUpTemplates/emailTemplates/EmailTemplatesDrawer';
import ConfirmDialog from '@Components/common/ConfirmDialog';
import FeatureBadge from '@Components/common/FeatureBadge';
import { useProAccess } from '@Components/pro/useProAccess';
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

// Columns: checkbox, name, trigger, 5 metrics, status, actions.
const COLUMN_COUNT = 10;

// Introduced a variable if in future or any user wants the subject column.
const shouldHideTableColumn = true;

const LIST_CONFIG = {
	fetchPath: '/wcar/api/admin/followup-emails',
	fetchMethod: 'POST',
	actions: {
		delete: {
			action: 'wcar_delete_email_template',
			nonce: 'delete_email_template_nonce',
		},
		status: {
			action: 'wcar_update_email_template_status',
			nonce: 'update_email_template_status_nonce',
		},
		clone: {
			action: 'wcar_clone_email_template',
			nonce: 'clone_email_template_nonce',
		},
		restore: {
			action: 'wcar_restore_email_templates',
			nonce: 'restore_email_templates_nonce',
		},
	},
};

/**
 * Placeholder figures shown blurred behind the Pro badge. Derived from the template id so
 * they stay put between renders instead of changing on every page load.
 *
 * @param {number|string} id Template id.
 * @return {Object} Placeholder metrics.
 */
const getPlaceholderMetrics = ( id ) => {
	const seed = Number( id ) || 0;
	const pick = ( offset ) => ( ( ( seed * 31 ) + ( offset * 17 ) ) % 90 ) + 5;

	return {
		sent: pick( 1 ),
		open: `${ pick( 2 ) }%`,
		click: `${ pick( 3 ) }%`,
		conversion: `${ pick( 4 ) }%`,
		unsub: `${ pick( 5 ) }%`,
	};
};

const MetricHeadCell = ( { label, showBadge } ) => (
	<Table.HeadCell>
		<div className="flex items-center justify-center gap-1.5">
			{ label }
			{ showBadge && (
				<FeatureBadge
					feature={ __( 'PRO', 'woo-cart-abandonment-recovery' ) }
				/>
			) }
		</div>
	</Table.HeadCell>
);

// Blocked (no Pro) rows show decorative numbers. Hide them from assistive tech and say what's
// really there instead of reading out figures that aren't the merchant's.
const MetricCell = ( { isBlocked, placeholder, value } ) => (
	<Table.Cell className="text-center">
		{ isBlocked ? (
			<>
				<span aria-hidden="true" className="blur-sm select-none">
					{ placeholder }
				</span>
				<span className="sr-only">
					{ __( 'Available in Pro', 'woo-cart-abandonment-recovery' ) }
				</span>
			</>
		) : (
			value
		) }
	</Table.Cell>
);

const formatRate = ( rate ) => ( rate ? `${ rate }%` : '-' );

const EmailTemplates = () => {
	const [ open, setOpen ] = useState( false );
	const [ template, setTemplate ] = useState( null );
	const { shouldBlockProFeatures } = useProAccess();
	const isFeatureBlocked = shouldBlockProFeatures();

	const list = useTemplatesList( LIST_CONFIG );
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
				currentTab="email"
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
						__( 'Open Rate', 'woo-cart-abandonment-recovery' ),
						__( 'Click Rate', 'woo-cart-abandonment-recovery' ),
						__( 'Conversion Rate', 'woo-cart-abandonment-recovery' ),
						__( 'Unsubscribed', 'woo-cart-abandonment-recovery' ),
					] }
					showBadge={ isFeatureBlocked }
				/>
			) }
			{ ! list.isLoading && list.loadError && (
				<TemplatesLoadError
					description={ __(
						'Something went wrong while loading your email templates. Check your connection and try again.',
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
						<EnvelopeIcon
							className="h-12 w-12 text-gray-400"
							aria-hidden="true"
						/>
					}
					title={ __(
						'No email templates yet',
						'woo-cart-abandonment-recovery'
					) }
					description={ __(
						'Create a template to email shoppers who leave items in their cart, or restore the defaults.',
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
						<Table.HeadCell
							className={ shouldHideTableColumn ? 'hidden' : '' }
						>
							{ __(
								'Email Subject',
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
							showBadge={ isFeatureBlocked }
						/>
						<MetricHeadCell
							label={ __(
								'Open Rate',
								'woo-cart-abandonment-recovery'
							) }
							showBadge={ isFeatureBlocked }
						/>
						<MetricHeadCell
							label={ __(
								'Click Rate',
								'woo-cart-abandonment-recovery'
							) }
							showBadge={ isFeatureBlocked }
						/>
						<MetricHeadCell
							label={ __(
								'Conversion Rate',
								'woo-cart-abandonment-recovery'
							) }
							showBadge={ isFeatureBlocked }
						/>
						<MetricHeadCell
							label={ __(
								'Unsubscribed',
								'woo-cart-abandonment-recovery'
							) }
							showBadge={ isFeatureBlocked }
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
							list.filteredData.map( ( item ) => {
								const placeholder = isFeatureBlocked
									? getPlaceholderMetrics( item.id )
									: {};

								return (
									<Table.Row
										key={ item.id }
										data-template-id={ item.id }
										className={ getRowClass( {
											isHighlighted: list.isHighlighted( item.id ),
											isSelected: selected.includes( item.id ),
										} ) }
										value={ item }
										selected={ selected.includes(
											item.id
										) }
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
										<Table.Cell
											className={
												shouldHideTableColumn
													? 'hidden'
													: ''
											}
										>
											{ item.email_subject }
										</Table.Cell>
										<Table.Cell>
											{ formatDuration(
												item.email_frequency,
												item.email_frequency_unit
											) }
										</Table.Cell>
										<MetricCell
											isBlocked={ isFeatureBlocked }
											placeholder={ placeholder.sent }
											value={ item?.sent || '-' }
										/>
										<MetricCell
											isBlocked={ isFeatureBlocked }
											placeholder={ placeholder.open }
											value={ formatRate(
												item?.open_rate
											) }
										/>
										<MetricCell
											isBlocked={ isFeatureBlocked }
											placeholder={ placeholder.click }
											value={ formatRate(
												item?.click_rate
											) }
										/>
										<MetricCell
											isBlocked={ isFeatureBlocked }
											placeholder={
												placeholder.conversion
											}
											value={ formatRate(
												item?.conversion_rate
											) }
										/>
										<MetricCell
											isBlocked={ isFeatureBlocked }
											placeholder={ placeholder.unsub }
											value={ formatRate(
												item?.unsubscribe_rate
											) }
										/>
										<Table.Cell>
											<TemplateStatusSwitch
												item={ item }
												name="wcf_activate_email_template"
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
													list.duplicatingId !==
														null
												}
												onDelete={ () =>
													list.requestDelete( item )
												}
											/>
										</Table.Cell>
									</Table.Row>
								);
							} )
						) : (
							<TemplatesNoMatchRow colSpan={ COLUMN_COUNT } />
						) }
					</Table.Body>
				</Table>
			) }

			<EmailTemplatesDrawer
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
					'The default email templates go back to their original content. Any edits you made to them are lost.',
					'woo-cart-abandonment-recovery'
				) }
				isConfirming={ list.isRestoring }
				isDestructive
				confirmLabel={ __( 'Restore', 'woo-cart-abandonment-recovery' ) }
			/>
		</>
	);
};

export default EmailTemplates;
