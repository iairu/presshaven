import {
	createContext,
	useCallback,
	useContext,
	useEffect,
	useId,
	useLayoutEffect,
	useMemo,
	useRef,
	useState,
} from '@wordpress/element';
import { Drawer } from '@bsf/force-ui';

import { HelpTextBelowContext } from '@Components/common/FieldWrapper';

// Slide-in length in seconds (the Drawer's transitionDuration).
export const DRAWER_TRANSITION_S = 0.2;

// Force UI hands the panel to its focus manager after the slide plus 0.1s, and focuses the
// first control only then. Anything that moves focus waits past that.
const FOCUS_SETTLE_MS = Math.round( ( DRAWER_TRANSITION_S + 0.1 ) * 1000 ) + 50;

// How long the check mark stays on Save after a successful save.
const SAVED_FLASH_MS = 3000;

const DrawerContext = createContext( null );

/**
 * What a form inside the drawer needs from it.
 *
 * @return {Object} The title id, `setDirty` to report unsaved changes (closing then asks first),
 *                  the state of that question, and `markSaved` to report a successful save.
 *                  `TemplateDrawerHeader` shows both.
 */
export const useTemplateDrawer = () => useContext( DrawerContext );

/**
 * Drawer shared by the email, SMS and WhatsApp template forms.
 *
 * Gives every one of them the same behavior: focus returns to what opened the drawer, the
 * panel is named after its title, and closing with unsaved changes asks first.
 *
 * @param {Object}   props
 * @param {boolean}  props.open     Whether the drawer is open.
 * @param {Function} props.setOpen  Opens or closes the drawer.
 * @param {Object}   props.children The form, rendered inside the panel only while open.
 * @return {JSX.Element} The drawer.
 */
const TemplateDrawerShell = ( { open, setOpen, children } ) => {
	const titleId = useId();
	const [ isDiscarding, setIsDiscarding ] = useState( false );
	const [ isSaved, setIsSaved ] = useState( false );
	const savedTimer = useRef( null );
	const dirtyRef = useRef( false );
	const openerRef = useRef( null );
	const lastTouched = useRef( null );

	// Track what the user last focused or clicked: that is what opens the drawer. Safari and
	// Firefox don't focus a button on click, so the click is tracked too.
	useEffect( () => {
		const remember = ( event ) => {
			lastTouched.current =
				event.target.closest?.( 'button, a, [tabindex]' ) || null;
		};
		document.addEventListener( 'click', remember, true );
		document.addEventListener( 'focusin', remember, true );
		return () => {
			document.removeEventListener( 'click', remember, true );
			document.removeEventListener( 'focusin', remember, true );
		};
	}, [] );

	// Put focus back on the opener once the drawer has gone.
	useLayoutEffect( () => {
		if ( open ) {
			openerRef.current = lastTouched.current;
			return undefined;
		}

		dirtyRef.current = false;
		setIsDiscarding( false );
		setIsSaved( false );
		clearTimeout( savedTimer.current );

		const opener = openerRef.current;
		openerRef.current = null;
		if ( ! opener ) {
			return undefined;
		}
		const timer = setTimeout( () => {
			if ( opener.isConnected ) {
				opener.focus();
			}
		}, FOCUS_SETTLE_MS );
		return () => clearTimeout( timer );
	}, [ open ] );

	useEffect( () => () => clearTimeout( savedTimer.current ), [] );

	// Esc, the close button and the backdrop all land here. With unsaved changes the first
	// attempt asks; a second Esc takes the question back.
	const requestClose = useCallback( () => {
		if ( dirtyRef.current ) {
			setIsDiscarding( ( asking ) => ! asking );
			return;
		}
		setOpen( false );
	}, [ setOpen ] );

	const context = useMemo(
		() => ( {
			titleId,
			isDiscarding,
			isSaved,
			markSaved: () => {
				clearTimeout( savedTimer.current );
				setIsSaved( true );
				savedTimer.current = setTimeout(
					() => setIsSaved( false ),
					SAVED_FLASH_MS
				);
			},
			keepEditing: () => setIsDiscarding( false ),
			discardChanges: () => {
				dirtyRef.current = false;
				setIsDiscarding( false );
				setOpen( false );
			},
			setDirty: ( isDirty ) => {
				dirtyRef.current = isDirty;
			},
		} ),
		[ titleId, isDiscarding, isSaved, setOpen ]
	);

	return (
		<DrawerContext.Provider value={ context }>
			<Drawer
				open={ open }
				design="simple"
				exitOnEsc
				position="right"
				scrollLock
				setOpen={ requestClose }
				transitionDuration={ DRAWER_TRANSITION_S }
				className="z-[100000]"
			>
				<Drawer.Panel className="w-full md:w-4/5 lg:w-2/5">
					<HelpTextBelowContext.Provider value={ true }>
						{ children }
					</HelpTextBelowContext.Provider>
				</Drawer.Panel>
				<Drawer.Backdrop />
			</Drawer>
		</DrawerContext.Provider>
	);
};

export default TemplateDrawerShell;
