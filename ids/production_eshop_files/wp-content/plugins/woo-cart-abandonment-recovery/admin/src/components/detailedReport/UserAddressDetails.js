import { Title, Badge } from '@bsf/force-ui';
import { __ } from '@wordpress/i18n';

import SectionWrapper from '@Components/common/SectionWrapper';
import OrderStatusBadge from '@Components/common/OrderStatusBadge';
import SkeletonLoader from '@Components/common/skeletons/SkeletonLoader';

// Shown for a field the customer never filled in, instead of a blank or the word "undefined".
const EMPTY_VALUE = '—';

const valueOrDash = ( ...parts ) =>
	parts
		.map( ( part ) => ( part ?? '' ).toString().trim() )
		.filter( Boolean )
		.join( ', ' ) || EMPTY_VALUE;

// One "Label: value" line of an address.
const AddressLine = ( { label, value } ) => (
	<p className="m-0 text-gray-500">
		<span className="text-gray-900">{ label }</span> { value }
	</p>
);

// A titled column of address lines, with room for extra content under them.
const AddressColumn = ( { title, lines, children } ) => (
	<div className="flex-1 flex flex-col gap-3">
		<Title
			size="xs"
			tag="h3"
			title={ title }
			className="[&_h2]:text-gray-900"
		/>
		<div className="flex flex-col gap-2">
			{ lines.map( ( [ label, value ] ) => (
				<AddressLine key={ label } label={ label } value={ value } />
			) ) }
		</div>
		{ children }
	</div>
);

const UserAddressDetails = ( {
	userDetails,
	email,
	orderStatus,
	checkoutLink,
	unsubscribed,
	isLoading,
} ) => {
	const billingLines = [
		[
			__( 'Full Name:', 'woo-cart-abandonment-recovery' ),
			valueOrDash(
				[ userDetails.wcf_first_name, userDetails.wcf_last_name ]
					.filter( Boolean )
					.join( ' ' )
			),
		],
		[
			__( 'Contact Email:', 'woo-cart-abandonment-recovery' ),
			valueOrDash( email ),
		],
		[
			__( 'Contact Number:', 'woo-cart-abandonment-recovery' ),
			valueOrDash( userDetails.wcf_phone_number ),
		],
		[
			__( 'Street Address 1:', 'woo-cart-abandonment-recovery' ),
			valueOrDash( userDetails.wcf_billing_address_1 ),
		],
		[
			__( 'Street Address 2:', 'woo-cart-abandonment-recovery' ),
			valueOrDash( userDetails.wcf_billing_address_2 ),
		],
		[
			__( 'Country, City:', 'woo-cart-abandonment-recovery' ),
			valueOrDash( userDetails.wcf_location ),
		],
		[
			__( 'State:', 'woo-cart-abandonment-recovery' ),
			valueOrDash( userDetails.wcf_billing_state ),
		],
		[
			__( 'Zip Code:', 'woo-cart-abandonment-recovery' ),
			valueOrDash( userDetails.wcf_billing_postcode ),
		],
	];
	const shippingLines = [
		[
			__( 'Street Address 1:', 'woo-cart-abandonment-recovery' ),
			valueOrDash( userDetails.wcf_shipping_address_1 ),
		],
		[
			__( 'Street Address 2:', 'woo-cart-abandonment-recovery' ),
			valueOrDash( userDetails.wcf_shipping_address_2 ),
		],
		[
			__( 'Country, City:', 'woo-cart-abandonment-recovery' ),
			valueOrDash(
				userDetails.wcf_shipping_country,
				userDetails.wcf_shipping_city
			),
		],
		[
			__( 'State:', 'woo-cart-abandonment-recovery' ),
			valueOrDash( userDetails.wcf_shipping_state ),
		],
		[
			__( 'Zip Code:', 'woo-cart-abandonment-recovery' ),
			valueOrDash( userDetails.wcf_shipping_postcode ),
		],
	];

	return (
		<SectionWrapper className="flex flex-col gap-4">
			<div className="flex items-center justify-between">
				<Title
					size="sm"
					tag="h2"
					title={ __(
						'User Address Details',
						'woo-cart-abandonment-recovery'
					) }
					className="[&_h2]:text-gray-900"
				/>
				{ ! isLoading && (
					<div className="flex gap-2">
						<OrderStatusBadge status={ orderStatus } />
						{ '1' === unsubscribed && (
							<Badge
								label={ __( 'Unsubscribed', 'woo-cart-abandonment-recovery' ) }
								size="sm"
								type="pill"
								variant="red"
								className="w-fit"
							/>
						) }
					</div>
				) }
			</div>
			{ isLoading ? (
				<div className="flex flex-col md:flex-row gap-8">
					<div className="flex-1 flex flex-col gap-3">
						<SkeletonLoader height="24px" width="150px" />
						{ [ ...Array( 8 ) ].map( ( _, index ) => (
							<SkeletonLoader
								key={ index }
								height="20px"
								// eslint-disable-next-line no-mixed-operators
								width={ `${ 70 + Math.random() * 30 }%` }
							/>
						) ) }
					</div>
					<div className="flex-1 flex flex-col gap-3">
						<SkeletonLoader height="24px" width="150px" />
						{ [ ...Array( 5 ) ].map( ( _, index ) => (
							<SkeletonLoader
								key={ index }
								height="20px"
								// eslint-disable-next-line no-mixed-operators
								width={ `${ 70 + Math.random() * 30 }%` }
							/>
						) ) }
						<div className="mt-2">
							<SkeletonLoader height="24px" width="200px" />
						</div>
					</div>
				</div>
			) : (
				<div className="flex flex-col md:flex-row gap-8">
					<AddressColumn
						title={ __(
							'Billing Address:',
							'woo-cart-abandonment-recovery'
						) }
						lines={ billingLines }
					/>
					<AddressColumn
						title={ __(
							'Shipping Address:',
							'woo-cart-abandonment-recovery'
						) }
						lines={ shippingLines }
					>
						<div className="flex gap-4 items-center">
							<span className="text-base text-gray-900 font-medium">
								{ __(
									'Checkout Page:',
									'woo-cart-abandonment-recovery'
								) }
							</span>
							<a
								href={ checkoutLink }
								className="inline-flex items-center text-xs font-semibold text-flamingo-400 no-underline border-0 [@media(pointer:coarse)]:min-h-11"
							>
								{ __(
									'Link to Checkout Page',
									'woo-cart-abandonment-recovery'
								) }
							</a>
						</div>
					</AddressColumn>
				</div>
			) }
		</SectionWrapper>
	);
};

export default UserAddressDetails;

