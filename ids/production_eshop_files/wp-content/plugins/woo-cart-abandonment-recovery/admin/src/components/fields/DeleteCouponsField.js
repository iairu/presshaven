import { useState } from 'react';
import { Button, toast } from '@bsf/force-ui';
import { __ } from '@wordpress/i18n';

import ConfirmDialog from '@Components/common/ConfirmDialog';
import FieldWrapper from '@Components/common/FieldWrapper';
import { doApiFetch } from '@Store';

const DeleteCouponsField = ( { title, description } ) => {
	const [ isDeleting, setIsDeleting ] = useState( false );
	const [ confirming, setConfirming ] = useState( false );

	const finish = () => {
		setIsDeleting( false );
		setConfirming( false );
	};

	const handleTrigger = () => {
		const nonce = window.wcf_ca_localized_vars?._delete_coupon_nonce;

		if ( ! nonce ) {
			toast.error(
				__( 'Delete failed', 'woo-cart-abandonment-recovery' ),
				{
					description: __(
						'This page is out of date. Reload it and try again.',
						'woo-cart-abandonment-recovery'
					),
				}
			);
			setConfirming( false );
			return;
		}

		setIsDeleting( true );
		const ajaxUrl = cart_abandonment_admin?.ajax_url;

		const formData = new window.FormData();
		formData.append( 'action', 'wcf_ca_delete_garbage_coupons' );
		formData.append( 'security', nonce );

		doApiFetch(
			ajaxUrl,
			formData,
			'POST',
			( response ) => {
				if ( response.success ) {
					toast.success(
						__(
							'Coupons deleted',
							'woo-cart-abandonment-recovery'
						),
						{
							description: response.data || '',
						}
					);
				} else {
					toast.error(
						__( 'Delete failed', 'woo-cart-abandonment-recovery' ),
						{
							description: response.data || '',
						}
					);
				}
				finish();
			},
			( error ) => {
				toast.error(
					__( 'Delete failed', 'woo-cart-abandonment-recovery' ),
					{
						description: error.data || '',
					}
				);
				finish();
			},
			true,
			false
		).catch( () => {
			// doApiFetch has already reported the failure through onError.
		} );
	};

	return (
		<FieldWrapper title={ title } description={ description } type="inline">
			<div className="my-auto">
				<Button
					size="md"
					tag="button"
					type="button"
					variant="outline"
					destructive
					onClick={ () => setConfirming( true ) }
					disabled={ isDeleting }
				>
					{ __( 'Delete coupons', 'woo-cart-abandonment-recovery' ) }
				</Button>
			</div>
			<ConfirmDialog
				open={ confirming }
				setOpen={ setConfirming }
				title={ __(
					'Delete used and expired coupons?',
					'woo-cart-abandonment-recovery'
				) }
				description={ __(
					'Coupons this plugin created that were fully used or have expired will be deleted. This cannot be undone.',
					'woo-cart-abandonment-recovery'
				) }
				confirmLabel={ __(
					'Delete coupons',
					'woo-cart-abandonment-recovery'
				) }
				onConfirm={ handleTrigger }
				isConfirming={ isDeleting }
				isDestructive
			/>
		</FieldWrapper>
	);
};

export default DeleteCouponsField;
