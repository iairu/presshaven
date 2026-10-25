/* eslint-disable no-mixed-spaces-and-tabs, indent, @wordpress/i18n-no-variables, @wordpress/i18n-no-collapsible-whitespace, @wordpress/i18n-translator-comments */
import { useState, useEffect, useRef } from 'react';
import {
	Title,
	Table,
	Input,
	Button,
	toast,
} from '@bsf/force-ui';
import {
	TrashIcon,
	MagnifyingGlassIcon,
	XMarkIcon,
	EyeIcon,
	InformationCircleIcon,
} from '@heroicons/react/24/outline';
import { __, _n, sprintf } from '@wordpress/i18n';

import { cn, toDateParam } from '@Utils/helper';
import ClearFiltersButton from '@Components/common/ClearFiltersButton';
import LoadFailedBlock from '@Components/common/LoadFailedBlock';
import NoResultsBlock from '@Components/common/NoResultsBlock';
import ScrollableTable from '@Components/common/ScrollableTable';
import SectionWrapper from '@Components/common/SectionWrapper';
import ProductTableSkeleton from '@Components/product/ProductTableSkeleton';
import { doApiFetch } from '@Store';
import ExportToExcel from '@Components/common/ExportToExcel';
import AppTooltip from '@Components/common/AppTooltip';
import TablePagination from '@Components/common/TablePagination';
import {
	getRowClass,
	SELECTABLE_TABLE_CLASS,
} from '@Components/common/tableStyles';
import TableRowAction from '@Components/common/TableRowAction';
import ConfirmDialog from '@Components/common/ConfirmDialog';
import { ProUpgradeCta, ProductReportDummyData } from '@Components/pro';
import { useProAccess } from '@Components/pro/useProAccess';
import DateRange from '@Components/fields/DateRange';
import { useDateRangeFilter } from '@Components/fields/useDateRangeFilter';

// Column heading with a short explanation. The hint opens on focus as well as hover, and a screen
// reader reads it as the icon's name.
const HeadingWithHint = ( { heading, hint } ) => (
	<div className="flex items-center">
		{ heading }
		<AppTooltip
			content={ hint }
			position="top"
			triggers={ [ 'hover', 'focus' ] }
		>
			<span
				tabIndex={ 0 }
				role="img"
				aria-label={ hint }
				className="ml-1 inline-flex h-6 w-6 items-center justify-center rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus [@media(pointer:coarse)]:h-11 [@media(pointer:coarse)]:w-11"
			>
				<InformationCircleIcon className="h-4 w-4 text-gray-500" />
			</span>
		</AppTooltip>
	</div>
);

// What the export file holds, in order.
const EXPORT_COLUMNS = [
	{ key: 'id', label: __( 'Product ID', 'woo-cart-abandonment-recovery' ) },
	{ key: 'productName', label: __( 'Product Name', 'woo-cart-abandonment-recovery' ) },
	{ key: 'abandoned', label: __( 'Times Abandoned', 'woo-cart-abandonment-recovery' ) },
	{ key: 'recovered', label: __( 'Times Recovered', 'woo-cart-abandonment-recovery' ) },
	{ key: 'productLink', label: __( 'Product Link', 'woo-cart-abandonment-recovery' ) },
];

