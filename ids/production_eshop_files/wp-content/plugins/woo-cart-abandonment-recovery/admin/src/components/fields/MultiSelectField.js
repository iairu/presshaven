import { useState, useEffect } from 'react';
import { Select } from '@bsf/force-ui';
import { useStateValue } from '@Store';
import useDebounceDispatch from '@Utils/debounceDispatch';
import FieldWrapper from '@Components/common/FieldWrapper';
import { useFieldA11y } from '@Components/common/fieldA11y';
import { useProAccess } from '@Components/pro/useProAccess';

const MultiSelectField = ( {
	title,
	description,
	name,
	value,
	optionsArray,
	placeholder,
	handleChange,
	autoSave = true,
	disableStyle,
	isPro = false,
	proUpgradeMessage = '',
	size,
} ) => {
	const [ state, dispatch ] = useStateValue();
	const { shouldBlockProFeatures } = useProAccess();
	const isFeatureBlocked = shouldBlockProFeatures();
	const settingsData = state.settingsData || {};
	const settingsValues = settingsData.values || {};

	// Use provided value when handleChange is provided (form mode)
	// Otherwise use global state value (auto-save mode)
	const initialArray =
		( handleChange && ! autoSave
			? value
			: settingsValues[ name ] ?? value ) || [];

	const [ multiValue, setMultiValue ] = useState(
		optionsArray.filter( ( option ) => initialArray.includes( option.id ) )
	);
	const debouncedUpdate = useDebounceDispatch(
		dispatch,
		name,
		undefined,
		400,
		true
	);

	useEffect( () => {
		const newValue =
			( handleChange && ! autoSave
				? value
				: settingsValues[ name ] ?? value ) || [];
		setMultiValue(
			optionsArray.filter( ( option ) => newValue.includes( option.id ) )
		);
	}, [ settingsValues[ name ], value, handleChange, autoSave ] );

	function handleOnChange( selectedValues ) {
		setMultiValue( selectedValues );
		const selectedIds = selectedValues.map( ( option ) => option.id );
		// Update global state immediately
		if ( handleChange && ! autoSave ) {
			handleChange( name, selectedIds );
			return;
		}
		dispatch( {
			type: 'UPDATE_SETTINGS_DATA',
			payload: {
				option: name,
				value: selectedIds,
			},
		} );

		// Debounced update for database
		debouncedUpdate( selectedIds );
	}

	const a11y = useFieldA11y( { description } );

	return (
		<FieldWrapper
			title={ title }
			description={ description }
			fieldId={ a11y.id }
			disableStyle={ disableStyle }
			type="block"
			isPro={ isPro }
			proUpgradeMessage={ proUpgradeMessage }
			{ ...( size !== undefined && { size } ) }
		>
			<Select
				id={ a11y.id }
				multiple
				onChange={ handleOnChange }
				size="md"
				name={ name }
				value={ multiValue }
				disabled={ isPro && isFeatureBlocked }
			>
				<Select.Button
					className="[&_[role=button]]:-m-1.5 [&_[role=button]]:p-1.5"
					{ ...( a11y.controlProps[ 'aria-describedby' ] && {
						'aria-describedby': a11y.controlProps[ 'aria-describedby' ],
					} ) }
					placeholder={ placeholder }
					render={ ( selected ) => selected.name }
				/>
				<Select.Options>
					{ optionsArray.map( ( option ) => (
						<Select.Option key={ option.id } value={ option }>
							{ option.name }
						</Select.Option>
					) ) }
				</Select.Options>
			</Select>
		</FieldWrapper>
	);
};

export default MultiSelectField;
