import { useState, useEffect } from 'react';
import { useStateValue } from '@Store';
import useDebounceDispatch from '@Utils/debounceDispatch';
import { Input } from '@bsf/force-ui';
import { __, sprintf } from '@wordpress/i18n';
import FieldWrapper from '@Components/common/FieldWrapper';
import { FieldError, useFieldA11y } from '@Components/common/fieldA11y';
import { useProAccess } from '@Components/pro/useProAccess';
import { cn } from '@Utils/helper';

const NumberField = ( {
	title,
	description,
	name,
	value,
	badge,
	min,
	max,
	after = '',
	suffix = '',
	handleChange,
	autoSave = true,
	disableStyle,
	className = '',
	isPro = false,
	proUpgradeMessage = '',
	size,
	ariaLabel,
	error,
	onValidityChange,
} ) => {
	const [ state, dispatch ] = useStateValue();
	const { shouldBlockProFeatures } = useProAccess();
	const isFeatureBlocked = shouldBlockProFeatures();
	const settingsData = state.settingsData || {};
	const settingsValues = settingsData.values || {};

	// Use provided value when handleChange is provided (form mode)
	// Otherwise use global state value (auto-save mode)
	const isFormMode = !! handleChange && ! autoSave;
	const currentValue = isFormMode
		? value ?? ''
		: settingsValues[ name ] ?? value ?? '';
	const [ numberValue, setNumberValue ] = useState( currentValue );
	const [ rangeError, setRangeError ] = useState( '' );
	const debouncedUpdate = useDebounceDispatch(
		dispatch,
		name,
		undefined,
		400,
		true
	);

	// Keyed on the mode, not on `handleChange` itself: a parent that rebuilds that
	// function on every render would otherwise put the saved value back over what is
	// being typed each time it re-renders.
	useEffect( () => {
		const newValue = isFormMode
			? value ?? ''
			: settingsValues[ name ] ?? value ?? '';
		setNumberValue( newValue );
		setRangeError( '' );
	}, [ settingsValues[ name ], value, isFormMode ] );

	// Only a number that meets `min` is ever passed on, so a smaller or blank one never
	// reaches the form or the saved option.
	const hasMax = max !== undefined && max !== null && max !== '';
	const isAcceptable = ( val ) =>
		/^\d+$/.test( String( val ) ) &&
		parseInt( val ) >= parseInt( min || 0 ) &&
		( ! hasMax || parseInt( val ) <= parseInt( max ) );

	const describeRange = () => {
		if ( hasMax ) {
			return sprintf(
				// translators: 1: lowest allowed number, 2: highest allowed number.
				__(
					'Enter a whole number from %1$s to %2$s.',
					'woo-cart-abandonment-recovery'
				),
				parseInt( min || 0 ),
				parseInt( max )
			);
		}
		return sprintf(
			// translators: %s: lowest allowed number.
			__(
				'Enter a whole number of %s or more.',
				'woo-cart-abandonment-recovery'
			),
			parseInt( min || 0 )
		);
	};

	// A form that wants to refuse the step while a value is too small passes
	// `onValidityChange`; the rejected value then stays on screen with its message
	// instead of being swapped back on blur.
	const reportsValidity = 'function' === typeof onValidityChange;

	function handleOnChange( val ) {
		setNumberValue( val );
		setRangeError( isAcceptable( val ) ? '' : describeRange() );

		// If handleChange is provided and autoSave is false, use form mode
		if ( handleChange && ! autoSave ) {
			if ( isAcceptable( val ) ) {
				handleChange( name, String( val ) );
				if ( reportsValidity ) {
					onValidityChange( name, '' );
				}
			} else if ( reportsValidity ) {
				onValidityChange( name, describeRange() );
			}
			return;
		}

		// Otherwise use auto-save mode
		if ( autoSave ) {
			if ( isAcceptable( val ) ) {
				debouncedUpdate( String( val ) );
			}
		}
	}

	// Typing through a rejected value (clearing the field to type a new number) is fine,
	// but leaving it there would show a number that isn't the one being saved: put the last
	// accepted value back.
	function handleBlur() {
		if ( ! reportsValidity && ! isAcceptable( numberValue ) ) {
			setNumberValue( currentValue );
			setRangeError( '' );
		}
	}

	const shownError = error || rangeError;
	const a11y = useFieldA11y( { description, error: shownError } );

	return (
		<FieldWrapper
			title={ title }
			description={ description }
			fieldId={ a11y.id }
			type="inline"
			disableStyle={ disableStyle }
			isPro={ isPro }
			proUpgradeMessage={ proUpgradeMessage }
			{ ...( size !== undefined && { size } ) }
		>
			<div className="flex flex-col justify-center sm:items-end">
				<div className="flex sm:justify-end items-center gap-2">
					<Input
						// The native up/down spinner sits flush on the right, same place as
						// `suffix` — hidden on every size so a plain number field and a
						// suffixed one look the same, instead of only fixing the overlap here.
						// Force UI only reserves 36px (`pr-9`) for the suffix, barely wider
						// than "minutes" itself, so digits crowd that boundary as the value
						// grows; widening it to 64px is real padding on the input, a hard
						// box-model edge digits can't render past, so it holds at any length.
						className={ cn(
							className || ( badge ? 'w-24' : 'w-20 rounded-r-md' ),
							'focus:[&>input]:ring-focus [&>input]:[appearance:textfield] [&>input::-webkit-outer-spin-button]:appearance-none [&>input::-webkit-inner-spin-button]:appearance-none [&>input::-webkit-outer-spin-button]:m-0 [&>input::-webkit-inner-spin-button]:m-0',
							suffix && '[&>input]:pr-16'
						) }
						suffix={
							suffix && (
								<span className="text-badge-color-gray p-0.5 text-center text-xs font-medium">
									{ suffix }
								</span>
							)
						}
						{ ...a11y.controlProps }
						// Fields nested in a grouped control (see TimeField) have no title of
						// their own, so the group names them.
						{ ...( ariaLabel && { 'aria-label': ariaLabel } ) }
						type="number"
						size="md"
						name={ name }
						value={ numberValue }
						onChange={ handleOnChange }
						onBlur={ handleBlur }
						// Editing a number field almost always means replacing it, not
						// inserting into it — without this, clicking in (which does not
						// select existing text the way it would in a normal text field)
						// and typing a new value interleaves the new digits with whatever
						// was already there instead of replacing it.
						onFocus={ ( event ) => event.target.select() }
						min={ min || 0 }
						{ ...( hasMax && { max } ) }
						disabled={ isPro && isFeatureBlocked }
					/>
					{ after && (
						<span className="text-badge-color-gray p-0.5 text-center text-xs font-medium">
							{ after }
						</span>
					) }
				</div>
				{ /* Beside the label, a short message keeps one line and a long one wraps at 256px
				instead of pushing the label aside or running off the card. */ }
				<FieldError
					id={ a11y.errorId }
					className="sm:w-max sm:max-w-64 sm:text-right"
				>
					{ shownError }
				</FieldError>
			</div>
		</FieldWrapper>
	);
};

export default NumberField;
