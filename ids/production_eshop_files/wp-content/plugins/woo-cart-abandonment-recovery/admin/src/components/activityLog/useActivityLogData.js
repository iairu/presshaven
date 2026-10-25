import { useEffect, useMemo, useState } from 'react';

import { doApiFetch } from '@Store';
import { useProAccess } from '@Components/pro/useProAccess';
import { formatLocalDate } from '@Utils/helper';
import {
	CHANNEL_OPTIONS,
	ACTIVITY_STATUS_OPTIONS,
	SCHEDULED_STATUS_OPTIONS,
} from './constants';

const useActivityLogData = ( type ) => {
	const isScheduled = type === 'scheduled';
	const statusOptions = isScheduled
		? SCHEDULED_STATUS_OPTIONS
		: ACTIVITY_STATUS_OPTIONS;

	const { shouldBlockProFeatures, upgradeActionButton } = useProAccess();
	const proCfg =
		typeof cart_abandonment_admin !== 'undefined'
			? cart_abandonment_admin?.activity_log
			: null;
	const isBlocked = shouldBlockProFeatures() || ! proCfg;

	const [ channel, setChannel ] = useState( CHANNEL_OPTIONS[ 0 ] );
	const [ status, setStatus ] = useState( statusOptions[ 0 ] );
	const [ dateRange, setDateRange ] = useState( { from: null, to: null } );
	const [ search, setSearch ] = useState( '' );
	const [ debouncedSearch, setDebouncedSearch ] = useState( '' );
	const [ currentPage, setCurrentPage ] = useState( 1 );
	const [ itemsPerPage, setItemsPerPage ] = useState( 20 );
	const [ items, setItems ] = useState( [] );
	const [ total, setTotal ] = useState( 0 );
	const [ isLoading, setIsLoading ] = useState( false );
	const [ hasLoaded, setHasLoaded ] = useState( false );
	const [ loadFailed, setLoadFailed ] = useState( false );
	const [ reloadKey, setReloadKey ] = useState( 0 );

	// Debounce the recipient search so typing doesn't fire one REST request per
	// keystroke; the query (and page reset) only applies after the user pauses.
	useEffect( () => {
		const handle = setTimeout( () => {
			setDebouncedSearch( search );
			setCurrentPage( 1 );
		}, 400 );
		return () => clearTimeout( handle );
	}, [ search ] );

	const filtersApplied = Boolean(
		channel?.id !== 'all' ||
			status?.id !== 'all' ||
			search !== '' ||
			dateRange.from ||
			dateRange.to
	);

	const payload = useMemo(
		() => ( {
			channel: channel?.id || 'all',
			status: status?.id || 'all',
			search: debouncedSearch,
			date_from: dateRange.from ? formatLocalDate( dateRange.from ) : '',
			date_to: dateRange.to ? formatLocalDate( dateRange.to ) : '',
			page: currentPage,
			per_page: itemsPerPage,
		} ),
		[ channel, status, debouncedSearch, dateRange, currentPage, itemsPerPage ]
	);

	const endpoint = isScheduled
		? proCfg?.endpoints?.scheduled
		: proCfg?.endpoints?.log;
	const canFetch = ! isBlocked && Boolean( endpoint );

	useEffect( () => {
		if ( ! canFetch ) {
			return;
		}
		// A slower, older request must not overwrite the answer to a newer one.
		let isStale = false;
		setIsLoading( true );
		setLoadFailed( false );
		doApiFetch(
			endpoint,
			payload,
			'POST',
			( response ) => {
				if ( isStale ) {
					return;
				}
				setItems( response?.items || [] );
				setTotal( response?.total || 0 );
				setHasLoaded( true );
				setIsLoading( false );
			},
			() => {
				if ( isStale ) {
					return;
				}
				setItems( [] );
				setTotal( 0 );
				setLoadFailed( true );
				setIsLoading( false );
			}
		).catch( () => {
			// `doApiFetch` has already reported the failure through `onError`.
		} );
		return () => {
			isStale = true;
		};
	}, [ canFetch, endpoint, payload, reloadKey ] );

	const clearFilters = () => {
		setChannel( CHANNEL_OPTIONS[ 0 ] );
		setStatus( statusOptions[ 0 ] );
		setDateRange( { from: null, to: null } );
		setSearch( '' );
		setDebouncedSearch( '' );
		setCurrentPage( 1 );
	};

	return {
		isBlocked,
		// A request with no rows on screen yet (the first one, or a retry after a failure):
		// the table is a skeleton, not an empty state.
		isInitialLoading:
			canFetch && ! loadFailed && ( ! hasLoaded || ( isLoading && ! items.length ) ),
		// Any later request: the rows on screen stay, dimmed, until the new ones arrive.
		isRefreshing: isLoading && hasLoaded,
		loadFailed,
		reload: () => setReloadKey( ( key ) => key + 1 ),
		items,
		total,
		channel,
		status,
		dateRange,
		search,
		currentPage,
		itemsPerPage,
		filtersApplied,
		payload,
		proCfg,
		setChannel: ( v ) => {
			setChannel( v );
			setCurrentPage( 1 );
		},
		setStatus: ( v ) => {
			setStatus( v );
			setCurrentPage( 1 );
		},
		setDateRange: ( v ) => {
			setDateRange( v );
			setCurrentPage( 1 );
		},
		setSearch,
		setCurrentPage,
		setItemsPerPage,
		clearFilters,
		upgradeActionButton,
	};
};

export default useActivityLogData;
