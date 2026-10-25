import { useState, useEffect, useRef } from 'react';
import { useStateValue } from '@Store';
import useDebounceDispatch from '@Utils/debounceDispatch';
import { Input, Button, DropdownMenu } from '@bsf/force-ui';
import { EllipsisVerticalIcon } from '@heroicons/react/24/outline';
import FieldWrapper from '@Components/common/FieldWrapper';
import { __ } from '@wordpress/i18n';
import { useFieldA11y, FieldError } from '@Components/common/fieldA11y';
import { useProAccess } from '@Components/pro/useProAccess';

const SubjectField = ( {
	title,
	description,
	name,
	value,
	badge,
	placeholder,
	handleChange,
	options = [],
	autoSave = true,
	error,
	isPro = false,
	proUpgradeMessage,
} ) => {
	const [ state, dispatch ] = useStateValue();
	const { shouldBlockProFeatures } = useProAccess();
	const isFeatureBlocked = shouldBlockProFeatures();
	const settingsData = state.settingsData || {};
	const settingsValues = settingsData.values || {};

	// Use provided value when handleChange is provided (form mode)
	// Otherwise use global state value (auto-save mode)
	const currentValue =
		handleChange && ! autoSave
			? value ?? ''
			: settingsValues[ name ] ?? value ?? '';
	const [ textValue, setTextValue ] = useState( currentValue );
	const debouncedUpdate = useDebounceDispatch(
		dispatch,
		name,
		undefined,
		400,
		true
	);
	const inputRef = useRef( null );

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
			value.substring( 0, start ) + optionValue + value.substring( end );
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

	const a11y = useFieldA11y( { description, error } );

	return (
		<FieldWrapper
			title={ title }
			description={ description }
			fieldId={ a11y.id }
			type="block"
			isPro={ isPro }
			proUpgradeMessage={ proUpgradeMessage }
		>
			<div className="flex gap-2">
				<div className="grow">
					<Input
						className={ `${
							badge ? 'w-24 ' : 'w-full'
						} focus:[&>input]:ring-focus` }
						{ ...a11y.controlProps }
						type="text"
						size="md"
						placeholder={ placeholder }
						name={ name }
						ref={ inputRef }
						value={ textValue }
						onChange={ handleOnChange }
						disabled={ isPro && isFeatureBlocked }
					/>
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
							<DropdownMenu.Content>
								<DropdownMenu.List>
									{ options.map( ( option, index ) => (
										<DropdownMenu.Item
											key={ index }
											onClick={ () =>
												handleDropdownClick(
													option.value
												)
											}
										>
											{ option.text }
										</DropdownMenu.Item>
									) ) }
								</DropdownMenu.List>
							</DropdownMenu.Content>
						</DropdownMenu.ContentWrapper>
					</DropdownMenu>
				) }
			</div>
		</FieldWrapper>
	);
};

export default SubjectField;
