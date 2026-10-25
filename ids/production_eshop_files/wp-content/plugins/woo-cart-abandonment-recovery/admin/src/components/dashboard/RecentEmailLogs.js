import { Link } from 'react-router-dom';
import PropTypes from 'prop-types';
import parse from 'html-react-parser';
import { Button, Table } from '@bsf/force-ui';
import {
	ArrowUpRightIcon,
	InboxIcon,
} from '@heroicons/react/24/outline';
import { __ } from '@wordpress/i18n';

import DashboardCard from '@Components/dashboard/DashboardCard';
import SkeletonLoader from '@Components/common/skeletons/SkeletonLoader';
import { EmptyBlock } from '@Components/common/empty-blocks';
import { BASE_URL } from '@Admin/constants';
import OrderStatusBadge from '@Components/common/OrderStatusBadge';

const RecentEmailLogs = ( { dashboardData, isDashboardLoading } ) => {
	// Use the new API key
	const logs = dashboardData?.recent_follow_up_reports || [];
	const hasData = logs.length > 0;

	return (
		<DashboardCard
			title={ __(
				'Recent Follow Up Reports',
				'woo-cart-abandonment-recovery'
			) }
			action={
				<Button
					variant="ghost"
					size="xs"
					tag={ Link }
					to={ BASE_URL + '&path=follow-up' }
					icon={ <ArrowUpRightIcon className="rtl:-scale-x-100" /> }
					iconPosition="right"
					aria-label={ __(
						'View all follow-up reports',
						'woo-cart-abandonment-recovery'
					) }
					className="no-underline hover:no-underline [@media(pointer:coarse)]:min-h-11 [@media(pointer:coarse)]:px-3"
				>
					{ __( 'View all', 'woo-cart-abandonment-recovery' ) }
				</Button>
			}
		>
			<span className="sr-only" role="status">
				{ isDashboardLoading
					? __( 'Loading…', 'woo-cart-abandonment-recovery' )
					: '' }
			</span>
			{ isDashboardLoading ? (
				<SkeletonLoader height="200px" />
			) : (
				<>
					{ hasData ? (
						<Table
							aria-label={ __(
								'Recent Follow Up Reports',
								'woo-cart-abandonment-recovery'
							) }
							className="whitespace-nowrap sm:whitespace-normal"
						>
							<Table.Head>
								<Table.HeadCell>
									{ __(
										'User Name',
										'woo-cart-abandonment-recovery'
									) }
								</Table.HeadCell>
								<Table.HeadCell>
									{ __(
										'Email',
										'woo-cart-abandonment-recovery'
									) }
								</Table.HeadCell>
								<Table.HeadCell>
									{ __(
										'Cart Total',
										'woo-cart-abandonment-recovery'
									) }
								</Table.HeadCell>
								<Table.HeadCell>
									{ __(
										'Order Status',
										'woo-cart-abandonment-recovery'
									) }
								</Table.HeadCell>
								<Table.HeadCell>
									{ __(
										'Date & Time',
										'woo-cart-abandonment-recovery'
									) }
								</Table.HeadCell>
							</Table.Head>
							<Table.Body>
								{ logs.map( ( item, index ) => (
									<Table.Row key={ item?.id ?? index }>
										<Table.Cell>
											{ item?.userName ||
												__(
													'Not Available',
													'woo-cart-abandonment-recovery'
												) }
										</Table.Cell>
										<Table.Cell>
											{ item?.id && item?.email ? (
												<Link
													to={
														BASE_URL +
														'&path=detailed-report&id=' +
														item.id
													}
													className="inline-flex items-center text-text-primary no-underline hover:underline [@media(pointer:coarse)]:min-h-11"
												>
													{ item.email }
												</Link>
											) : (
												item?.email || '-'
											) }
										</Table.Cell>
										<Table.Cell>
											{ parse( item?.cartTotal || '-' ) }
										</Table.Cell>
										<Table.Cell>
											<OrderStatusBadge
												status={
													item?.orderStatus || '-'
												}
											/>
										</Table.Cell>
										<Table.Cell className="whitespace-nowrap">
											{ item?.dateTime || '-' }
										</Table.Cell>
									</Table.Row>
								) ) }
							</Table.Body>
						</Table>
					) : (
						<EmptyBlock
							icon={
								<InboxIcon className="size-12 text-icon-secondary" />
							}
							title={ __(
								'No Follow-Up Reports Yet',
								'woo-cart-abandonment-recovery'
							) }
							description={ __(
								'Reports will show up here once customers start abandoning their carts.',
								'woo-cart-abandonment-recovery'
							) }
						/>
					) }
				</>
			) }
		</DashboardCard>
	);
};

RecentEmailLogs.propTypes = {
	dashboardData: PropTypes.object,
	isDashboardLoading: PropTypes.bool,
};

export default RecentEmailLogs;
