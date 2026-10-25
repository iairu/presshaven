import { useState, useEffect, useCallback, useRef } from 'react';
import { toast } from '@bsf/force-ui';
import { __ } from '@wordpress/i18n';

import { doApiFetch } from '@Store';

const CLOSED_DELETE_MODAL = { isOpen: false, type: null, id: null, name: '' };

// How long a freshly duplicated row stays highlighted.
const HIGHLIGHT_DURATION_MS = 3000;

const getAdminVars = () => window.cart_abandonment_admin || {};

const getAjaxUrl = () => getAdminVars().ajax_url || window.ajaxurl;

/**
 * Build a FormData for an admin-ajax action with its nonce attached.
 *
 * @param {string} action   AJAX action name.
 * @param {string} nonceKey Key of the nonce in cart_abandonment_admin.
 * @return {FormData} Form data with action and security set.
 */
const buildForm = ( action, nonceKey ) => {
	const formData = new window.FormData();
	formData.append( 'action', action );
	formData.append( 'security', getAdminVars()[ nonceKey ] );
	return formData;
};

const errorToast = ( title, error ) =>
	toast.error( title, { description: error?.message || '' } );

/**
 * Shared state and handlers for a follow-up template list (email, SMS, WhatsApp).
 *
 * Every request routes through `doApiFetch`, which rethrows after calling the error
 * callback, so each call ends in `.catch()`: the UI has already handled the failure.
 *
 * @param {Object}  config
 * @param {string}  config.fetchPath   REST path for the list request.
 * @param {string}  config.fetchMethod HTTP method for the list request.
 * @param {boolean} config.skipFetch   Skip loading (feature blocked).
 * @param {Object}  config.actions     admin-ajax `delete`, `status`, `clone`, optional `restore`: { action, nonce }.
 * @return {Object} List state and handlers.
 */
