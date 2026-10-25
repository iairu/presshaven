import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Button, toast } from '@bsf/force-ui';
import { doApiFetch } from '@Store';
import {
	ChevronLeftIcon,
	ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';
import { __ } from '@wordpress/i18n';

import SectionWrapper from '@Components/common/SectionWrapper';
import { EmptyBlock } from '@Components/common/empty-blocks';
import { OUTLINE_PRIMARY_BUTTON_CLASS } from '@Components/common/tableStyles';
import { cn } from '@Utils/helper';
import EmailDetails from '@Components/detailedReport/EmailDetails';
import UserOrderDetails from '@Components/detailedReport/UserOrderDetails';
import UserAddressDetails from '@Components/detailedReport/UserAddressDetails';
import SmsDetails from '@Components/detailedReport/SmsDetails';
import WhatsappDetails from '@Components/detailedReport/WhatsappDetails';

// Shape the order table expects before a report has loaded, or when it could not be found.
const EMPTY_ORDER_DETAILS = { items: [], summary: {} };

const DetailedReport = () => {
	const [ isLoading, setIsLoading ] = useState( true );
	// Why no report is shown: it does not exist (deleted, or a stale link), or the request failed.
	const [ loadProblem, setLoadProblem ] = useState( null );
	const [ reloadKey, setReloadKey ] = useState( 0 );
	const [ scheduledEmails, setScheduledEmails ] = useState( [] );
	const [ scheduledMessages, setScheduledMessages ] = useState( [] );
	const [ scheduledSms, setScheduledSms ] = useState( [] );
	const [ userDetails, setUserDetails ] = useState( {} );
	const [ orderDetails, setOrderDetails ] = useState( EMPTY_ORDER_DETAILS );
	const [ orderStatus, setOrderStatus ] = useState( '' );
	const [ email, setEmail ] = useState( '' );
	const [ checkoutLink, setCheckoutLink ] = useState( '' );
	const [ sessionId, setSessionId ] = useState( '' );
	const [ unsubscribed, setUnsubscribed ] = useState( '' );
	const [ emailButtonLoading, setEmailButtonLoading ] = useState( false );
	const [ smsButtonLoading, setSmsButtonLoading ] = useState( false );
	const [ messageButtonLoading, setMessageButtonLoading ] = useState( false );
	const navigate = useNavigate();
	const urlParams = new URLSearchParams( useLocation().search );
	const reportId = urlParams.get( 'id' );

	// Load data
	useEffect( () => {
		const fetchData = async () => {
			setIsLoading( true );
			setLoadProblem( null );
			try {
				await doApiFetch(
					'/wcar/api/admin/detailed-report/',
					{ id: reportId },
					'POST',
					( response ) => {
						// An unknown id comes back as an empty answer.
						if ( ! response?.details ) {
							setLoadProblem( 'not-found' );
							return;
						}
						setScheduledEmails( response.scheduled_emails || [] );
						setScheduledSms( response.scheduled_sms || [] );
						setScheduledMessages(
							response.scheduled_whatsapp_messages || []
						);
						setUserDetails( response.user_details || {} );
						setOrderDetails(
							response.order_details || EMPTY_ORDER_DETAILS
						);
						setOrderStatus( response.details.order_status || '' );
						setEmail( response.details.email || '' );
						setCheckoutLink( response.checkout_link || '' );
						setSessionId( response.details.session_id || '' );
						setUnsubscribed( response.details.unsubscribed || '' );
					}
				);
			} catch ( error ) {
				setLoadProblem( 'failed' );
			}
			setIsLoading( false );
		};
		if ( reportId ) {
			fetchData();
		} else {
			setLoadProblem( 'not-found' );
			setIsLoading( false );
		}
	}, [ reportId, reloadKey ] );

	const handleBackToReports = () => {
		navigate( {
			search: '?page=woo-cart-abandonment-recovery&path=follow-up',
		} );
	};

	// Email, SMS and WhatsApp reschedule the same way: post the cart's session id to a different
	// AJAX action and show the list it sends back.
	const reschedule = ( {
		action,
		nonce,
		setLoading,
		setRows,
		rowsKey,
		successMessage,
		failureMessage,
	} ) => {
		if ( ! sessionId ) {
			return;
		}
		setLoading( true );

		const formData = new window.FormData();
		formData.append( 'action', action );
		formData.append( 'session_id', sessionId );
		formData.append( 'security', nonce );
		doApiFetch(
			cart_abandonment_admin?.ajax_url,
			formData,
			'POST',
			( response ) => {
				if ( response.success ) {
					toast.success( successMessage );
					setRows( response.data?.[ rowsKey ] || [] );
				} else {
					toast.error( failureMessage, {
						description: response.data?.message || '',
					} );
				}
				setLoading( false );
			},
			( error ) => {
				toast.error( failureMessage, {
					description: error.data?.message || '',
				} );
				setLoading( false );
			},
			true,
			false
		).catch( () => {} );
	};

	const handleRescheduleEmails = () =>
		reschedule( {
			action: 'wcar_reschedule_emails',
			nonce: cart_abandonment_admin?.reschedule_emails_nonce,
			setLoading: setEmailButtonLoading,
			setRows: setScheduledEmails,
			rowsKey: 'scheduled_emails',
			successMessage: __(
				'Email Scheduled Successfully',
				'woo-cart-abandonment-recovery'
			),
			failureMessage: __(
				'Email Scheduling failed',
				'woo-cart-abandonment-recovery'
			),
		} );

	const handleRescheduleSms = () =>
		reschedule( {
			action: 'wcar_pro_reschedule_sms',
			nonce: cart_abandonment_admin?.reschedule_sms_nonce,
			setLoading: setSmsButtonLoading,
			setRows: setScheduledSms,
			rowsKey: 'scheduled_sms',
			successMessage: __(
				'SMS Scheduled Successfully',
				'woo-cart-abandonment-recovery'
			),
			failureMessage: __(
				'SMS Scheduling failed',
				'woo-cart-abandonment-recovery'
			),
		} );

	const handleRescheduleMessages = () =>
		reschedule( {
			action: 'wcar_pro_reschedule_whatsapp_messages',
			nonce: cart_abandonment_admin?.reschedule_whatsapp_messages_nonce,
			setLoading: setMessageButtonLoading,
			setRows: setScheduledMessages,
			rowsKey: 'scheduled_messages',
			successMessage: __(
				'Messages Scheduled Successfully',
				'woo-cart-abandonment-recovery'
			),
			failureMessage: __(
				'Message Scheduling failed',
				'woo-cart-abandonment-recovery'
			),
		} );

	let problemCopy = {
		title: __( 'Could not load this report', 'woo-cart-abandonment-recovery' ),
		description: __(
			'Check your connection and try again.',
			'woo-cart-abandonment-recovery'
		),
	};
	if ( 'not-found' === loadProblem ) {
		problemCopy = {
			title: __( 'Report not found', 'woo-cart-abandonment-recovery' ),
			description: __(
				'It may have been deleted. Go back to the reports list to pick another one.',
				'woo-cart-abandonment-recovery'
			),
		};
	}

	return (
		<div className="p-4 md:p-8">
			<SectionWrapper className="p-4 flex flex-col gap-5">
				<Button
					className={ cn( 'w-fit', OUTLINE_PRIMARY_BUTTON_CLASS ) }
					size="sm"
					tag="button"
					type="button"
					variant="outline"
					icon={ <ChevronLeftIcon className="h-5 w-5" /> }
					iconPosition="left"
					onClick={ handleBackToReports }
				>
					{ __( 'Back to Reports', 'woo-cart-abandonment-recovery' ) }
				</Button>
				{ loadProblem ? (
					<div role="alert">
						<h1 className="sr-only">
							{ __( 'Report details', 'woo-cart-abandonment-recovery' ) }
						</h1>
						<EmptyBlock
							icon={
								<ExclamationTriangleIcon className="h-12 w-12 text-yellow-500" />
							}
							title={ problemCopy.title }
							description={ problemCopy.description }
							action={
								'failed' === loadProblem && (
									<Button
										size="sm"
										variant="primary"
										onClick={ () =>
											setReloadKey( ( key ) => key + 1 )
										}
									>
										{ __(
											'Try Again',
											'woo-cart-abandonment-recovery'
										) }
									</Button>
								)
							}
						/>
					</div>
				) : (
					<div className="p-1 rounded-lg flex flex-col gap-1 bg-light-background">
						{ /* Email Details Section */ }
						<EmailDetails
							scheduledEmails={ scheduledEmails }
							handleRescheduleEmails={ handleRescheduleEmails }
							isLoading={ isLoading }
							buttonLoading={ emailButtonLoading }
							disabled={ 'Blacklisted' === orderStatus }
							unsubscribed={ unsubscribed }
						/>
						<SmsDetails
							scheduledSms={ scheduledSms }
							handleRescheduleSms={ handleRescheduleSms }
							isLoading={ isLoading }
							buttonLoading={ smsButtonLoading }
							disabled={ 'Blacklisted' === orderStatus }
							unsubscribed={ unsubscribed }
						/>
						<WhatsappDetails
							scheduledMessages={ scheduledMessages }
							handleRescheduleMessage={ handleRescheduleMessages }
							isLoading={ isLoading }
							buttonLoading={ messageButtonLoading }
							disabled={ 'Blacklisted' === orderStatus }
							unsubscribed={ unsubscribed }
						/>
						{ /* User Address Details Section */ }
						<UserAddressDetails
							userDetails={ userDetails }
							email={ email }
							orderStatus={ orderStatus }
							checkoutLink={ checkoutLink }
							unsubscribed={ unsubscribed }
							isLoading={ isLoading }
						/>
						{ /* User Order Details Section */ }
						<UserOrderDetails
							orderDetails={ orderDetails }
							isLoading={ isLoading }
						/>
					</div>
				) }
			</SectionWrapper>
		</div>
	);
};

export default DetailedReport;

