import { useState, useEffect } from 'react';
import { useStateValue } from '@Store';
import useDebounceDispatch from '@Utils/debounceDispatch';
import { TextArea } from '@bsf/force-ui';
import FieldWrapper from '@Components/common/FieldWrapper';
import { useFieldA11y } from '@Components/common/fieldA11y';
import { useProAccess } from '@Components/pro/useProAccess';

const TextAreaField = ( {
	title,
	description,
	name,
	value,
	onSaved,
	placeholder = '',
	isPro = false,
	proUpgradeMessage = '',
} ) => {
	const [ state, dispatch ] = useStateValue();
	const { shouldBlockProFeatures } = useProAccess();
	const isFeatureBlocked = shouldBlockProFeatures();
	const settingsData = state.settingsData || {};
	const settingsValues = settingsData.values || {};
	const initial = settingsValues[ name ] ?? value;
	const [ textValue, setTextValue ] = useState( initial );
	const debouncedUpdate = useDebounceDispatch(
		dispatch,
		name,
		onSaved,
		400,
		true
	);

	useEffect( () => {
		setTextValue( initial );
	}, [ initial ] );

	function handleOnChange( val ) {
		setTextValue( val );
		debouncedUpdate( String( val ) );
	}

	const a11y = useFieldA11y( { description } );

	return (
		<FieldWrapper
			title={ title }
			description={ description }
			fieldId={ a11y.id }
			type="block"
			isPro={ isPro }
			proUpgradeMessage={ proUpgradeMessage }
		>
			<TextArea
				{ ...a11y.controlProps }
				className="w-full focus:[&>input]:ring-focus"
				type="text"
				size="md"
				name={ name }
				value={ textValue }
				placeholder={ placeholder }
				onChange={ handleOnChange }
				disabled={ isPro && isFeatureBlocked }
			/>
		</FieldWrapper>
	);
};

export default TextAreaField;
