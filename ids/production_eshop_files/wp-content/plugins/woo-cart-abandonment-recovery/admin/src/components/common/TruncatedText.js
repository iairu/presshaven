import { useLayoutEffect, useRef, useState } from '@wordpress/element';
import PropTypes from 'prop-types';

import AppTooltip from '@Components/common/AppTooltip';
import { cn } from '@Utils/helper';

/**
 * One line of text that ends in an ellipsis when it does not fit. The full text shows in a tooltip
 * only while it is cut off, on hover, and on keyboard focus or a tap.
 *
 * @param {Object} props
 * @param {string} props.text        The text to show.
 * @param {string} [props.className] Classes for the text line, such as its colour.
 * @return {JSX.Element} The text.
 */
const TruncatedText = ( { text, className = '' } ) => {
	const wrapperRef = useRef( null );
	const [ isTruncated, setIsTruncated ] = useState( false );

	useLayoutEffect( () => {
		const wrapper = wrapperRef.current;
		if ( ! wrapper ) {
			return undefined;
		}
		const measure = () => {
			const line = wrapper.querySelector( '[data-truncated-text]' );
			if ( line ) {
				setIsTruncated( line.scrollWidth > line.clientWidth );
			}
		};
		measure();
		// The column changes width with the window.
		const observer = new window.ResizeObserver( measure );
		observer.observe( wrapper );
		return () => observer.disconnect();
	}, [ text ] );

	const line = (
		<div
			data-truncated-text=""
			className={ cn( 'truncate', className ) }
			// A text line takes focus only when there is more to read, so keyboard and touch
			// users can open the tooltip too.
			tabIndex={ isTruncated ? 0 : undefined }
		>
			{ text }
		</div>
	);

	return (
		<div ref={ wrapperRef } className="min-w-0">
			{ isTruncated ? (
				<AppTooltip content={ text } triggers={ [ 'hover', 'focus' ] }>
					{ line }
				</AppTooltip>
			) : (
				line
			) }
		</div>
	);
};

TruncatedText.propTypes = {
	text: PropTypes.string.isRequired,
	className: PropTypes.string,
};

export default TruncatedText;
