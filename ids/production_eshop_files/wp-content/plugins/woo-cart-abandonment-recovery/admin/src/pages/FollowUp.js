/* eslint-disable no-mixed-spaces-and-tabs, indent, @wordpress/i18n-no-variables, @wordpress/i18n-no-collapsible-whitespace, @wordpress/i18n-translator-comments */
import { useState, useEffect, useRef } from 'react';
import {
	Title,
	Table,
	Button,
	Select,
	Input,
	toast,
} from '@bsf/force-ui';
import {
	MagnifyingGlassIcon,
	XMarkIcon,
	ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';
import { __, _n, sprintf } from '@wordpress/i18n';
import { useNavigate } from 'react-router-dom';

import { cn, toDateParam } from '@Utils/helper';

import { doApiFetch, useStateValue, ActionTypes } from '@Store';

import SectionWrapper from '@Components/common/SectionWrapper';
import OrderStatusBadge from '@Components/common/OrderStatusBadge';
import DateRange from '@Components/fields/DateRange';
import { useDateRangeFilter } from '@Components/fields/useDateRangeFilter';
import LoadFailedBlock from '@Components/common/LoadFailedBlock';
import NoResultsBlock from '@Components/common/NoResultsBlock';
import FollowUpTableSkeleton from '@Components/followUp/FollowUpTableSkeleton';
import FollowUpRowActions from '@Components/followUp/FollowUpRowActions';
import ScrollableTable from '@Components/common/ScrollableTable';
import TablePagination from '@Components/common/TablePagination';
import ClearFiltersButton from '@Components/common/ClearFiltersButton';
import TableLinkButton from '@Components/common/TableLinkButton';
import {
	getRowClass,
	SELECTABLE_TABLE_CLASS,
} from '@Components/common/tableStyles';
import { EmptyBlock } from '@Components/common/empty-blocks';
import ExportToExcel from '@Components/common/ExportToExcel';
import ConfirmDialog from '@Components/common/ConfirmDialog';
import { useProAccess } from '@Components/pro/useProAccess';

// How long to wait after the last keystroke before searching.
const SEARCH_DEBOUNCE_MS = 300;

// What the export file holds, in order.
const EXPORT_COLUMNS = [
	{ key: 'id', label: __( 'Report ID', 'woo-cart-abandonment-recovery' ) },
	{ key: 'userName', label: __( 'User Name', 'woo-cart-abandonment-recovery' ) },
	{ key: 'email', label: __( 'Email To', 'woo-cart-abandonment-recovery' ) },
	{ key: 'cartTotal', label: __( 'Cart Total', 'woo-cart-abandonment-recovery' ) },
	{ key: 'orderStatus', label: __( 'Order Status', 'woo-cart-abandonment-recovery' ) },
	{ key: 'dateTime', label: __( 'Date & Time', 'woo-cart-abandonment-recovery' ) },
	{ key: 'country', label: __( 'Country', 'woo-cart-abandonment-recovery' ) },
	{
		key: 'unsubscribed',
		label: __( 'Unsubscribed', 'woo-cart-abandonment-recovery' ),
		format: ( value ) =>
			value
				? __( 'Yes', 'woo-cart-abandonment-recovery' )
				: __( 'No', 'woo-cart-abandonment-recovery' ),
	},
];

const getDateParams = ( range ) => ( {
	date_from: toDateParam( range.from ),
	date_to: toDateParam( range.to ),
} );

const FollowUp = () => {
	const [ selected, setSelected ] = useState( [] );
	// Currently-picked bulk action from the toolbar dropdown, fired on Apply click.
	const [ bulkAction, setBulkAction ] = useState( null );
	const [ currentPage, setCurrentPage ] = useState( 1 );
	const [ itemsPerPage, setItemsPerPage ] = useState( 20 );
	const [ searchText, setSearchText ] = useState( '' );
	const [ selectedOption, setSelectedOption ] = useState( {
		id: 'all',
		title: __( 'All', 'woo-cart-abandonment-recovery' ),
	} );
	// There is no default range: every report shows, and no dates are sent, until the user picks some.
	const { selectedRange, setSelectedRange, clearRange, hasPickedRange } =
		useDateRangeFilter();
	// The first load shows the skeleton; later loads (a page, filter or search change) keep the
	// rows on screen, dimmed, so the table does not flash.
	const [ isLoading, setIsLoading ] = useState( true );
	const [ isRefreshing, setIsRefreshing ] = useState( false );
	// The rows on the current page, how many reports match the filters, and whether any exist at all.
	const [ data, setData ] = useState( [] );
	const [ totalItems, setTotalItems ] = useState( 0 );
	const [ hasRecords, setHasRecords ] = useState( false );
	// The last request for the list failed, so what is on screen cannot be trusted.
	const [ loadFailed, setLoadFailed ] = useState( false );
	const [ reloadKey, setReloadKey ] = useState( 0 );
	const [ debouncedSearch, setDebouncedSearch ] = useState( '' );
	const latestRequest = useRef( 0 );
	const [ , dispatch ] = useStateValue();
	const navigate = useNavigate();
	const [ deleteModal, setDeleteModal ] = useState( {
		isOpen: false,
		type: null,
		id: null,
	} );
	const [ isDeleting, setIsDeleting ] = useState( false );
	const { shouldBlockProFeatures } = useProAccess();
	const isFeatureBlocked = shouldBlockProFeatures();
	const notAvailableString = __(
		'Not Available',
		'woo-cart-abandonment-recovery'
	);

	// Wait for a pause in typing before asking the server to search. A new term also goes back to
	// the first page, in the same update, so one request carries both and none carries a stale term.
	useEffect( () => {
		const timer = setTimeout( () => {
			const term = searchText.trim();
			if ( term !== debouncedSearch ) {
				setDebouncedSearch( term );
				setCurrentPage( 1 );
			}
		}, SEARCH_DEBOUNCE_MS );
		return () => clearTimeout( timer );
	}, [ searchText ] );

	// Selection belongs to the rows on screen, so it ends when they change.
	useEffect( () => {
		setSelected( [] );
	}, [ currentPage, itemsPerPage, debouncedSearch, selectedOption, selectedRange ] );

	// Ask the server for one page. Answers that arrive after a newer request are dropped.
	const fetchReports = ( params, { isPageLoad = false } = {} ) => {
		const requestId = isPageLoad
			? ++latestRequest.current
			: latestRequest.current;
		return new Promise( ( resolve ) => {
			doApiFetch(
				'/wcar/api/admin/follow-up/',
				{
					...params,
					search: debouncedSearch,
					status: selectedOption.id,
					...getDateParams( selectedRange ),
				},
				'POST',
				( response ) =>
					resolve(
						! isPageLoad || requestId === latestRequest.current
							? response
							: null
					),
				() => resolve( null )
			).catch( () => {} );
		} );
	};

	useEffect( () => {
		let cancelled = false;
		const load = async () => {
			setIsRefreshing( true );
			const response = await fetchReports(
				{ page: currentPage, per_page: itemsPerPage },
				{ isPageLoad: true }
			);
			if ( cancelled ) {
				return;
			}
			if ( ! response ) {
				setLoadFailed( true );
				setIsLoading( false );
				setIsRefreshing( false );
				return;
			}
			setLoadFailed( false );
			// The last row of the last page was deleted: step back to the new last page.
			if ( response.items.length === 0 && currentPage > 1 ) {
				setCurrentPage( Math.max( 1, Math.ceil( response.total_items / itemsPerPage ) ) );
				return;
			}
			setData( response.items || [] );
			setTotalItems( response.total_items || 0 );
			setHasRecords( !! response.has_records );
			setIsLoading( false );
			setIsRefreshing( false );
		};
		load();
		return () => {
			cancelled = true;
		};
	}, [ currentPage, itemsPerPage, debouncedSearch, selectedOption, selectedRange, reloadKey ] );

	// Every report that matches the filters, for the export. A failed request throws, so the export
	// says it failed instead of saying there is nothing to export.
	const fetchAllReports = async () => {
		const response = await fetchReports( { export: true } );
		if ( ! response ) {
			throw new Error( 'The reports could not be loaded for the export.' );
		}
		return response.items || [];
	};

	// Handler for date range changes
	const handleDateRangeChange = ( range ) => {
		setSelectedRange( range );
		setCurrentPage( 1 ); // Reset to first page when date range changes
	};

	const handleCheckboxChange = ( checked, value ) => {
		if ( checked ) {
			setSelected( [ ...selected, value.id ] );
		} else {
			setSelected( selected.filter( ( item ) => item !== value.id ) );
		}
	};

	const toggleSelectAll = ( checked ) => {
		if ( checked ) {
			setSelected( data.map( ( item ) => item.id ) );
		} else {
			setSelected( [] );
		}
	};

	const filterOptions = [
		{
			id: 'all',
			title: __( 'All', 'woo-cart-abandonment-recovery' ),
		},
		{
			id: 'abandoned_orders',
			title: __( 'Abandoned Orders', 'woo-cart-abandonment-recovery' ),
		},
		{
			id: 'recovered_orders',
			title: __( 'Recovered Orders', 'woo-cart-abandonment-recovery' ),
		},
		{
			id: 'lost_orders',
			title: __( 'Lost Orders', 'woo-cart-abandonment-recovery' ),
		},
		{
			id: 'blacklisted',
			title: __( 'Blacklisted', 'woo-cart-abandonment-recovery' ),
		},
	];

	// The server pages, searches and filters; `data` is already the current page.
	const totalPages = Math.ceil( totalItems / itemsPerPage );

	const filtersApplied =
		searchText !== '' ||
		selectedOption?.id !== 'all' ||
		hasPickedRange;

	const handleClearFilters = () => {
		setSelectedOption( {
			id: 'all',
			title: __( 'All', 'woo-cart-abandonment-recovery' ),
		} );
		setSearchText( '' );
		// Clear the term the request uses now, not after the debounce, so no request carries it.
		setDebouncedSearch( '' );
		clearRange();
		setCurrentPage( 1 );
	};

	const handlePageChange = ( page ) => {
		setCurrentPage( page );
	};

	const handleItemsPerPageChange = ( value ) => {
		setItemsPerPage( Number( value ) );
		setCurrentPage( 1 ); // Reset to first page when changing items per page
	};

	// Handle search
	const handleSelectedOptionChange = ( value ) => {
		setSelectedOption( value );
		setCurrentPage( 1 ); // Reset to first page when filter changes
	};

	// The page resets once the debounced term changes, not on every keystroke.
	const handleSearch = ( value ) => {
		setSearchText( value );
	};

	// Handle delete trigger
	const handleDeleteTrigger = () => {
		if ( selected.length === 0 ) {
			return;
		}
		setDeleteModal( { isOpen: true, type: 'bulk', id: null } );
	};

	// Handle bulk delete
	const handleBulkDelete = () => {
		setIsDeleting( true );
		const ajaxUrl = cart_abandonment_admin?.ajax_url;
		const nonce = cart_abandonment_admin?.delete_follow_up_reports_nonce;

		const formData = new window.FormData();
		formData.append( 'action', 'wcar_delete_follow_up_reports' );
		selected.forEach( ( id ) => formData.append( 'ids[]', id ) );
		formData.append( 'security', nonce );

		doApiFetch(
			ajaxUrl,
			formData,
			'POST',
			( response ) => {
				if ( response.success ) {
					setReloadKey( ( key ) => key + 1 );
					setSelected( [] );
					toast.success(
						__(
							'Record(s) deleted',
							'woo-cart-abandonment-recovery'
						)
					);
				} else {
					toast.error(
						__( 'Delete failed', 'woo-cart-abandonment-recovery' ),
						{
							description: response.data?.message || '',
						}
					);
				}
				setIsDeleting( false );
				setDeleteModal( { isOpen: false, type: null, id: null } );
			},
			( error ) => {
				toast.error(
					__( 'Delete failed', 'woo-cart-abandonment-recovery' ),
					{
						description: error.data?.message || '',
					}
				);
				setIsDeleting( false );
				setDeleteModal( { isOpen: false, type: null, id: null } );
			},
			true,
			false
		);
	};

	// Handle single delete
	const handleSingleDelete = () => {
		setIsDeleting( true );
		const ajaxUrl = cart_abandonment_admin?.ajax_url;
		const nonce = cart_abandonment_admin?.delete_follow_up_reports_nonce;

		const formData = new window.FormData();
		formData.append( 'action', 'wcar_delete_follow_up_reports' );
		formData.append( 'ids[]', deleteModal.id );
		formData.append( 'security', nonce );

		doApiFetch(
			ajaxUrl,
			formData,
			'POST',
			( response ) => {
				if ( response.success ) {
					setSelected( ( ids ) =>
						ids.filter( ( id ) => id !== deleteModal.id )
					);
					setReloadKey( ( key ) => key + 1 );
					toast.success(
						__( 'Record deleted', 'woo-cart-abandonment-recovery' )
					);
				} else {
					toast.error(
						__( 'Delete failed', 'woo-cart-abandonment-recovery' ),
						{
							description: response.data?.message || '',
						}
					);
				}
				setIsDeleting( false );
				setDeleteModal( { isOpen: false, type: null, id: null } );
			},
			( error ) => {
				toast.error(
					__( 'Delete failed', 'woo-cart-abandonment-recovery' ),
					{
						description: error.data?.message || '',
					}
				);
				setIsDeleting( false );
				setDeleteModal( { isOpen: false, type: null, id: null } );
			},
			true,
			false
		);
	};

	const handleConfirmDelete = () => {
		if ( deleteModal.type === 'bulk' ) {
			handleBulkDelete();
		} else {
			handleSingleDelete();
		}
	};

	const handleUnsubscribe = ( id ) => {
		const ajaxUrl = cart_abandonment_admin?.ajax_url;
		const nonce =
			cart_abandonment_admin?.unsubscribe_follow_up_reports_nonce;

		const formData = new window.FormData();
		formData.append( 'action', 'wcar_unsubscribe_follow_up_reports' );
		formData.append( 'ids[]', id );
		formData.append( 'security', nonce );

		doApiFetch(
			ajaxUrl,
			formData,
			'POST',
			( response ) => {
				if ( response.success ) {
					// Load the page again: the page on screen may have changed since the click.
					setReloadKey( ( key ) => key + 1 );
					toast.success(
						__(
							'Unsubscribed Successfully',
							'woo-cart-abandonment-recovery'
						)
					);
				} else {
					toast.error(
						__(
							'Unsubscribe failed',
							'woo-cart-abandonment-recovery'
						),
						{
							description: response.data?.message || '',
						}
					);
				}
			},
			( error ) => {
				toast.error(
					__( 'Unsubscribe failed', 'woo-cart-abandonment-recovery' ),
					{
						description: error.data?.message || '',
					}
				);
			},
			true,
			false
		);
	};

	const handleBlacklist = ( id, action ) => {
		const ajaxUrl = cart_abandonment_admin?.ajax_url;
		const nonce =
			'blacklist' === action
				? cart_abandonment_admin?.blacklist_cart_nonce
				: cart_abandonment_admin?.whitelist_cart_nonce;

		const formData = new window.FormData();
		formData.append( 'action', 'wcar_pro_' + action + '_cart' );
		formData.append( 'ids', String( id ) );
		formData.append( 'security', nonce );

		doApiFetch(
			ajaxUrl,
			formData,
			'POST',
			( response ) => {
				if ( response.success ) {
					// Load the page again: the row may no longer match the status filter.
					setReloadKey( ( key ) => key + 1 );
					// Sync the blacklist setting in the store so the Settings
					// page reflects the latest list without a page reload.
					if ( response.data?.blacklist_list !== undefined ) {
						dispatch( {
							type: ActionTypes.UPDATE_SETTINGS_DATA,
							payload: {
								option: 'wcf_ca_email_blacklist_list',
								value: response.data.blacklist_list,
							},
						} );
					}
					toast.success(
						'blacklist' === action
							? __(
									'Cart blacklisted successfully',
									'woo-cart-abandonment-recovery'
							  )
							: __(
									'Cart whitelisted successfully',
									'woo-cart-abandonment-recovery'
							  )
					);
				} else {
					toast.error(
						'blacklist' === action
							? __(
									'Blacklist failed',
									'woo-cart-abandonment-recovery'
							  )
							: __(
									'Whitelist failed',
									'woo-cart-abandonment-recovery'
							  ),
						{
							description: response.data?.message || '',
						}
					);
				}
			},
			( error ) => {
				toast.error(
					'blacklist' === action
						? __(
								'Blacklist failed',
								'woo-cart-abandonment-recovery'
						  )
						: __(
								'Whitelist failed',
								'woo-cart-abandonment-recovery'
						  ),
					{
						description: error.data?.message || '',
					}
				);
			},
			true,
			false
		);
	};

	// Bulk-flip selected rows to unsubscribed=1 — the free AJAX handler already accepts ids[].
	const handleBulkUnsubscribe = () => {
		if ( selected.length === 0 ) {
			return;
		}
		const ajaxUrl = cart_abandonment_admin?.ajax_url;
		const nonce =
			cart_abandonment_admin?.unsubscribe_follow_up_reports_nonce;

		const formData = new window.FormData();
		formData.append( 'action', 'wcar_unsubscribe_follow_up_reports' );
		// Send every selected id under the same ids[] key so PHP receives an array.
		selected.forEach( ( id ) => formData.append( 'ids[]', id ) );
		formData.append( 'security', nonce );

		doApiFetch(
			ajaxUrl,
			formData,
			'POST',
			( response ) => {
				if ( response.success ) {
					setReloadKey( ( key ) => key + 1 );
					setSelected( [] );
					toast.success(
						__(
							'Record(s) unsubscribed',
							'woo-cart-abandonment-recovery'
						)
					);
				} else {
					toast.error(
						__(
							'Unsubscribe failed',
							'woo-cart-abandonment-recovery'
						),
						{ description: response.data?.message || '' }
					);
				}
			},
			( error ) => {
				toast.error(
					__( 'Unsubscribe failed', 'woo-cart-abandonment-recovery' ),
					{ description: error.data?.message || '' }
				);
			},
			true,
			false
		);
	};

	// Bulk Blacklist/Whitelist — send selected ids as a CSV string; the pro handler
	// loops them and updates the shared blacklist option.
	const handleBulkBlacklistAction = ( action ) => {
		if ( selected.length === 0 ) {
			return;
		}

		const nonce =
			'blacklist' === action
				? cart_abandonment_admin?.blacklist_cart_nonce
				: cart_abandonment_admin?.whitelist_cart_nonce;

		const formData = new window.FormData();
		formData.append( 'action', 'wcar_pro_' + action + '_cart' );
		formData.append( 'security', nonce );
		formData.append( 'ids', selected.join( ',' ) );

		doApiFetch(
			cart_abandonment_admin?.ajax_url,
			formData,
			'POST',
			( response ) => {
				if ( ! response?.success ) {
					toast.error(
						response?.data?.message ||
							( 'blacklist' === action
								? __(
										'Blacklist failed',
										'woo-cart-abandonment-recovery'
								  )
								: __(
										'Whitelist failed',
										'woo-cart-abandonment-recovery'
								  ) )
					);
					return;
				}

				setReloadKey( ( key ) => key + 1 );

				if ( response?.data?.blacklist_list !== undefined ) {
					dispatch( {
						type: ActionTypes.UPDATE_SETTINGS_DATA,
						payload: {
							option: 'wcf_ca_email_blacklist_list',
							value: response.data.blacklist_list,
						},
					} );
				}

				setSelected( [] );
				toast.success(
					'blacklist' === action
						? __(
								'Cart(s) blacklisted',
								'woo-cart-abandonment-recovery'
						  )
						: __(
								'Cart(s) whitelisted',
								'woo-cart-abandonment-recovery'
						  )
				);
			},
			undefined,
			true,
			false
		);
	};

	// Thin wrappers so the Apply switch case reads as `handleBulkBlacklist()` / `handleBulkWhitelist()`.
	const handleBulkBlacklist = () => handleBulkBlacklistAction( 'blacklist' );
	const handleBulkWhitelist = () => handleBulkBlacklistAction( 'whitelist' );

	// Handle detailed screen navigation
	const handleDetailedScreen = ( id ) => {
		navigate( {
			search: `?page=woo-cart-abandonment-recovery&path=detailed-report&id=${ id }`,
		} );
	};

	const handleCancelSelect = () => {
		setSelected( [] );
	};

	// Bulk-action availability follows the selection contents, not the active tab.
	const selectedRecords = data.filter( ( record ) =>
		selected.includes( record.id )
	);
	const selectionHasBlacklisted = selectedRecords.some(
		( record ) => 'Blacklisted' === record.orderStatus
	);
	const selectionHasNonBlacklisted = selectedRecords.some(
		( record ) => 'Blacklisted' !== record.orderStatus
	);

	// Build the dropdown options list based on what the current selection can act on.
	// Says what goes with the report: the cart and its email, SMS and WhatsApp history.
	const getDeleteDescription = () => {
		if ( deleteModal.type === 'bulk' ) {
			return sprintf(
				/* translators: %d: number of selected reports */
				_n(
					'Are you sure you want to delete the %d selected report? Its cart and follow-up history will be removed. This action cannot be undone.',
					'Are you sure you want to delete the %d selected reports? Their carts and follow-up history will be removed. This action cannot be undone.',
					selected.length,
					'woo-cart-abandonment-recovery'
				),
				selected.length
			);
		}

		const userName = data
			.find( ( record ) => record.id === deleteModal.id )
			?.userName?.trim();
		if ( ! userName ) {
			return __(
				'Are you sure you want to delete this report? The cart and its follow-up history will be removed. This action cannot be undone.',
				'woo-cart-abandonment-recovery'
			);
		}
		return sprintf(
			/* translators: %s: customer name */
			__(
				'Are you sure you want to delete the report for “%s”? The cart and its follow-up history will be removed. This action cannot be undone.',
				'woo-cart-abandonment-recovery'
			),
			userName
		);
	};

	const bulkActionOptions = [];
	// Unsubscribe is meaningful only if any selected row is not already blacklisted.
	if ( selectionHasNonBlacklisted ) {
		bulkActionOptions.push( {
			id: 'unsubscribe',
			title: __( 'Unsubscribe', 'woo-cart-abandonment-recovery' ),
		} );
	}
	// Blacklist/Whitelist are pro features — hide entirely when the pro plugin isn't active.
	if ( ! isFeatureBlocked && selectionHasNonBlacklisted ) {
		bulkActionOptions.push( {
			id: 'blacklist',
			title: __( 'Blacklist', 'woo-cart-abandonment-recovery' ),
		} );
	}
	if ( ! isFeatureBlocked && selectionHasBlacklisted ) {
		bulkActionOptions.push( {
			id: 'whitelist',
			title: __( 'Whitelist', 'woo-cart-abandonment-recovery' ),
		} );
	}
	// Delete is always available regardless of status.
	bulkActionOptions.push( {
		id: 'delete',
		title: __( 'Delete', 'woo-cart-abandonment-recovery' ),
	} );

	// Route the dropdown's picked action to the matching handler, then reset the picker.
	const handleApplyBulkAction = () => {
		if ( ! bulkAction ) {
			return;
		}
		switch ( bulkAction.id ) {
			case 'unsubscribe':
				handleBulkUnsubscribe();
				break;
			case 'blacklist':
				handleBulkBlacklist();
				break;
			case 'whitelist':
				handleBulkWhitelist();
				break;
			case 'delete':
				handleDeleteTrigger();
				break;
		}
		setBulkAction( null );
	};

	// While rows are selected the bulk toolbar takes the place of the filters, so the
	// header stays on one row instead of pushing the filters down.
	const isBulkMode = ! isLoading && selected.length > 0;

	return (
		<div className="p-4 md:p-8">
			<SectionWrapper className="flex flex-col gap-4">
				<div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:flex-wrap lg:justify-between relative lg:min-h-10">
					<div className="flex flex-wrap gap-4 items-center">
						<Title
							size="sm"
							tag="h1"
							title={ __(
								'Follow Up Reports',
								'woo-cart-abandonment-recovery'
							) }
							className="[&_h2]:text-gray-900"
						/>
						{ /* Bulk-action toolbar — only rendered while at least one row is selected. */ }
						{ isBulkMode && (
							// shrink-0 keeps the toolbar from getting squished by the right-side filters.
							<div className="flex gap-4 items-center shrink-0 pl-4 border-0 border-l border-solid border-gray-200">
								<Button
									variant="ghost"
									icon={
										<XMarkIcon className="h-6 w-6 text-gray-500" />
									}
									size="xs"
									className="text-icon-secondary hover:text-icon-primary"
									onClick={ handleCancelSelect }
								/>
								{ /* whitespace-nowrap keeps "N Selected" on one line when space is tight. */ }
								<span
									className="text-sm font-normal text-gray-500 whitespace-nowrap"
									role="status"
								>
									{ sprintf(
										__(
											'%d Selected',
											'woo-cart-abandonment-recovery'
										),
										selected.length
									) }
								</span>
								{ /* Bulk-actions dropdown — options come from bulkActionOptions above. */ }
								<Select
									onChange={ setBulkAction }
									size="sm"
									value={ bulkAction?.title || '' }
								>
									<Select.Button
										className="w-40 text-gray-500"
										placeholder={ __(
											'Bulk Actions',
											'woo-cart-abandonment-recovery'
										) }
									/>
									<Select.Options>
										{ bulkActionOptions.map( ( option ) => (
											<Select.Option
												key={ option.id }
												value={ option }
											>
												{ option.title }
											</Select.Option>
										) ) }
									</Select.Options>
								</Select>
								{ /* Apply stays disabled until the user picks something from the dropdown. */ }
								<Button
									size="sm"
									tag="button"
									type="button"
									variant="primary"
									disabled={ ! bulkAction }
									onClick={ handleApplyBulkAction }
								>
									{ __(
										'Apply',
										'woo-cart-abandonment-recovery'
									) }
								</Button>
							</div>
						) }
					</div>
					{ ! isBulkMode && (
						<div className="flex flex-col lg:flex-row lg:ml-auto gap-4">
							{ filtersApplied && (
								<ClearFiltersButton onClick={ handleClearFilters } />
							) }

							<Input
								placeholder={ __( 'Search…', 'woo-cart-abandonment-recovery' ) }
								prefix={
									<MagnifyingGlassIcon className="h-6 w-6 text-gray-500" />
								}
								size="sm"
								type="search"
								aria-label={ __(
									'Search',
									'woo-cart-abandonment-recovery'
								) }
								value={ searchText }
								onChange={ handleSearch }
								className="w-full lg:w-52 [&_input]:min-h-0"
								disabled={ isLoading }
							/>
							<Select
								onChange={ handleSelectedOptionChange }
								size="sm"
								value={ selectedOption.title }
								disabled={ isLoading }
							>
								<Select.Button className="w-full lg:w-52 text-gray-500" />
								<Select.Options>
									{ filterOptions.map( ( option ) => (
										<Select.Option
											key={ option.id }
											value={ option }
										>
											{ option.title }
										</Select.Option>
									) ) }
								</Select.Options>
							</Select>
							<DateRange
								selectedRange={ selectedRange }
								setSelectedRange={ handleDateRangeChange }
								disabled={ isLoading }
								disableFutureDates
							/>
							<ExportToExcel
								fetchData={ fetchAllReports }
								columns={ EXPORT_COLUMNS }
								filename="followUpReport"
								disabled={ isLoading || ! hasRecords }
							/>
						</div>
					) }
				</div>
				<p className="sr-only" role="status">
					{ ! isLoading &&
						! isRefreshing &&
						sprintf(
							/* translators: %d: number of reports that match the search and filters */
							_n(
								'%d report found',
								'%d reports found',
								totalItems,
								'woo-cart-abandonment-recovery'
							),
							totalItems
						) }
				</p>
				{ isLoading ? (
					<FollowUpTableSkeleton
						actionCount={ isFeatureBlocked ? 3 : 4 }
					/>
				) : loadFailed ? (
					<LoadFailedBlock
						title={ __(
							'Could not load the reports',
							'woo-cart-abandonment-recovery'
						) }
						onRetry={ () => setReloadKey( ( key ) => key + 1 ) }
					/>
				) : ! hasRecords ? (
					<EmptyBlock
						className="my-2"
						icon={
							<ExclamationTriangleIcon className="h-12 w-12 text-yellow-500" />
						}
						title={ __(
							'No Follow-Up Reports Yet',
							'woo-cart-abandonment-recovery'
						) }
						description={ __(
							'Reports will show up here once customers start abandoning their carts.',
							'woo-cart-abandonment-recovery'
						) }
					/>
				) : data.length === 0 ? (
					<NoResultsBlock
						title={ __(
							'No reports match these filters',
							'woo-cart-abandonment-recovery'
						) }
						description={ __(
							'No follow-up reports match the current search, status or dates. Try changing them.',
							'woo-cart-abandonment-recovery'
						) }
					/>
				) : (
					<ScrollableTable
						label={ __(
							'Follow Up Reports',
							'woo-cart-abandonment-recovery'
						) }
					>
						<Table
							checkboxSelection={ true }
							className={ cn(
								SELECTABLE_TABLE_CLASS,
								'transition-opacity',
								isRefreshing && 'opacity-60'
							) }
							aria-label={ __(
								'Follow Up Reports',
								'woo-cart-abandonment-recovery'
							) }
							aria-busy={ isRefreshing }
						>
							<Table.Head
								selected={ selected.length > 0 }
								onChangeSelection={ toggleSelectAll }
								indeterminate={
									selected.length > 0 &&
									selected.length < data.length
								}
							>
								<Table.HeadCell>
									{ __(
										'User Name',
										'woo-cart-abandonment-recovery'
									) }
								</Table.HeadCell>
								<Table.HeadCell>
									{ __(
										'Email To',
										'woo-cart-abandonment-recovery'
									) }
								</Table.HeadCell>
								<Table.HeadCell>
									{ __(
										'Cart Total',
										'woo-cart-abandonment-recovery'
									) }
								</Table.HeadCell>
								<Table.HeadCell>
									{ __(
										'Order Status',
										'woo-cart-abandonment-recovery'
									) }
								</Table.HeadCell>
								<Table.HeadCell>
									{ __(
										'Date & Time',
										'woo-cart-abandonment-recovery'
									) }
								</Table.HeadCell>
								<Table.HeadCell className="text-right">
									{ __(
										'Actions',
										'woo-cart-abandonment-recovery'
									) }
								</Table.HeadCell>
							</Table.Head>
							<Table.Body>
								{ data.map( ( item ) => (
									<Table.Row
										key={ item.id }
										value={ item }
										className={ getRowClass( {
											isSelected: selected.includes(
												item.id
											),
										} ) }
										selected={ selected.includes(
											item.id
										) }
										onChangeSelection={
											handleCheckboxChange
										}
									>
										<Table.Cell>
											<TableLinkButton
												onClick={ () =>
													handleDetailedScreen(
														item.id
													)
												}
											>
												{ item.userName }
											</TableLinkButton>
										</Table.Cell>
										<Table.Cell>
											{ item?.email ||
												notAvailableString }
										</Table.Cell>
										<Table.Cell>
											{ item?.cartTotal ||
												notAvailableString }
										</Table.Cell>
										<Table.Cell>
											<OrderStatusBadge
												status={
													item?.orderStatus ||
													notAvailableString
												}
											/>
										</Table.Cell>
										<Table.Cell>
											{ item?.dateTime ||
												notAvailableString }
										</Table.Cell>
										<Table.Cell>
											<FollowUpRowActions
												item={ item }
												canBlacklist={
													! isFeatureBlocked
												}
												onView={ () =>
													handleDetailedScreen(
														item.id
													)
												}
												onUnsubscribe={ () =>
													handleUnsubscribe( item.id )
												}
												onBlacklist={ ( action ) =>
													handleBlacklist(
														item.id,
														action
													)
												}
												onDelete={ () =>
													setDeleteModal( {
														isOpen: true,
														type: 'single',
														id: item.id,
													} )
												}
											/>
										</Table.Cell>
									</Table.Row>
								) ) }
							</Table.Body>
							<Table.Footer>
								<TablePagination
									itemsPerPage={ itemsPerPage }
									onItemsPerPageChange={
										handleItemsPerPageChange
									}
									currentPage={ currentPage }
									totalPages={ totalPages }
									onPageChange={ handlePageChange }
								/>
							</Table.Footer>
						</Table>
					</ScrollableTable>
				) }
				<ConfirmDialog
					open={ deleteModal.isOpen }
					setOpen={ () =>
						setDeleteModal( {
							isOpen: false,
							type: null,
							id: null,
						} )
					}
					onConfirm={ handleConfirmDelete }
					title={
						deleteModal.type === 'bulk'
							? __(
									'Delete Selected Reports',
									'woo-cart-abandonment-recovery'
							  )
							: __(
									'Delete Report',
									'woo-cart-abandonment-recovery'
							  )
					}
					description={ getDeleteDescription() }
					isConfirming={ isDeleting }
					isDestructive
					confirmLabel={ __( 'Delete', 'woo-cart-abandonment-recovery' ) }
				/>
			</SectionWrapper>
		</div>
	);
};

export default FollowUp;

