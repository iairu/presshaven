import React, { useState, useEffect } from 'react';
import { __, sprintf } from '@wordpress/i18n';
import { Select, Button } from '@bsf/force-ui';

import FieldWrapper from '@Components/common/FieldWrapper';
import ConfirmDialog from '@Components/common/ConfirmDialog';

const RollbackField = ( {
	title,
	description,
	name,
	options = [],
	disableStyle,
} ) => {
	const [ previousVersion, setPreviousVersion ] = useState( options[ 0 ] );
	const [ isPopupOpen, setIsPopupOpen ] = useState( false );
	const [ pluginName, setPluginName ] = useState( '' );
	const [ isRollingBack, setIsRollingBack ] = useState( false );

	// Coming back via the browser's back button restores this page from cache, mid-spinner.
	useEffect( () => {
		const reset = ( event ) => event.persisted && setIsRollingBack( false );
		window.addEventListener( 'pageshow', reset );
		return () => window.removeEventListener( 'pageshow', reset );
	}, [] );

	// The version list comes from wordpress.org and can arrive empty.
	if ( ! previousVersion ) {
		return (
			<FieldWrapper
				title={ title }
				description={ description }
				type="inline"
				disableStyle={ disableStyle }
			>
				<p className="m-0 text-sm text-gray-600">
					{ __(
						'Previous versions could not be loaded. Reload the page to try again.',
						'woo-cart-abandonment-recovery'
					) }
				</p>
			</FieldWrapper>
		);
	}

	const rollbackButtonClickHandler = () => {
		setPluginName( 'Cart Abandonment Recovery' );
		setIsPopupOpen( true );
	};

	const onConfirm = () => {
		const rollbackUrl = cart_abandonment_admin.rollback_url.replace(
			'VERSION',
			previousVersion.name
		);
		// Keep the dialog open, spinning, until the browser leaves the page.
		setIsRollingBack( true );
		window.location.href = rollbackUrl;
	};

	return (
		<>
			<FieldWrapper
				title={ title }
				description={ description }
				type="inline"
				disableStyle={ disableStyle }
			>
				<div className="flex flex-wrap gap-3 items-center">
					<Select
						onChange={ ( val ) => {
							setPreviousVersion( val );
						} }
						size="md"
						name={ name }
						value={ previousVersion.name }
					>
						<Select.Button
							aria-label={ __(
								'Version to roll back to',
								'woo-cart-abandonment-recovery'
							) }
							placeholder={ __(
								'Select an option',
								'woo-cart-abandonment-recovery'
							) }
						/>
						<Select.Options>
							{ options.map( ( option ) => (
								<Select.Option
									key={ option.id }
									value={ option }
								>
									{ option.name }
								</Select.Option>
							) ) }
						</Select.Options>
					</Select>
					<Button
						iconPosition="left"
						size="md"
						tag="button"
						type="button"
						variant="primary"
						disabled={ isPopupOpen }
						onClick={ rollbackButtonClickHandler }
					>
						{ __( 'Rollback', 'woo-cart-abandonment-recovery' ) }
					</Button>
				</div>
			</FieldWrapper>
			<ConfirmDialog
				open={ isPopupOpen }
				setOpen={ () => setIsPopupOpen( false ) }
				onConfirm={ onConfirm }
				title={ __(
					'Rollback to Previous Version',
					'woo-cart-abandonment-recovery'
				) }
				description={ sprintf(
					// translators: %1$s is the selected product of CartFlows, %2$s is the selected version of CartFlows.
					__(
						'Are you sure you want to rollback to %1$s v%2$s?',
						'woo-cart-abandonment-recovery'
					),
					pluginName,
					previousVersion.name
				) }
				confirmLabel={ __( 'Confirm', 'woo-cart-abandonment-recovery' ) }
				isConfirming={ isRollingBack }
			/>
		</>
	);
};

export default RollbackField;

