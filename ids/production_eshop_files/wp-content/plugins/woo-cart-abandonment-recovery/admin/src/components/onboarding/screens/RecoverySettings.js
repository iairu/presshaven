import { __ } from '@wordpress/i18n';
import ErrorBanner from '@Components/onboarding/ErrorBanner';
import Header from '@Components/onboarding/Header';
import NavigationButtons from '@Components/onboarding/NavigationButtons';
import RenderFields from '@Components/RenderFields';
import {
	useOnboardingFieldsStep,
	useOnboardingNavigation,
} from '../hooks';

const RecoverySettings = () => {
	const {
		fieldSettings,
		settingsValues,
		conditions,
		valueFor,
		handleChange,
		saveAndAdvance,
		isSaving,
		saveError,
		fieldErrors,
		handleValidity,
	} = useOnboardingFieldsStep( 'recovery-settings' );
	const { navigateToNextRoute } = useOnboardingNavigation();

	return (
		<>
			<Header
				heading={ __(
					'Configure Recovery Settings',
					'woo-cart-abandonment-recovery'
				) }
				subHeading={ __(
					'Decide when a cart counts as abandoned, when it’s lost for good, and which user roles to leave out of tracking.',
					'woo-cart-abandonment-recovery'
				) }
			/>

			{ saveError && (
				<ErrorBanner
					title={ __(
						'Could not save your changes',
						'woo-cart-abandonment-recovery'
					) }
					content={ saveError }
				/>
			) }

			{ /* FieldWrapper always gives its first row a `pt-6` (see FieldWrapper.js: the
			     `first:` variant lands on that row's own first child, not on this list, so
			     it fires unconditionally). Stacked under the card's own `gap-6` that doubles
			     the gap under the header to 48px; this cancels the card's half so only the
			     field's own padding shows. */ }
			<div className="-mt-6">
				{ fieldSettings.fields &&
					Object.keys( fieldSettings.fields ).map( ( field ) => {
						const data = fieldSettings.fields[ field ];
						const isActive = conditions.isActiveControl(
							data,
							settingsValues
						);

						return (
							<RenderFields
								key={ data?.name || field }
								data={ data }
								value={ valueFor( data ) }
								isActive={ isActive }
								handleChange={ handleChange }
								errors={ fieldErrors }
								onValidityChange={ handleValidity }
								autoSave={ false }
								size="sm"
							/>
						);
					} ) }
			</div>

			<NavigationButtons
				nextLoading={ isSaving }
				nextLabel={
					isSaving
						? __( 'Saving…', 'woo-cart-abandonment-recovery' )
						: undefined
				}
				onNext={ () => saveAndAdvance( navigateToNextRoute ) }
			/>
		</>
	);
};

export default RecoverySettings;
