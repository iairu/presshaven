import { useState, useEffect } from 'react';
import { Select, toast } from '@bsf/force-ui';
import { __ } from '@wordpress/i18n';
import { ArrowPathIcon } from '@heroicons/react/24/outline';

import { useStateValue, doApiFetch } from '@Store';
import useDebounceDispatch from '@Utils/debounceDispatch';
import FieldWrapper from '@Components/common/FieldWrapper';
import { useFieldA11y, FieldError } from '@Components/common/fieldA11y';
import { useProAccess } from '@Components/pro/useProAccess';
import AppTooltip from '@Components/common/AppTooltip';

const DynamicSelectField = ( {
	title,
	description,
	name,
	placeholder = '',
	value,
	action,
	actionNonce,
	handleChange,
	autoSave = true,
	disableStyle,
	isPro = false,
	proUpgradeMessage = '',
	error,
} ) => {
	const [ state, dispatch ] = useStateValue();
	const { shouldBlockProFeatures } = useProAccess();
	const [ optionsArray, setOptionsArray ] = useState( [] );
	const [ isLoading, setIsLoading ] = useState( false );
	const isFeatureBlocked = shouldBlockProFeatures();
	const settingsData = state.settingsData || {};
	const settingsValues = settingsData.values || {};

	// Use provided value when handleChange is provided (form mode)
	// Otherwise use global state value (auto-save mode)
	const currentValue =
		handleChange && ! autoSave ? value : settingsValues[ name ] ?? value;
	const [ selectValue, setSelectValue ] = useState(
		optionsArray.find( ( opt ) => opt.id === currentValue ) ||
			optionsArray[ 0 ]
	);
	const debouncedUpdate = useDebounceDispatch(
		dispatch,
		name,
		undefined,
		400,
		true
	);

	useEffect( () => {
		fetchOptions();
	}, [] );

	useEffect( () => {
		const newValue =
			handleChange && ! autoSave
				? value
				: settingsValues[ name ] ?? value;
		setSelectValue(
			optionsArray.find( ( opt ) => opt.id === newValue ) ||
				optionsArray[ 0 ]
		);
	}, [
		settingsValues[ name ],
		value,
		handleChange,
		autoSave,
		optionsArray,
	] );

	const fetchOptions = () => {
		const ajaxUrl = cart_abandonment_admin?.ajax_url;

		const formData = new FormData();
		formData.append( 'action', action );
		formData.append( 'security', cart_abandonment_admin?.[ actionNonce ] );

		setIsLoading( true );
		doApiFetch(
			ajaxUrl,
			formData,
			'POST',
			( response ) => {
				if ( response.success ) {
					setOptionsArray( response.data?.options );
				} else {
					toast.error(
						__( 'Error', 'woo-cart-abandonment-recovery' ),
						{
							description: response.data?.message || '',
						}
					);
				}
				setIsLoading( false );
			},
			( requestError ) => {
				toast.error( __( 'Error', 'woo-cart-abandonment-recovery' ), {
					description: requestError.data?.message || '',
				} );
				setIsLoading( false );
			},
			true
		);
	};

	function handleOnChange( val ) {
		setSelectValue( val );

		// If handleChange is provided and autoSave is false, use form mode
		if ( handleChange && ! autoSave ) {
			handleChange( name, val.id );
			return;
		}

		// Otherwise use auto-save mode
		// Update global state immediately
		dispatch( {
			type: 'UPDATE_SETTINGS_DATA',
			payload: {
				option: name,
				value: val.id,
			},
		} );

		// Debounced update for database (only in auto-save mode)
		if ( autoSave ) {
			debouncedUpdate( val.id );
		}
	}

	const a11y = useFieldA11y( { description, error } );

	return (
		<FieldWrapper
			title={ title }
			description={ description }
			fieldId={ a11y.id }
			type="block"
			disableStyle={ disableStyle }
			isPro={ isPro }
			proUpgradeMessage={ proUpgradeMessage }
		>
			<div className="flex gap-2 items-center">
				<div className="flex-1">
					<Select
						id={ a11y.id }
						onChange={ handleOnChange }
						size="md"
						name={ name }
						value={ selectValue?.name }
						disabled={ isPro && isFeatureBlocked }
					>
						<Select.Button
							{ ...( a11y.controlProps[ 'aria-describedby' ] && {
								'aria-describedby':
									a11y.controlProps[ 'aria-describedby' ],
							} ) }
							aria-invalid={ a11y.controlProps[ 'aria-invalid' ] }
							className="whitespace-nowrap"
							placeholder={
								placeholder ||
								__(
									'Select an option',
									'woo-cart-abandonment-recovery'
								)
							}
						/>
						<Select.Options>
							{ optionsArray.map( ( option ) => (
								<Select.Option
									key={ option.id }
									value={ option }
								>
									{ option.name }
								</Select.Option>
							) ) }
						</Select.Options>
					</Select>
					<FieldError id={ a11y.errorId }>{ error }</FieldError>
				</div>
				<AppTooltip
					content={ __(
						'Refresh Options',
						'woo-cart-abandonment-recovery'
					) }
					arrow
					placement="top"
				>
					<button
						type="button"
						className="m-0 inline-flex items-center justify-center rounded border-0 bg-transparent p-2 text-inherit cursor-pointer disabled:cursor-not-allowed disabled:opacity-60"
						onClick={ fetchOptions }
						disabled={ isLoading }
						aria-label={ __(
							'Refresh Options',
							'woo-cart-abandonment-recovery'
						) }
					>
						<ArrowPathIcon
							className={ `h-5 w-5 stroke-2 transform ${
								isLoading ? 'rotate-180' : ''
							} transition-transform duration-500` }
							aria-hidden="true"
						/>
					</button>
				</AppTooltip>
			</div>
		</FieldWrapper>
	);
};

export default DynamicSelectField;
