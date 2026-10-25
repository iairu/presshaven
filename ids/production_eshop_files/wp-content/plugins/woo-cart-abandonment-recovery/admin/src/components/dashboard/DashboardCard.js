import PropTypes from 'prop-types';
import { Title, Text } from '@bsf/force-ui';
import { cn } from '@Utils/helper';

/**
 * Shared card shell for every dashboard section: same padding, radius, border,
 * header row and header-to-content gap, so sections cannot drift apart.
 *
 * @param {Object}  props           - Component props.
 * @param {string}  props.title     - Section heading.
 * @param {Node}    props.action    - Optional control shown at the right of the header (e.g. "View all").
 * @param {boolean} props.compact   - Smaller padding and 14px heading, for sidebar-sized cards.
 * @param {string}  props.className - Extra classes for the card.
 * @param {Node}    props.children  - Card content.
 * @return {JSX.Element} Dashboard card.
 */
const DashboardCard = ( {
	title,
	action = null,
	compact = false,
	className = '',
	children,
} ) => {
	return (
		<div
			className={ cn(
				'bg-background-primary border border-solid border-border-subtle rounded-lg shadow-sm flex flex-col',
				compact ? 'p-3 gap-2' : 'p-5 gap-3',
				className
			) }
		>
			<div className="flex flex-wrap items-center justify-between gap-3 p-1">
				{ compact ? (
					<Text as="h2" size={ 14 } weight={ 600 } color="primary">
						{ title }
					</Text>
				) : (
					<Title
						tag="h2"
						size="xs"
						title={ title }
						className="[&>*]:text-text-primary"
					/>
				) }
				{ action }
			</div>
			{ children }
		</div>
	);
};

DashboardCard.propTypes = {
	title: PropTypes.string.isRequired,
	action: PropTypes.node,
	compact: PropTypes.bool,
	className: PropTypes.string,
	children: PropTypes.node,
};

export default DashboardCard;
