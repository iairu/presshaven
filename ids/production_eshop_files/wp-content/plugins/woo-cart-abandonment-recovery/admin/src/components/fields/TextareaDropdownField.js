import { useState, useEffect, useRef, useId, useCallback } from 'react';
import { useStateValue } from '@Store';
import useDebounceDispatch from '@Utils/debounceDispatch';
import { TextArea, Button, DropdownMenu, Input } from '@bsf/force-ui';
import {
	EllipsisVerticalIcon,
	MagnifyingGlassIcon,
} from '@heroicons/react/24/outline';
import { __, _n, sprintf } from '@wordpress/i18n';

import FieldWrapper from '@Components/common/FieldWrapper';
import { useFieldA11y, FieldError } from '@Components/common/fieldA11y';

// The blacklist dictionary has thousands of entries; rendering them all at once makes the menu slow.
const OPTIONS_PER_PAGE = 50;

const TextareaDropdownField = ( {
	title,
	description,
	name,
	value,
	handleChange,
	countLimit = null,
	options = [],
	search = false,
	autoSave = true,
	error,
} ) => {
	const [ state, dispatch ] = useStateValue();
	const settingsData = state.settingsData || {};
	const settingsValues = settingsData.values || {};

	// Use provided value when handleChange is provided (form mode)
	// Otherwise use global state value (auto-save mode)
	const currentValue =
		handleChange && ! autoSave
			? value ?? ''
			: settingsValues[ name ] ?? value ?? '';
	const [ textValue, setTextValue ] = useState( currentValue );
	const [ searchText, setSearchText ] = useState( '' );
	const [ visibleCount, setVisibleCount ] = useState( OPTIONS_PER_PAGE );
	const listRef = useRef( null );

	const debouncedUpdate = useDebounceDispatch(
		dispatch,
		name,
		undefined,
		1000,
		true
	);
	const inputRef = useRef( null );
	const optionsListId = useId();

	useEffect( () => {
		const newValue =
			handleChange && ! autoSave
				? value ?? ''
				: settingsValues[ name ] ?? value ?? '';
		setTextValue( newValue );
	}, [ settingsValues[ name ], value, handleChange, autoSave ] );

	function handleOnChange( val ) {
		setTextValue( val );

		// If handleChange is provided and autoSave is false, use form mode
		if ( handleChange && ! autoSave ) {
			handleChange( name, String( val ) );
			return;
		}

		// Otherwise use auto-save mode
		if ( autoSave ) {
			debouncedUpdate( String( val ) );
		}
	}

	const handleDropdownClick = ( optionValue ) => {
		const input = inputRef.current;

		if ( ! input ) {
			return;
		}

		const start = input.selectionStart;
		const end = input.selectionEnd;

		const newValue =
			textValue.substring( 0, start ) +
			optionValue +
			textValue.substring( end );
		setTextValue( newValue );

		// If handleChange is provided and autoSave is false, use form mode
		if ( handleChange && ! autoSave ) {
			handleChange( name, newValue );
			return;
		}

		// Otherwise use auto-save mode
		if ( autoSave ) {
			debouncedUpdate( newValue );
		}
	};

	// The menu mounts on open, so focusing here puts the cursor in the search box each time.
	const focusSearchOnOpen = useCallback( ( node ) => {
		node?.querySelector( 'input' )?.focus( { preventScroll: true } );
		setVisibleCount( OPTIONS_PER_PAGE );
	}, [] );

	const handleSearch = ( val ) => {
		setSearchText( val );
		setVisibleCount( OPTIONS_PER_PAGE );
		if ( listRef.current ) {
			listRef.current.scrollTop = 0;
		}
	};

	const showMoreOnScroll = ( event ) => {
		const list = event.currentTarget;
		const nearBottom =
			list.scrollTop + list.clientHeight >= list.scrollHeight - 48;
		if ( nearBottom && visibleCount < filteredOptions.length ) {
			setVisibleCount( ( count ) => count + OPTIONS_PER_PAGE );
		}
	};

	// Filter options based on search text
	const filteredOptions = searchText
		? options.filter( ( option ) =>
			option.value?.toLowerCase().includes( searchText.toLowerCase() )
		)
		: options;

	const a11y = useFieldA11y( { description, error } );
	const isOverLimit = countLimit !== null && textValue.length > countLimit;
	const counterId = `${ a11y.id }-count`;
	let counterColor = 'text-gray-500';
	if ( isOverLimit ) {
		counterColor = 'text-support-error';
	} else if ( countLimit !== null && textValue.length > countLimit * 0.9 ) {
		counterColor = 'text-badge-color-yellow';
	}

	return (
		<FieldWrapper
			title={ title }
			description={ description }
			fieldId={ a11y.id }
			type="block"
		>
			<div className="flex gap-2">
				<div className="grow">
					<TextArea
						{ ...a11y.controlProps }
						aria-describedby={
							[
								a11y.controlProps[ 'aria-describedby' ],
								countLimit !== null ? counterId : null,
							]
								.filter( Boolean )
								.join( ' ' ) || undefined
						}
						aria-invalid={ isOverLimit || !! error || undefined }
						className={ `w-full h-40 focus:[&>input]:ring-focus ${
							isOverLimit
								? 'border-support-error focus:border-support-error hover:border-support-error'
								: ''
						}` }
						type="text"
						size="md"
						name={ name }
						ref={ inputRef }
						value={ textValue }
						onChange={ handleOnChange }
					/>
					{ countLimit !== null && (
						<div
							className={ `flex ${
								isOverLimit ? 'justify-between' : 'justify-end'
							} mt-1` }
						>
							{ isOverLimit && (
								<span
									role="alert"
									className="text-support-error text-sm"
								>
									{ __(
										'Character limit exceeded',
										'woo-cart-abandonment-recovery'
									) }
								</span>
							) }
							<span
								id={ counterId }
								className={ `text-sm ${ counterColor }` }
							>
								{ textValue.length } / { countLimit }
							</span>
						</div>
					) }

					<FieldError id={ a11y.errorId }>{ error }</FieldError>
				</div>
				{ options.length > 0 && (
					<DropdownMenu placement="bottom-end">
						<DropdownMenu.Trigger>
							<Button
								aria-label={ __(
									'Insert placeholder',
									'woo-cart-abandonment-recovery'
								) }
								size="md"
								type="button"
								variant="outline"
								icon={
									<EllipsisVerticalIcon className="h-6 w-6 text-gray-500" />
								}
								iconPosition="left"
							/>
						</DropdownMenu.Trigger>
						<DropdownMenu.ContentWrapper className="z-50">
							<DropdownMenu.Content className="w-72">
								{ search && (
									<div
										className="pb-2"
										role="search"
										ref={ focusSearchOnOpen }
									>
										<Input
											type="search"
											size="sm"
											value={ searchText }
											onChange={ handleSearch }
											placeholder={ __(
												'Search options…',
												'woo-cart-abandonment-recovery'
											) }
											prefix={
												<MagnifyingGlassIcon className="h-5 w-5 text-gray-500" />
											}
											aria-label={ __(
												'Search options',
												'woo-cart-abandonment-recovery'
											) }
											aria-controls={ optionsListId }
											autoComplete="off"
											className="w-full [&_input]:min-h-0"
										/>
										<p className="sr-only" role="status">
											{ searchText &&
												sprintf(
													/* translators: %d: number of matching options */
													_n(
														'%d option found',
														'%d options found',
														filteredOptions.length,
														'woo-cart-abandonment-recovery'
													),
													filteredOptions.length
												) }
										</p>
									</div>
								) }
								<div
									id={ optionsListId }
									ref={ listRef }
									onScroll={ showMoreOnScroll }
									className="max-h-60 overflow-y-auto overflow-x-hidden"
								>
									<DropdownMenu.List>
										{ filteredOptions.length > 0 ? (
											filteredOptions
												.slice( 0, visibleCount )
												.map( ( option, index ) => (
													<DropdownMenu.Item
														key={ index }
														className="[overflow-wrap:anywhere]"
														onClick={ () =>
															handleDropdownClick( option.value )
														}
													>
														{ option.text }
													</DropdownMenu.Item>
												) )
										) : (
											<div className="text-center">
												{ __(
													'No options available',
													'woo-cart-abandonment-recovery'
												) }
											</div>
										) }
									</DropdownMenu.List>
								</div>
							</DropdownMenu.Content>
						</DropdownMenu.ContentWrapper>
					</DropdownMenu>
				) }
			</div>
		</FieldWrapper>
	);
};

export default TextareaDropdownField;
