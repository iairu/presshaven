import { Label } from '@bsf/force-ui';
import { cn } from '@Utils/helper';
import parse from 'html-react-parser';

import Tooltip from '@Components/fields/Tooltip';
import FeatureBadge from '@Components/common/FeatureBadge';
import { useProAccess } from '../pro/useProAccess';
import ProUpgradeSettingsMsg from '../pro/ProUpgradeSettingsMsg';
import { createContext, useContext, useId } from '@wordpress/element';

// Set where full-width fields should put their help text under the control instead of between
// the title and the control (the template drawers).
export const HelpTextBelowContext = createContext( false );

// Set where field titles should be the smaller, medium-weight size (the Settings and Integrations pages).
export const CompactLabelContext = createContext( false );

const FieldWrapper = ( {
	title,
	name = '',
	description,
	type = 'inline',
	tooltip = '',
	size = 'normal',
	fieldId: fieldIdProp,
	disableStyle = false,
	isPro = false,
	proUpgradeMessage = '',
	afterControl = null,
	children,
} ) => {
	const { getActionButtonText, upgradeActionButton, shouldBlockProFeatures } =
		useProAccess();
	// The control's id, so the label's `for` matches it (see `useFieldA11y`). Fields that don't
	// pass one still get a stable id of their own rather than a new random one each render.
	const generatedId = useId();
	const fieldId = fieldIdProp || generatedId;
	const compactLabel = useContext( CompactLabelContext );
	const smallLabel = compactLabel || size !== 'normal';
	const helpTextBelow =
		useContext( HelpTextBelowContext ) && type === 'block' && !! description;
	const helpText = description && (
		<p
			className={ cn(
				'font-normal text-sm text-gray-500 m-0 break-words [&_pre]:max-w-full [&_pre]:overflow-x-auto',
				// Links in help text come from PHP and some carry no colour of their own.
				compactLabel &&
					'[&_strong]:font-medium [&_a]:text-link-primary [&_a:hover]:text-link-primary-hover'
			) }
			id={ `${ fieldId }-description` }
		>
			{ parse( description ) }
		</p>
	);
	const showProUpgradeMessage =
		shouldBlockProFeatures() && proUpgradeMessage.length > 0;

	return (
		<div
			className={ `flex flex-col gap-2 pb-4 last:pb-6 ${
				! disableStyle
					? 'border-0 border-b border-solid border-gray-200 last:border-b-0'
					: '!p-0'
			}` }
		>
			<div
				id={ name ? `wcar-${ name }` : undefined }
				className={ cn(
					'flex justify-between',
					type === 'block' ? 'flex-col' : 'flex-col sm:flex-row',
					! disableStyle && 'pt-4 first:pt-6',
					// On the Settings and Integrations pages a full-width control sits close under its title,
					// or under its help text when it has one.
					compactLabel && type === 'block'
						? ( description && ! helpTextBelow
							? 'gap-[14px]'
							: 'gap-1' )
						: 'gap-2 lg:gap-5'
				) }
			>
				{ ( title || ( description && ! helpTextBelow ) ) && (
					<div
						className={ cn(
							'w-full min-w-0',
							type !== 'block' && 'sm:w-[70%]'
						) }
					>
						{ title && (
							<div className="flex gap-2 items-center mb-1">
								<Label
									className={
										smallLabel
											? 'font-medium'
											: 'font-semibold'
									}
									htmlFor={ fieldIdProp }
									size={ smallLabel ? 'sm' : 'md' }
									id={ `${ fieldId }-title` }
								>
									{ title.replace(
										/(^|\s)(\p{Ll})/gu,
										( match, space, char ) =>
											space + char.toLocaleUpperCase()
									) }
									{ tooltip && tooltip?.content && (
										<Tooltip
											content={ tooltip?.content }
											title={ tooltip?.title }
										/>
									) }
								</Label>
								{ isPro && <FeatureBadge feature="PRO" /> }
							</div>
						) }
						{ ! helpTextBelow && helpText }
					</div>
				) }
				{ helpTextBelow || afterControl ? (
					<div className="flex flex-col gap-2 w-full">
						{ children }
						{ helpTextBelow && helpText }
						{ afterControl }
					</div>
				) : (
					children
				) }
			</div>
			{ showProUpgradeMessage && (
				<ProUpgradeSettingsMsg
					isVisible={ true }
					description={ proUpgradeMessage }
					buttonText={ getActionButtonText() }
					buttonAction={ upgradeActionButton }
				/>
			) }
		</div>
	);
};

export default FieldWrapper;