const Product = () => {
	const [ selected, setSelected ] = useState( [] );
	const [ currentPage, setCurrentPage ] = useState( 1 );
	const [ itemsPerPage, setItemsPerPage ] = useState( 20 );
	const [ searchText, setSearchText ] = useState( '' );
	// The first load shows the skeleton; later loads (a new date range, or after a delete) keep the
	// rows on screen, dimmed, so the table does not flash.
	const [ isLoading, setIsLoading ] = useState( false );
	const [ isRefreshing, setIsRefreshing ] = useState( false );
	const [ data, setData ] = useState( [] );
	// The last request for the report failed, so what is on screen cannot be trusted.
	const [ loadFailed, setLoadFailed ] = useState( false );
	const [ reloadKey, setReloadKey ] = useState( 0 );
	const hasLoaded = useRef( false );
	const latestRequest = useRef( 0 );
	const { canAccessProFeatures, shouldBlockProFeatures } = useProAccess();

	const [ deleteModal, setDeleteModal ] = useState( {
		isOpen: false,
		type: null,
		id: null,
	} );
	const [ isDeleting, setIsDeleting ] = useState( false );
	// The default range is the date field's placeholder, and the report loads it until the user
	// applies another range.
	const {
		defaultRange,
		selectedRange,
		setSelectedRange,
		clearRange,
		hasPickedRange,
		activeRange,
	} = useDateRangeFilter();
	// Single condition check - this is all you need for pro feature access!
	const canAccessPro = canAccessProFeatures();
	const isFeatureBlocked = shouldBlockProFeatures();

	// Ask the server for the report. An answer that arrives after a newer request is dropped.
	useEffect( () => {
		// Only fetch data if pro features are accessible
		if ( ! canAccessPro ) {
			return undefined;
		}
		const requestId = ++latestRequest.current;
		const fetchData = async () => {
			if ( hasLoaded.current ) {
				setIsRefreshing( true );
			} else {
				setIsLoading( true );
			}
			const response = await new Promise( ( resolve ) => {
				doApiFetch(
					'/wcar-pro/api/admin/product-report',
					{
						date_range: {
							from: toDateParam( activeRange.from ),
							to: toDateParam( activeRange.to ),
						},
					},
					'POST',
					resolve,
					() => resolve( null )
				).catch( () => {} );
			} );
			if ( requestId !== latestRequest.current ) {
				return;
			}
			if ( response && Array.isArray( response.items ) ) {
				hasLoaded.current = true;
				setLoadFailed( false );
				setData( response.items );
			} else {
				setLoadFailed( true );
			}
			setIsLoading( false );
			setIsRefreshing( false );
		};
		fetchData();
		return () => {
			latestRequest.current++;
		};
	}, [ canAccessPro, selectedRange, reloadKey ] );

	// Selection belongs to the rows on screen, so it ends when they change.
	useEffect( () => {
		setSelected( [] );
	}, [ currentPage, itemsPerPage, searchText, selectedRange ] );

	const handleCheckboxChange = ( checked, value ) => {
		if ( checked ) {
			setSelected( [ ...selected, value.id ] );
		} else {
			setSelected( selected.filter( ( item ) => item !== value.id ) );
		}
	};

	const toggleSelectAll = ( checked ) => {
		if ( checked ) {
			setSelected( currentItems.map( ( item ) => item.id ) );
		} else {
			setSelected( [] );
		}
	};

	const handleSearch = ( value ) => {
		setSearchText( value );
		setCurrentPage( 1 );
	};

	const handleItemsPerPageChange = ( value ) => {
		setItemsPerPage( Number( value ) );
		setCurrentPage( 1 );
	};

	const handlePageChange = ( page ) => {
		setCurrentPage( page );
	};

	const handleDateRangeChange = ( range ) => {
		setSelectedRange( range );
		setCurrentPage( 1 ); // Reset to first page when date range changes
	};

	const filteredData = data.filter( ( item ) =>
		item.productName.toLowerCase().includes( searchText.toLowerCase() )
	);

	const indexOfLastItem = currentPage * itemsPerPage;
	const indexOfFirstItem = indexOfLastItem - itemsPerPage;
	const currentItems = filteredData.slice(
		indexOfFirstItem,
		indexOfLastItem
	);
	const totalPages = Math.ceil( filteredData.length / itemsPerPage );

	// The page on screen can fall off the end when rows go away, so step back to the new last page.
	useEffect( () => {
		if ( totalPages > 0 && currentPage > totalPages ) {
			setCurrentPage( totalPages );
		}
	}, [ totalPages, currentPage ] );

	const filtersApplied = searchText !== '' || hasPickedRange;

	const handleClearFilters = () => {
		setSearchText( '' );
		clearRange();
		setCurrentPage( 1 );
	};

	// Handle delete trigger
	const handleDeleteTrigger = () => {
		if ( selected.length === 0 ) {
			return;
		}
		setDeleteModal( { isOpen: true, type: 'bulk', id: null } );
	};

	// The server deletes the carts that hold these products inside the dates on screen, and the other
	// products in those carts lose them too, so the whole report is loaded again afterwards.
	const deleteProducts = ( ids, successMessage ) => {
		setIsDeleting( true );
		const ajaxUrl = cart_abandonment_admin?.ajax_url;
		const nonce = cart_abandonment_admin?.delete_product_reports_nonce;

		const formData = new window.FormData();
		formData.append( 'action', 'wcar_pro_delete_product_reports' );
		ids.forEach( ( id ) => formData.append( 'ids[]', id ) );
		formData.append( 'date_from', toDateParam( activeRange.from ) );
		formData.append( 'date_to', toDateParam( activeRange.to ) );
		formData.append( 'security', nonce );

		const finish = () => {
			setIsDeleting( false );
			setDeleteModal( { isOpen: false, type: null, id: null } );
		};

		doApiFetch(
			ajaxUrl,
			formData,
			'POST',
			( response ) => {
				if ( response.success ) {
					setSelected( [] );
					setReloadKey( ( key ) => key + 1 );
					toast.success( successMessage );
				} else {
					toast.error(
						__( 'Delete failed', 'woo-cart-abandonment-recovery' ),
						{
							description: response.data?.message || '',
						}
					);
				}
				finish();
			},
			( error ) => {
				toast.error(
					__( 'Delete failed', 'woo-cart-abandonment-recovery' ),
					{
						description: error.data?.message || '',
					}
				);
				finish();
			},
			true
		).catch( () => {} );
	};

	const handleConfirmDelete = () => {
		if ( deleteModal.type === 'bulk' ) {
			deleteProducts(
				selected,
				__( 'Record(s) deleted', 'woo-cart-abandonment-recovery' )
			);
		} else {
			deleteProducts(
				[ deleteModal.id ],
				__( 'Record deleted', 'woo-cart-abandonment-recovery' )
			);
		}
	};

	// Says what goes with the product: the carts that hold it and their follow-up history, and the
	// counts of the other products in those carts.
	const getDeleteDescription = () => {
		if ( deleteModal.type === 'bulk' ) {
			return sprintf(
				/* translators: %d: number of selected products */
				_n(
					'Are you sure you want to delete the %d selected product? The carts that contain it and their follow-up history will be removed, and other products in those carts will lose those cart counts too. This action cannot be undone.',
					'Are you sure you want to delete the %d selected products? The carts that contain them and their follow-up history will be removed, and other products in those carts will lose those cart counts too. This action cannot be undone.',
					selected.length,
					'woo-cart-abandonment-recovery'
				),
				selected.length
			);
		}

		const product = data.find( ( item ) => item.id === deleteModal.id );
		const name = product?.productName?.trim();
		if ( ! name ) {
			return __(
				'Are you sure you want to delete this product? The carts that contain it and their follow-up history will be removed, and other products in those carts will lose those cart counts too. This action cannot be undone.',
				'woo-cart-abandonment-recovery'
			);
		}
		return sprintf(
			/* translators: %s: product name and ID, e.g. "Blue Hoodie (#123)" */
			__(
				'Are you sure you want to delete the product “%s”? The carts that contain it and their follow-up history will be removed, and other products in those carts will lose those cart counts too. This action cannot be undone.',
				'woo-cart-abandonment-recovery'
			),
			`${ name } (#${ product.id })`
		);
	};

	const handleCancelSelect = () => {
		setSelected( [] );
	};

	const handleViewClick = ( productLink ) => {
		if ( productLink ) {
			window.open( productLink, '_blank', 'noopener,noreferrer' );
		}
	};

	// While rows are selected the bulk toolbar takes the place of the filters, so the
	// header stays on one row instead of pushing the filters down.
	const isBulkMode = ! isLoading && selected.length > 0;

	return (
		<div className="p-4 md:p-8">
			<SectionWrapper className="flex flex-col gap-4">
				<div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 relative md:min-h-10">
					<div className="flex flex-wrap gap-4 items-center">
						<Title
							size="sm"
							tag="h1"
							title={ __(
								'Product Reports',
								'woo-cart-abandonment-recovery'
							) }
							className="[&_h2]:text-gray-900"
						/>
						{ isBulkMode && (
							// shrink-0 keeps the toolbar from getting squished by the filters.
							<div className="flex gap-4 items-center shrink-0 pl-4 border-0 border-l border-solid border-gray-200">
								<Button
									variant="ghost"
									icon={
										<XMarkIcon className="h-6 w-6 text-gray-500" />
									}
									size="xs"
									className="text-icon-secondary hover:text-icon-primary"
									aria-label={ __(
										'Clear selection',
										'woo-cart-abandonment-recovery'
									) }
									onClick={ handleCancelSelect }
								/>
								<span
									className="text-sm font-normal text-gray-500 whitespace-nowrap"
									role="status"
								>
									{ sprintf(
										/* translators: %d: number of selected products */
										__(
											'%d Selected',
											'woo-cart-abandonment-recovery'
										),
										selected.length
									) }
								</span>
								<Button
									className="py-2 px-4 bg-red-50 text-red-600 outline-red-600 hover:bg-red-50 hover:outline-red-600"
									size="sm"
									tag="button"
									type="button"
									variant="outline"
									icon={ <TrashIcon className="h-4 w-4" /> }
									iconPosition="left"
									onClick={ handleDeleteTrigger }
								>
									{ __( 'Delete', 'woo-cart-abandonment-recovery' ) }
								</Button>
							</div>
						) }
					</div>
					{ ! isBulkMode && (
						<div className="flex flex-col lg:flex-row gap-4">
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
							<DateRange
								selectedRange={ selectedRange }
								placeholder={ defaultRange }
								setSelectedRange={ handleDateRangeChange }
								disabled={ isLoading }
								disableFutureDates
							/>
							<ExportToExcel
								data={ filteredData }
								columns={ EXPORT_COLUMNS }
								filename="productReport"
								disabled={ isLoading || loadFailed }
							/>
						</div>
					) }
				</div>
				<p className="sr-only" role="status">
					{ canAccessPro &&
						! isLoading &&
						! isRefreshing &&
						! loadFailed &&
						sprintf(
							/* translators: %d: number of products that match the search and dates */
							_n(
								'%d product found',
								'%d products found',
								filteredData.length,
								'woo-cart-abandonment-recovery'
							),
							filteredData.length
						) }
				</p>
				{ isLoading ? (
					<ProductTableSkeleton />
				) : isFeatureBlocked ? (
					// Show dummy data with modal overlay when pro is not active or feature is blocked
					<div className="relative">
						<ProductReportDummyData />
						<ProUpgradeCta
							isVisible={ true }
							highlightText={ __(
								'Unlock Pro Features',
								'woo-cart-abandonment-recovery'
							) }
							mainTitle={ __(
								'Cart Abandonment Recovery Pro is Here 🔥',
								'woo-cart-abandonment-recovery'
							) }
							description={ __(
								"You've seen how emails bring shoppers back. With Pro, you'll unlock advanced tools that recover more carts, boost profits, and grow your store faster.",
								'woo-cart-abandonment-recovery'
							) }
							usps={ [
								__(
									'Product Reports',
									'woo-cart-abandonment-recovery'
								),
								__(
									'SMS + WhatsApp Followups',
									'woo-cart-abandonment-recovery'
								),
								__(
									'Smart Rules',
									'woo-cart-abandonment-recovery'
								),
								__(
									'Advanced Automations',
									'woo-cart-abandonment-recovery'
								),
								__(
									'And More…',
									'woo-cart-abandonment-recovery'
								),
							] }
							footerMessage={ '' }
							backgroundBlur={ true }
						/>
					</div>
				) : loadFailed ? (
					<LoadFailedBlock
						title={ __(
							'Could not load the product reports',
							'woo-cart-abandonment-recovery'
						) }
						onRetry={ () => setReloadKey( ( key ) => key + 1 ) }
					/>
				) : data.length === 0 ? (
					<NoResultsBlock
						title={ __(
							'No product data for these dates',
							'woo-cart-abandonment-recovery'
						) }
						description={ __(
							'No products were abandoned or recovered in the selected date range. Try a wider date range.',
							'woo-cart-abandonment-recovery'
						) }
					/>
				) : filteredData.length === 0 ? (
					<NoResultsBlock
						title={ __(
							'No matching products',
							'woo-cart-abandonment-recovery'
						) }
						description={ __(
							'Try a different search term.',
							'woo-cart-abandonment-recovery'
						) }
					/>
				) : (
					<ScrollableTable
						label={ __(
							'Product Reports',
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
								'Product Reports',
								'woo-cart-abandonment-recovery'
							) }
							aria-busy={ isRefreshing }
						>
							<Table.Head
								selected={ selected.length > 0 }
								onChangeSelection={ toggleSelectAll }
								indeterminate={
									selected.length > 0 &&
									selected.length < currentItems.length
								}
							>
								<Table.HeadCell>
									{ __(
										'Product Name',
										'woo-cart-abandonment-recovery'
									) }
								</Table.HeadCell>
								<Table.HeadCell>
									<HeadingWithHint
										heading={ __(
											'Times Abandoned',
											'woo-cart-abandonment-recovery'
										) }
										hint={ __(
											'Total times the product was abandoned and the associated abandoned amount',
											'woo-cart-abandonment-recovery'
										) }
									/>
								</Table.HeadCell>
								<Table.HeadCell>
									<HeadingWithHint
										heading={ __(
											'Times Recovered',
											'woo-cart-abandonment-recovery'
										) }
										hint={ __(
											'Total times the product was recovered and the associated recovered amount',
											'woo-cart-abandonment-recovery'
										) }
									/>
								</Table.HeadCell>
								<Table.HeadCell className="text-right">
									<span className="">
										{ __(
											'Actions',
											'woo-cart-abandonment-recovery'
										) }
									</span>
								</Table.HeadCell>
							</Table.Head>

							<Table.Body>
								{ currentItems.map( ( item ) => (
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
											<a
												href={ item?.productLink }
												className="w-fit flex gap-2 items-center cursor-pointer no-underline text-inherit hover:text-flamingo-400 focus-visible:text-flamingo-400"
												target="_blank"
												rel="noreferrer"
											>
												<img
													src={ item?.imageUrl }
													alt=""
													width={ 48 }
													height={ 48 }
													loading="lazy"
													decoding="async"
													className="w-12 h-12 object-cover rounded-md border border-solid border-gray-200"
												/>
												<span>
													{ item.productName } (#
													{ item.id })
												</span>
											</a>
										</Table.Cell>
										<Table.Cell>
											{ item.abandoned }
										</Table.Cell>
										<Table.Cell>
											{ item.recovered }
										</Table.Cell>
										<Table.Cell>
											<div className="flex items-center justify-end gap-2">
												<TableRowAction
													label={ __(
														'View',
														'woo-cart-abandonment-recovery'
													) }
													icon={
														<EyeIcon className="h-6 w-6" />
													}
													disabled={ ! item?.productLink }
													onClick={ () =>
														handleViewClick(
															item?.productLink
														)
													}
													className="text-gray-500 hover:text-flamingo-400"
												/>
												<TableRowAction
													label={ __(
														'Delete',
														'woo-cart-abandonment-recovery'
													) }
													icon={
														<TrashIcon className="h-6 w-6" />
													}
													onClick={ () =>
														setDeleteModal( {
															isOpen: true,
															type: 'single',
															id: item.id,
														} )
													}
													className="text-gray-500 hover:text-red-600"
												/>
											</div>
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
									'Delete Selected Products',
									'woo-cart-abandonment-recovery'
							  )
							: __(
									'Delete Product',
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

export default Product;

