import { useState, useEffect } from 'react';
import { useStateValue } from '@Store';
import useDebounceDispatch from '@Utils/debounceDispatch';
import { Input } from '@bsf/force-ui';
import FieldWrapper from '@Components/common/FieldWrapper';
import { cn } from '@Utils/helper';
import { useFieldA11y, FieldError } from '@Components/common/fieldA11y';
import { useProAccess } from '@Components/pro/useProAccess';

const PasswordField = ( {
	title,
	description,
	name,
	value,
	badge,
	handleChange,
	autoSave = true,
	error,
	isPro = false,
	proUpgradeMessage = '',
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
			<div>
				<Input
					className={ cn(
						badge ? 'w-24' : 'w-full',
						'focus:[&>input]:ring-focus',
						error && 'border-support-error'
					) }
					{ ...a11y.controlProps }
					autoComplete="new-password"
					type="password"
					size="md"
					name={ name }
					value={ textValue }
					onChange={ handleOnChange }
					disabled={ isPro && isFeatureBlocked }
				/>
				<FieldError id={ a11y.errorId }>{ error }</FieldError>
			</div>
		</FieldWrapper>
	);
};

export default PasswordField;
