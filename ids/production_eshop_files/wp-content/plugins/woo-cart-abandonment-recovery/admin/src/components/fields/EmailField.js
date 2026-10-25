import { useState, useEffect } from 'react';
import { useStateValue } from '@Store';
import useDebounceDispatch from '@Utils/debounceDispatch';
import { Input } from '@bsf/force-ui';
import { __ } from '@wordpress/i18n';
import FieldWrapper from '@Components/common/FieldWrapper';
import { cn } from '@Utils/helper';
import { useFieldA11y, FieldError } from '@Components/common/fieldA11y';

const EmailField = ( {
	title,
	description,
	name,
	value,
	badge,
	handleChange,
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
	const [ email, setEmail ] = useState( currentValue );
	const [ invalid, setInvalid ] = useState( false );
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
		setEmail( newValue );
	}, [ settingsValues[ name ], value, handleChange, autoSave ] );

	const handleOnChange = ( val ) => {
		setEmail( val );
		setInvalid( false );
	};

	const handleBlur = () => {
		if ( ! /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test( email ) ) {
			setInvalid( true );
			return false;
		}
		if ( email !== currentValue ) {
			// If handleChange is provided and autoSave is false, use form mode
			if ( handleChange && ! autoSave ) {
				handleChange( name, email );
				return;
			}

			// Otherwise use auto-save mode
			if ( autoSave ) {
				debouncedUpdate( email );
			}
		}
	};

	let validationError = error;
	if ( invalid ) {
		validationError = __(
			'Enter a valid email address, like name@example.com.',
			'woo-cart-abandonment-recovery'
		);
	}
	const a11y = useFieldA11y( { description, error: validationError } );

	return (
		<FieldWrapper
			title={ title }
			description={ description }
			fieldId={ a11y.id }
			type="block"
		>
			<div>
				<Input
					className={ cn(
						badge ? 'w-24' : 'w-full',
						'focus:[&>input]:ring-focus',
						validationError && 'border-support-error'
					) }
					{ ...a11y.controlProps }
					type="email"
					size="md"
					name={ name }
					value={ email }
					onChange={ handleOnChange }
					onBlur={ handleBlur }
				/>
				<FieldError id={ a11y.errorId }>{ validationError }</FieldError>
			</div>
		</FieldWrapper>
	);
};

export default EmailField;
