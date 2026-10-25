import { useEffect, useRef } from '@wordpress/element';

// Focus ring, written out in full so Tailwind generates it. It goes on the bordered frame around
// the scroll area: the table's own cells paint over an outline drawn on the scroll area itself, so
// a ring there never shows.
const RING_CLASSES =
	'outline outline-2 outline-offset-1 outline-primary-600'.split( ' ' );

/**
 * Wraps a Force UI `Table` so its sideways scroll area can be reached and scrolled with the
 * keyboard when, and only when, it overflows. The table scrolls inside a div of its own on narrow
 * screens, and a div that scrolls but cannot take focus leaves keyboard users without the hidden
 * columns. A table that fits has nothing to scroll, so it gets no tab stop.
 *
 * @param {Object} props
 * @param {string} props.label    Names the region for screen readers.
 * @param {Node}   props.children The `Table`.
 * @return {JSX.Element} The wrapped table.
 */
const ScrollableTable = ( { label, children } ) => {
	const wrapperRef = useRef( null );

	useEffect( () => {
		const scroller = wrapperRef.current?.querySelector( '.overflow-x-auto' );
		if ( ! scroller ) {
			return undefined;
		}
		const frame = scroller.parentElement || scroller;

		// Only keyboard focus draws the ring, as with `:focus-visible`, not a click inside the table.
		// A browser that does not know the selector throws, and then every focus gets the ring.
		const isKeyboardFocus = () => {
			try {
				return scroller.matches( ':focus-visible' );
			} catch ( error ) {
				return true;
			}
		};
		const showRing = () => {
			if ( isKeyboardFocus() ) {
				frame.classList.add( ...RING_CLASSES );
			}
		};
		const hideRing = () => frame.classList.remove( ...RING_CLASSES );

		const sync = () => {
			if ( scroller.scrollWidth > scroller.clientWidth ) {
				scroller.setAttribute( 'tabindex', '0' );
				scroller.setAttribute( 'role', 'region' );
				scroller.setAttribute( 'aria-label', label );
			} else {
				scroller.removeAttribute( 'tabindex' );
				scroller.removeAttribute( 'role' );
				scroller.removeAttribute( 'aria-label' );
				// A scroll area that stops being focusable may not send a blur event.
				hideRing();
			}
		};

		sync();
		scroller.addEventListener( 'focus', showRing );
		scroller.addEventListener( 'blur', hideRing );
		// The scroll area changes size with the window; its table changes size with the data.
		const observer = new window.ResizeObserver( sync );
		observer.observe( scroller );
		const table = scroller.querySelector( 'table' );
		if ( table ) {
			observer.observe( table );
		}
		return () => {
			observer.disconnect();
			scroller.removeEventListener( 'focus', showRing );
			scroller.removeEventListener( 'blur', hideRing );
			hideRing();
		};
	}, [ label ] );

	return <div ref={ wrapperRef }>{ children }</div>;
};

export default ScrollableTable;