const useTemplatesList = ( {
	fetchPath,
	fetchMethod = 'GET',
	skipFetch = false,
	actions,
} ) => {
	const [ templates, setTemplates ] = useState( [] );
	const [ isLoading, setIsLoading ] = useState( true );
	const [ loadError, setLoadError ] = useState( false );
	const [ searchText, setSearchText ] = useState( '' );
	const [ selected, setSelected ] = useState( [] );
	const [ deleteModal, setDeleteModal ] = useState( CLOSED_DELETE_MODAL );
	const [ isDeleting, setIsDeleting ] = useState( false );
	const [ isRestoreOpen, setIsRestoreOpen ] = useState( false );
	const [ isRestoring, setIsRestoring ] = useState( false );
	const [ duplicatingId, setDuplicatingId ] = useState( null );
	const [ highlightedId, setHighlightedId ] = useState( null );
	const highlightTimer = useRef( null );

	useEffect( () => () => clearTimeout( highlightTimer.current ), [] );

	// A duplicate lands at the end of the list, possibly off-screen: bring it into view.
	useEffect( () => {
		if ( highlightedId === null ) {
			return;
		}
		const row = document.querySelector(
			`[data-template-id="${ highlightedId }"]`
		);
		const prefersReducedMotion = window.matchMedia(
			'(prefers-reduced-motion: reduce)'
		).matches;
		row?.scrollIntoView( {
			block: 'nearest',
			behavior: prefersReducedMotion ? 'auto' : 'smooth',
		} );
	}, [ highlightedId ] );

	const highlightTemplate = ( id ) => {
		clearTimeout( highlightTimer.current );
		setHighlightedId( id );
		highlightTimer.current = setTimeout(
			() => setHighlightedId( null ),
			HIGHLIGHT_DURATION_MS
		);
	};

	const isHighlighted = ( id ) =>
		highlightedId !== null && String( id ) === String( highlightedId );

	const loadTemplates = useCallback( () => {
		setIsLoading( true );
		setLoadError( false );

		return doApiFetch(
			fetchPath,
			{},
			fetchMethod,
			( response ) => {
				setTemplates( Array.isArray( response ) ? response : [] );
				setIsLoading( false );
			},
			() => {
				setLoadError( true );
				setIsLoading( false );
			}
		).catch( () => {} );
	}, [ fetchPath, fetchMethod ] );

	useEffect( () => {
		if ( skipFetch ) {
			setIsLoading( false );
			return;
		}
		loadTemplates();
	}, [] ); // eslint-disable-line react-hooks/exhaustive-deps

	const matchesSearch = ( item, text ) =>
		( item.template_name || '' ).toLowerCase().includes( text.toLowerCase() );

	const filteredData = templates.filter( ( item ) =>
		matchesSearch( item, searchText )
	);

	// A selection must never include rows the merchant can't see.
	const handleSearch = ( value ) => {
		setSearchText( value );
		setSelected( ( prev ) =>
			prev.filter( ( id ) =>
				templates.some(
					( item ) => item.id === id && matchesSearch( item, value )
				)
			)
		);
	};

	const handleCheckboxChange = ( checked, value ) => {
		setSelected( ( prev ) =>
			checked
				? [ ...prev, value.id ]
				: prev.filter( ( id ) => id !== value.id )
		);
	};

	const toggleSelectAll = ( checked ) => {
		setSelected( checked ? filteredData.map( ( item ) => item.id ) : [] );
	};

	const clearSelection = () => setSelected( [] );

	const requestBulkDelete = () => {
		if ( ! selected.length ) {
			return;
		}
		setDeleteModal( { isOpen: true, type: 'bulk', id: null } );
	};

	const requestDelete = ( item ) =>
		setDeleteModal( {
			isOpen: true,
			type: 'single',
			id: item.id,
			name: item.template_name,
		} );

	// Keep type and name so the dialog doesn't change its text while it animates out.
	const closeDeleteModal = () =>
		setDeleteModal( ( prev ) => ( { ...prev, isOpen: false } ) );

	const confirmDelete = () => {
		const isBulk = deleteModal.type === 'bulk';
		const ids = isBulk ? selected : [ deleteModal.id ];
		let deletedMessage = __(
			'Template deleted',
			'woo-cart-abandonment-recovery'
		);
		if ( isBulk ) {
			deletedMessage = __(
				'Template(s) deleted',
				'woo-cart-abandonment-recovery'
			);
		}

		const formData = buildForm(
			actions.delete.action,
			actions.delete.nonce
		);
		ids.forEach( ( id ) => formData.append( 'ids[]', id ) );

		setIsDeleting( true );

		return doApiFetch(
			getAjaxUrl(),
			formData,
			'POST',
			( response ) => {
				if ( response.success ) {
					// Ensure both sides are numbers for comparison.
					const deletedIds = ( response.data?.ids || ids ).map(
						Number
					);
					setTemplates( ( prev ) =>
						prev.filter(
							( tpl ) => ! deletedIds.includes( Number( tpl.id ) )
						)
					);
					setSelected( ( prev ) =>
						prev.filter(
							( id ) => ! deletedIds.includes( Number( id ) )
						)
					);
					toast.success( deletedMessage );
				} else {
					toast.error(
						__( 'Delete failed', 'woo-cart-abandonment-recovery' ),
						{ description: response.data?.message || '' }
					);
				}
			},
			( error ) =>
				errorToast(
					__( 'Delete failed', 'woo-cart-abandonment-recovery' ),
					error
				),
			true
		)
			.catch( () => {} )
			.finally( () => {
				setIsDeleting( false );
				closeDeleteModal();
			} );
	};

	const setActive = ( id, isActive ) =>
		setTemplates( ( prev ) =>
			prev.map( ( item ) =>
				item.id === id
					? { ...item, is_activated: isActive ? 'on' : '' }
					: item
			)
		);

	// Optimistic: flip immediately, then put the switch back if the server says no.
	const toggleStatus = ( id, value ) => {
		const isOn = value === true;
		setActive( id, isOn );

		const formData = buildForm( actions.status.action, actions.status.nonce );
		formData.append( 'id', id );
		// Send 1 for enabled, 0 for disabled.
		formData.append( 'state', isOn ? 1 : 0 );

		const failToast = ( message ) => {
			setActive( id, ! isOn );
			toast.error( __( 'Error!', 'woo-cart-abandonment-recovery' ), {
				description:
					message ||
					__(
						'Failed to update status',
						'woo-cart-abandonment-recovery'
					),
			} );
		};

		return doApiFetch(
			getAjaxUrl(),
			formData,
			'POST',
			( response ) => {
				if ( response.success ) {
					setActive(
						id,
						response.data.is_active === '1' ||
							response.data.is_active === 1
					);
					toast.success(
						__( 'Success!', 'woo-cart-abandonment-recovery' ),
						{
							description: __(
								'Template status updated successfully',
								'woo-cart-abandonment-recovery'
							),
						}
					);
				} else {
					failToast( response.data?.message );
				}
			},
			( error ) => failToast( error?.message ),
			true
		).catch( () => {} );
	};

	const duplicate = ( item ) => {
		if ( duplicatingId !== null ) {
			return Promise.resolve();
		}
		setDuplicatingId( item.id );

		const formData = buildForm( actions.clone.action, actions.clone.nonce );
		formData.append( 'id', item.id );

		return doApiFetch(
			getAjaxUrl(),
			formData,
			'POST',
			( response ) => {
				if ( response.success ) {
					setTemplates( ( prev ) => [
						...prev,
						response.data.template,
					] );
					highlightTemplate( response.data.template.id );
					toast.success(
						__(
							'Template cloned successfully',
							'woo-cart-abandonment-recovery'
						)
					);
				} else {
					toast.error(
						__( 'Clone failed', 'woo-cart-abandonment-recovery' ),
						{ description: response.data?.message || '' }
					);
				}
			},
			( error ) =>
				errorToast(
					__( 'Clone failed', 'woo-cart-abandonment-recovery' ),
					error
				),
			true
		)
			.catch( () => {} )
			.finally( () => setDuplicatingId( null ) );
	};

	const requestRestore = () => setIsRestoreOpen( true );

	const closeRestore = () => setIsRestoreOpen( false );

	const confirmRestore = () => {
		setIsRestoring( true );

		return doApiFetch(
			getAjaxUrl(),
			buildForm( actions.restore.action, actions.restore.nonce ),
			'POST',
			( response ) => {
				if ( response.success ) {
					setTemplates( response.data.templates || [] );
					setSelected( [] );
					toast.success(
						__(
							'Default templates restored',
							'woo-cart-abandonment-recovery'
						)
					);
				} else {
					toast.error(
						__( 'Restore failed', 'woo-cart-abandonment-recovery' ),
						{ description: response.data?.message || '' }
					);
				}
			},
			( error ) =>
				errorToast(
					__( 'Restore failed', 'woo-cart-abandonment-recovery' ),
					error
				),
			true
		)
			.catch( () => {} )
			.finally( () => {
				setIsRestoring( false );
				setIsRestoreOpen( false );
			} );
	};

	/**
	 * Add or replace a template saved from the drawer.
	 *
	 * @param {Object} saved Template returned by the server.
	 * @return {boolean} True when the template is new.
	 */
	const upsertTemplate = ( saved ) => {
		const isCreate = ! templates.some( ( item ) => item.id === saved.id );

		setTemplates( ( prev ) =>
			isCreate
				? [ ...prev, saved ]
				: prev.map( ( item ) => ( item.id === saved.id ? saved : item ) )
		);

		return isCreate;
	};

	return {
		templates,
		filteredData,
		isLoading,
		loadError,
		retry: loadTemplates,
		searchText,
		handleSearch,
		selected,
		handleCheckboxChange,
		toggleSelectAll,
		clearSelection,
		deleteModal,
		isDeleting,
		requestDelete,
		requestBulkDelete,
		closeDeleteModal,
		confirmDelete,
		toggleStatus,
		duplicatingId,
		duplicate,
		isHighlighted,
		isRestoreOpen,
		isRestoring,
		requestRestore,
		closeRestore,
		confirmRestore,
		upsertTemplate,
	};
};

export default useTemplatesList;
