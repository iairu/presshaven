import { Link } from 'react-router-dom';
import PropTypes from 'prop-types';
import { Button, Table } from '@bsf/force-ui';
import {
	ArrowUpRightIcon,
	ShoppingBagIcon,
} from '@heroicons/react/24/outline';
import { __ } from '@wordpress/i18n';
import parse from 'html-react-parser';

import DashboardCard from '@Components/dashboard/DashboardCard';
import SkeletonLoader from '@Components/common/skeletons/SkeletonLoader';
import { EmptyBlock } from '@Components/common/empty-blocks';
import { BASE_URL } from '@Admin/constants';
import { ProUpgradeCta, ProductReportDummyData } from '@Components/pro';
import { useProAccess } from '@Components/pro/useProAccess';

const ProductReport = ( { dashboardData, isDashboardLoading } ) => {
	const { shouldBlockProFeatures } = useProAccess();
	// Check if product report data exists and has items
	const hasProductData =
		dashboardData?.product_report &&
		dashboardData.product_report.length > 0;
	const isFeatureBlocked = shouldBlockProFeatures();

	return (
		<DashboardCard
			title={ __( 'Product Reports', 'woo-cart-abandonment-recovery' ) }
			action={
				<Button
					variant="ghost"
					size="xs"
					tag={ Link }
					to={ BASE_URL + '&path=product' }
					icon={ <ArrowUpRightIcon className="rtl:-scale-x-100" /> }
					iconPosition="right"
					aria-label={ __(
						'View all product reports',
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
					{ isFeatureBlocked ? (
						<div className="relative">
							<ProUpgradeCta
								isVisible={ true }
								mainTitle=""
								subTitle=""
								variation="message"
								description={
									/* translators: %%1$s: Link HTML Start and %2$sof: Link HTML End. */
									__(
										'Product Report shows you which items bring the most recoveries and sales.',
										'woo-cart-abandonment-recovery'
									)
								}
							/>
							<ProductReportDummyData minified={ true } />
						</div>
					) : hasProductData ? (
						<Table
							aria-label={ __(
								'Product Reports',
								'woo-cart-abandonment-recovery'
							) }
						>
							<Table.Head>
								<Table.HeadCell>
									{ __(
										'Product Name',
										'woo-cart-abandonment-recovery'
									) }
								</Table.HeadCell>
								<Table.HeadCell>
									{ __(
										'No. of time Abandoned',
										'woo-cart-abandonment-recovery'
									) }
								</Table.HeadCell>
								<Table.HeadCell>
									{ __(
										'No. of time Recovered',
										'woo-cart-abandonment-recovery'
									) }
								</Table.HeadCell>
							</Table.Head>
							<Table.Body>
								{ dashboardData.product_report.map(
									( item, index ) => (
										<Table.Row
											key={
												item.id ??
												`${ item.productName }-${ index }`
											}
										>
											<Table.Cell>
												{ item.productName }
											</Table.Cell>
											<Table.Cell>
												{ parse( item.abandoned ) }
											</Table.Cell>
											<Table.Cell>
												{ parse( item.recovered ) }
											</Table.Cell>
										</Table.Row>
									)
								) }
							</Table.Body>
						</Table>
					) : (
						<EmptyBlock
							icon={
								<ShoppingBagIcon className="size-12 text-icon-secondary" />
							}
							title={ __(
								'No Product Data Yet',
								'woo-cart-abandonment-recovery'
							) }
							description={ __(
								"You'll see product abandonment stats here once customers start adding items to their carts.",
								'woo-cart-abandonment-recovery'
							) }
						/>
					) }
				</>
			) }
		</DashboardCard>
	);
};

ProductReport.propTypes = {
	dashboardData: PropTypes.object,
	isDashboardLoading: PropTypes.bool,
};

export default ProductReport;
