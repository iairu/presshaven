import { Table, Title } from '@bsf/force-ui';
import parse from 'html-react-parser';
import { __ } from '@wordpress/i18n';

import SectionWrapper from '@Components/common/SectionWrapper';
import SkeletonLoader from '@Components/common/skeletons/SkeletonLoader';
import ScrollableTable from '@Components/common/ScrollableTable';

const UserOrderDetails = ( { orderDetails, isLoading } ) => {
	const items = orderDetails?.items ?? [];
	const summary = orderDetails?.summary ?? {};
	const summaryRows = [
		[ __( 'Discount:', 'woo-cart-abandonment-recovery' ), summary.discount ],
		[ __( 'Others:', 'woo-cart-abandonment-recovery' ), summary.others ],
		[ __( 'Shipping:', 'woo-cart-abandonment-recovery' ), summary.shipping ],
		[ __( 'Cart Total:', 'woo-cart-abandonment-recovery' ), summary.cartTotal ],
	];

	return (
		<SectionWrapper className="flex flex-col gap-4">
			<Title
				size="sm"
				tag="h2"
				title={ __(
					'User Order Details',
					'woo-cart-abandonment-recovery'
				) }
				className="[&_h2]:text-gray-900"
			/>
			{ isLoading ? (
				<div className="flex flex-col gap-4">
					<SkeletonLoader height="40px" />
					{ [ ...Array( 3 ) ].map( ( _, index ) => (
						<div key={ index } className="flex gap-4">
							<SkeletonLoader
								width="60px"
								height="60px"
								borderRadius="8px"
							/>
							<div className="flex-1 flex flex-col gap-2">
								<SkeletonLoader height="20px" width="70%" />
								<SkeletonLoader height="16px" width="40%" />
							</div>
						</div>
					) ) }
					<div className="mt-2">
						<SkeletonLoader height="80px" />
					</div>
				</div>
			) : (
				<>
					<ScrollableTable
						label={ __(
							'Items in the cart',
							'woo-cart-abandonment-recovery'
						) }
					>
						<Table
							className="whitespace-nowrap"
							aria-label={ __(
								'Items in the cart',
								'woo-cart-abandonment-recovery'
							) }
						>
							<Table.Head>
								<Table.HeadCell>
									{ __( 'Items', 'woo-cart-abandonment-recovery' ) }
								</Table.HeadCell>
								<Table.HeadCell>
									{ __( 'Quantity', 'woo-cart-abandonment-recovery' ) }
								</Table.HeadCell>
								<Table.HeadCell>
									{ __( 'Price', 'woo-cart-abandonment-recovery' ) }
								</Table.HeadCell>
								<Table.HeadCell>
									{ __( 'Subtotal', 'woo-cart-abandonment-recovery' ) }
								</Table.HeadCell>
							</Table.Head>
							<Table.Body>
								{ items.map( ( item, index ) => (
									<Table.Row key={ index }>
										<Table.Cell>
											<div className="flex items-center gap-4 text-gray-900">
												<img
													loading="lazy"
													src={ item.imageUrl }
													alt=""
													className="w-12 h-12 shrink-0 object-cover rounded-md border border-solid border-gray-200"
												/>
												{ parse( item.name || '' ) }
											</div>
										</Table.Cell>
										<Table.Cell className="font-medium">
											{ item.quantity }
										</Table.Cell>
										<Table.Cell className="font-medium">
											{ item.price }
										</Table.Cell>
										<Table.Cell className="font-medium">
											{ item.subtotal }
										</Table.Cell>
									</Table.Row>
								) ) }
							</Table.Body>
						</Table>
					</ScrollableTable>
					{ /* A list of its own, so the labels stay readable on narrow screens. */ }
					<dl className="m-0 ml-auto box-border flex w-full max-w-sm flex-col gap-3 rounded-md bg-background-secondary p-4">
						{ summaryRows.map( ( [ label, value ] ) => (
							<div
								key={ label }
								className="flex items-center justify-between gap-6"
							>
								<dt className="font-medium text-gray-900">
									{ label }
								</dt>
								<dd className="m-0 font-medium">
									{ value || '—' }
								</dd>
							</div>
						) ) }
					</dl>
				</>
			) }
		</SectionWrapper>
	);
};

export default UserOrderDetails;
