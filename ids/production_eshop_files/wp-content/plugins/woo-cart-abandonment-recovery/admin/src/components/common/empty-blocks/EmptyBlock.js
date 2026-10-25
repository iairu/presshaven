import React from 'react';
import PropTypes from 'prop-types';
import { Container, Label } from '@bsf/force-ui';
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline';
import { cn } from '@Utils/helper';

/**
 * EmptyBlock component for displaying empty state messages.
 *
 * @param {Object}          props             - Component props.
 * @param {React.ReactNode} props.icon        - Icon to display (defaults to ExclamationTriangle).
 * @param {string}          props.title       - Primary message to display.
 * @param {string}          props.description - Secondary message with additional context.
 * @param {React.ReactNode} props.action      - Optional next-step control (button group) shown under the description.
 * @param {string}          props.className   - Additional CSS classes. Merged with the defaults, so a class such as "min-h-64" replaces the default 200px minimum height.
 * @return {JSX.Element} EmptyBlock component.
 */
const EmptyBlock = ( {
	icon = <ExclamationTriangleIcon className="h-12 w-12 text-yellow-500" />,
	title,
	description,
	action,
	className = '',
} ) => {
	return (
		<Container
			className={ cn(
				'flex-1 min-h-[200px] flex items-center justify-center bg-white rounded-md',
				className
			) }
			containerType="flex"
			direction="column"
			align="center"
			gap="xs"
		>
			<Container.Item className="mb-1">{ icon }</Container.Item>
			<Container.Item className="flex flex-col items-center gap-1">
				<Label className="text-gray-600 font-medium text-base text-center">
					{ title }
				</Label>
				{ description && (
					<Label className="text-gray-500 text-sm text-center">
						{ description }
					</Label>
				) }
			</Container.Item>
			{ action && (
				<Container.Item className="mt-3 flex flex-wrap justify-center gap-3">
					{ action }
				</Container.Item>
			) }
		</Container>
	);
};

EmptyBlock.propTypes = {
	icon: PropTypes.node,
	title: PropTypes.string.isRequired,
	description: PropTypes.string,
	action: PropTypes.node,
	className: PropTypes.string,
};

export default EmptyBlock;
