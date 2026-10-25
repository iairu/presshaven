import { Badge } from '@bsf/force-ui';
import { __ } from '@wordpress/i18n';

import AppTooltip from '@Components/common/AppTooltip';

// The top bar sits at z-30 and the tooltip lands in the app root outside it, so the tooltip needs a
// higher layer to show over the bar.
const TOOLTIP_LAYER = 'z-[99999]';

/**
 * Version badges for the top bar.
 *
 * The free plugin's version always shows. The Pro plugin's version joins it, behind a divider,
 * whenever Pro is active: Pro puts `pro_version` on the localized admin vars. The tooltips read "Core"
 * for the free plugin and "Pro" for Pro, or the plan name, such as "Business", when Pro sends
 * `pro_plan`.
 *
 * @return {JSX.Element} The badges.
 */
const VersionBadge = () => {
	const {
		version,
		pro_version: proVersion,
		pro_plan: proPlan,
	} = window.cart_abandonment_admin || {};

	if ( ! version ) {
		return null;
	}

	return (
		<>
			<AppTooltip
				content={ __( 'Core', 'woo-cart-abandonment-recovery' ) }
				position="bottom"
				className={ TOOLTIP_LAYER }
			>
				<Badge
					label={ `V ${ version }` }
					size="xs"
					variant="neutral"
					disableHover
				/>
			</AppTooltip>
			{ proVersion && (
				<>
					<hr className="m-0 h-4 w-px border-0 border-l border-solid border-border-subtle" />
					<AppTooltip
						content={ proPlan || __( 'Pro', 'woo-cart-abandonment-recovery' ) }
						position="bottom"
						className={ TOOLTIP_LAYER }
					>
						<Badge
							label={ `V ${ proVersion }` }
							size="xs"
							variant="inverse"
							disableHover
						/>
					</AppTooltip>
				</>
			) }
		</>
	);
};

export default VersionBadge;
