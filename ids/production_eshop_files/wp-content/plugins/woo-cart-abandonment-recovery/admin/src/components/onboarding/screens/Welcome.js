import { __ } from '@wordpress/i18n';
import { CheckIcon } from '@heroicons/react/24/outline';

import Header from '@Components/onboarding/Header';
import NavigationButtons from '@Components/onboarding/NavigationButtons';

const features = [
	__(
		'Recover lost revenue automatically and effortlessly',
		'woo-cart-abandonment-recovery'
	),
	__(
		'Quick and easy setup, no technical skills needed',
		'woo-cart-abandonment-recovery'
	),
	__(
		'Track, log, and resend emails with ease',
		'woo-cart-abandonment-recovery'
	),
	__( 'Fully customizable to your store', 'woo-cart-abandonment-recovery' ),
	__(
		'Dynamic coupon generation with expiry control',
		'woo-cart-abandonment-recovery'
	),
];

const Welcome = () => (
	<>
		<Header
			size="lg"
			heading={ __(
				'Welcome to Cart Abandonment Recovery',
				'woo-cart-abandonment-recovery'
			) }
			badge={ __( '≈ 3 min setup', 'woo-cart-abandonment-recovery' ) }
			subHeading={ __(
				'Track abandoned carts in real time & recover lost revenue automatically.',
				'woo-cart-abandonment-recovery'
			) }
		/>

		{ /* Muted is required — browsers block autoplay with sound. */ }
		<div className="rounded-lg overflow-hidden aspect-video">
			<iframe
				className="w-full h-full"
				src="https://www.youtube.com/embed/EXz2joiA6Uc?autoplay=1&mute=1"
				title={ __(
					'Cart Abandonment Recovery walkthrough',
					'woo-cart-abandonment-recovery'
				) }
				frameBorder="0"
				allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
				allowFullScreen
			></iframe>
		</div>

		<ul className="list-none pl-0 m-0 space-y-2.5">
			{ features.map( ( feature ) => (
				<li
					key={ feature }
					className="flex items-start gap-2 text-sm font-medium text-text-secondary"
				>
					<CheckIcon
						className="size-4 text-icon-interactive shrink-0 mt-0.5"
						aria-hidden="true"
					/>
					<span>{ feature }</span>
				</li>
			) ) }
		</ul>

		<NavigationButtons
			nextFullWidth
			nextLabel={ __(
				'Set Up My Cart Recovery',
				'woo-cart-abandonment-recovery'
			) }
		/>
	</>
);

export default Welcome;
