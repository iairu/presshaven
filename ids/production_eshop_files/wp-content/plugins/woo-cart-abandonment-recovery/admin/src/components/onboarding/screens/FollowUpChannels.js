import { __ } from '@wordpress/i18n';
import ErrorBanner from '@Components/onboarding/ErrorBanner';
import Header from '@Components/onboarding/Header';
import NavigationButtons from '@Components/onboarding/NavigationButtons';
import RenderFields from '@Components/RenderFields';
import {
	useOnboardingFieldsStep,
	useOnboardingNavigation,
} from '../hooks';

const FollowUpChannels = () => {
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
	} = useOnboardingFieldsStep( 'follow-up-channels' );
	const { navigateToNextRoute } = useOnboardingNavigation();

	return (
		<>
			<Header
				heading={ __(
					'Select Your Follow Up Sequence Channels',
					'woo-cart-abandonment-recovery'
				) }
				subHeading={ __(
					'Choose how you reach shoppers who leave items in their cart.',
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

export default FollowUpChannels;
