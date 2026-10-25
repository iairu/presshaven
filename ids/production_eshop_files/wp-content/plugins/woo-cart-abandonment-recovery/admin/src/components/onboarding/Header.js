import { Title, Label, Badge } from '@bsf/force-ui';

/**
 * Step heading, shared across the onboarding wizard.
 *
 * `size` separates the screens that open and close the wizard (Welcome, Done)
 * from the form steps in between: the former are felt rather than filled in,
 * and read at `lg` (24px); the latter stay at the default `md` (20px).
 *
 * @param {Object} props
 * @param {string} props.heading      Screen title.
 * @param {string} [props.subHeading] Supporting sentence.
 * @param {string} [props.badge]      Optional pill beside the title (e.g. setup duration).
 * @param {string} [props.tag]        Heading level. Defaults to h1 — every step is its own
 *                                    view, so every step title is that view's h1.
 * @param {string} [props.size]       Force UI Title scale — `md` (20px) or `lg` (24px).
 */
const Header = ( { heading, subHeading, badge, tag = 'h1', size = 'md' } ) => (
	<div className="flex flex-col gap-2">
		<div className="flex flex-wrap items-center gap-3">
			<Title
				size={ size }
				tag={ tag }
				className="text-text-primary tracking-[-0.02em]"
				title={ heading }
			/>
			{ badge && (
				// Box-centred, the pill sits ~2px above the heading's lowercase mass.
				<Badge
					className="translate-y-0.5"
					label={ badge }
					type="pill"
					size="xs"
					variant="neutral"
					disableHover
				/>
			) }
		</div>
		{ subHeading && (
			<Label className="text-text-secondary text-sm font-normal block">
				{ subHeading }
			</Label>
		) }
	</div>
);

export default Header;
