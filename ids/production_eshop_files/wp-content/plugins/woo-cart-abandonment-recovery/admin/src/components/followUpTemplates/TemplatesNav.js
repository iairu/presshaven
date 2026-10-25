import { Tabs } from '@bsf/force-ui';
import { __ } from '@wordpress/i18n';
import { useNavigate } from 'react-router-dom';

import { cn } from '@Utils/helper';

const TemplatesNav = ( { currentTab } ) => {
	const navigate = useNavigate();

	const tabs = [
		{
			slug: 'email',
			text: __( 'Email', 'woo-cart-abandonment-recovery' ),
		},
		{ slug: 'sms', text: __( 'SMS', 'woo-cart-abandonment-recovery' ) },
		{
			slug: 'whatsapp',
			text: __( 'WhatsApp', 'woo-cart-abandonment-recovery' ),
		},
	];

	return (
		<Tabs activeItem={ currentTab }>
			<Tabs.Group
				onChange={ ( { value } ) => {
					navigate( {
						search:
							'?page=woo-cart-abandonment-recovery&path=follow-up-templates&tab=' +
							value.slug,
					} );
				} }
				size="md"
				variant="rounded"
				width="auto"
				className="p-0 w-fit bg-white"
			>
				{ tabs.map( ( tab, index ) => (
					<Tabs.Tab
						key={ index }
						slug={ tab.slug }
						text={ tab.text }
						className={ cn(
							'hover:text-primary-600 [@media(pointer:coarse)]:min-h-11',
							currentTab === tab.slug &&
								'text-primary-600 bg-primary-25 outline outline-1 outline-primary-300 focus:outline-1'
						) }
					/>
				) ) }
			</Tabs.Group>
		</Tabs>
	);
};

export default TemplatesNav;

