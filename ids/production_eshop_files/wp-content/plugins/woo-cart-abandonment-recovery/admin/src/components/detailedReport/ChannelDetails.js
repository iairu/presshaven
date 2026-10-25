import { useId } from 'react';
import { Table, Title, Button, Loader } from '@bsf/force-ui';
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline';
import { __ } from '@wordpress/i18n';

import SectionWrapper from '@Components/common/SectionWrapper';
import SkeletonLoader from '@Components/common/skeletons/SkeletonLoader';
import { EmptyBlock } from '@Components/common/empty-blocks';
import { ProUpgradeCta } from '@Components/pro';
import { OUTLINE_PRIMARY_BUTTON_CLASS } from '@Components/common/tableStyles';
import ScrollableTable from '@Components/common/ScrollableTable';
import MessageStatusBadge from '@Components/detailedReport/MessageStatusBadge';

/**
 * One channel's section of the Detailed Report: the follow-ups scheduled for this cart, with a
 * button to schedule them again. Email, SMS and WhatsApp differ only in their labels and in which
 * fields hold the message and its sent flag.
 *
 * @param {Object}   props
 * @param {string}   props.title            Section heading, such as "Email Details".
 * @param {string}   props.rescheduleLabel  Label of the reschedule button.
 * @param {string}   props.messageHeading   Heading of the column that shows the message.
 * @param {string}   props.messageKey       Field of a row that holds the message.
 * @param {string}   props.sentKey          Field of a row that holds the sent flag.
 * @param {string}   props.emptyDescription Says why the section is empty.
 * @param {Object[]} props.rows             The scheduled follow-ups.
 * @param {Function} props.onReschedule     Schedules them again.
 * @param {boolean}  props.isLoading        Whether the report is still loading.
 * @param {boolean}  props.buttonLoading    Whether a reschedule is running.
 * @param {boolean}  props.disabled         Whether the cart is blacklisted.
 * @param {string}   props.unsubscribed     The cart's unsubscribed flag.
 * @param {boolean}  [props.isLocked]       Whether this channel needs a Pro upgrade.
 * @param {string}   [props.lockedMessage]  What to tell a free user the channel offers.
 * @return {JSX.Element} The section.
 */
const ChannelDetails = ( {
	title,
	rescheduleLabel,
	messageHeading,
	messageKey,
	sentKey,
	emptyDescription,
	rows,
	onReschedule,
	isLoading,
	buttonLoading,
	disabled,
	unsubscribed,
	isLocked = false,
	lockedMessage = '',
} ) => {
	const showLocked = ! isLoading && isLocked;
	// A blacklisted cart cannot be rescheduled; say so next to the button that stopped working.
	const reasonId = useId();
	const showDisabledReason = ! isLoading && ! isLocked && disabled;

	return (
		<SectionWrapper className="flex flex-col gap-4">
			<div className="flex flex-wrap items-center justify-between gap-3">
				<Title
					size="sm"
					tag="h2"
					title={ title }
					className="[&_h2]:text-gray-900"
				/>
				<Button
					className={ OUTLINE_PRIMARY_BUTTON_CLASS }
					size="sm"
					tag="button"
					type="button"
					variant="outline"
					onClick={ onReschedule }
					disabled={ isLoading || buttonLoading || isLocked || disabled }
					aria-describedby={ showDisabledReason ? reasonId : undefined }
					icon={
						buttonLoading && (
							<Loader
								className="text-flamingo-400 p-0"
								icon={ null }
								size="sm"
								variant="primary"
							/>
						)
					}
					iconPosition="left"
				>
					{ rescheduleLabel }
				</Button>
			</div>
			{ showDisabledReason && (
				<p id={ reasonId } className="m-0 text-sm text-gray-500">
					{ __(
						'This cart is blacklisted, so no follow-ups can be scheduled for it.',
						'woo-cart-abandonment-recovery'
					) }
				</p>
			) }
			{ showLocked && (
				<div className="relative h-24">
					<ProUpgradeCta
						isVisible={ true }
						mainTitle=""
						subTitle=""
						variation="message"
						description={ lockedMessage }
					/>
				</div>
			) }
			{ ! showLocked && isLoading && (
				<div className="flex flex-col gap-4">
					<SkeletonLoader height="40px" />
					{ [ ...Array( 3 ) ].map( ( _, index ) => (
						<SkeletonLoader key={ index } height="50px" />
					) ) }
				</div>
			) }
			{ ! showLocked && ! isLoading && rows.length > 0 && (
				<ScrollableTable label={ title }>
					<Table className="whitespace-nowrap" aria-label={ title }>
						<Table.Head>
							<Table.HeadCell>
								{ __(
									'Scheduled Templates',
									'woo-cart-abandonment-recovery'
								) }
							</Table.HeadCell>
							<Table.HeadCell>{ messageHeading }</Table.HeadCell>
							<Table.HeadCell>
								{ __( 'Coupon', 'woo-cart-abandonment-recovery' ) }
							</Table.HeadCell>
							<Table.HeadCell>
								{ __( 'Status', 'woo-cart-abandonment-recovery' ) }
							</Table.HeadCell>
							<Table.HeadCell>
								{ __(
									'Scheduled At',
									'woo-cart-abandonment-recovery'
								) }
							</Table.HeadCell>
						</Table.Head>
						<Table.Body>
							{ rows.map( ( item, index ) => (
								<Table.Row key={ index }>
									<Table.Cell>{ item.template_name }</Table.Cell>
									{ /* Long messages wrap to two lines instead of hiding behind an ellipsis. */ }
									<Table.Cell className="max-w-72 whitespace-normal">
										<div
											className="line-clamp-2 break-words"
											title={ item[ messageKey ] }
										>
											{ item[ messageKey ] }
										</div>
									</Table.Cell>
									<Table.Cell>
										{ item.coupon_code || '-' }
									</Table.Cell>
									<Table.Cell>
										<MessageStatusBadge
											status={ item[ sentKey ] }
											disabled={ disabled }
											unsubscribed={ unsubscribed }
										/>
									</Table.Cell>
									<Table.Cell>{ item.scheduled_time }</Table.Cell>
								</Table.Row>
							) ) }
						</Table.Body>
					</Table>
				</ScrollableTable>
			) }
			{ ! showLocked && ! isLoading && rows.length === 0 && (
				<EmptyBlock
					icon={
						<ExclamationTriangleIcon className="h-12 w-12 text-yellow-500" />
					}
					title={ __(
						'No data available',
						'woo-cart-abandonment-recovery'
					) }
					description={ emptyDescription }
				/>
			) }
		</SectionWrapper>
	);
};

export default ChannelDetails;
