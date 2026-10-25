import {
	createContext,
	useContext,
	useEffect,
	useReducer,
	useRef,
} from '@wordpress/element';

import {
	clearPersistedState,
	readPersistedState,
	writePersistedState,
} from './Persist';

const OnboardingContext = createContext();

/**
 * How long to sit on a change before writing the snapshot.
 *
 * This fires on every keystroke and checkbox click, and each run reads and
 * rewrites the whole snapshot, so an unthrottled version costs a JSON pass
 * per change. Short enough that any real pause commits the answer.
 */
const PERSIST_DEBOUNCE_MS = 400;

const buildInitialState = () => {
	const persisted = readPersistedState();

	return {
		userDetails: {
			...cart_abandonment_admin.onboarding.defaults[ 'user-details' ],
			...persisted.userDetails,
		},
		plugins: {
			...cart_abandonment_admin.onboarding.defaults.plugins,
			...persisted.plugins,
		},
		hasSkippedUserDetails: persisted.hasSkippedUserDetails || false,
	};
};

const onboardingReducer = ( state, action ) => {
	switch ( action.type ) {
		case 'UPDATE_USER_DATA':
			return {
				...state,
				userDetails: {
					...state.userDetails,
					[ action.payload.option ]: action.payload.value,
				},
				// Typing again after Skip means they changed their mind.
				hasSkippedUserDetails: false,
			};

		case 'CONTINUE_USER_DETAILS':
			return {
				...state,
				hasSkippedUserDetails: false,
			};

		case 'SKIP_USER_DETAILS':
			return {
				...state,
				hasSkippedUserDetails: true,
			};

		case 'UPDATE_PLUGIN_DATA':
			return {
				...state,
				plugins: {
					...state.plugins,
					[ action.payload.option ]: action.payload.value,
				},
			};

		default:
			return state;
	}
};

export const OnboardingProvider = ( { children } ) => {
	const [ state, dispatch ] = useReducer(
		onboardingReducer,
		undefined,
		buildInitialState
	);

	// Set once onboarding finishes, so a debounced write already in flight can't
	// land after the snapshot is cleared and resurrect stale pre-finish answers.
	const isCompletedRef = useRef( false );

	// Keeps answers recoverable after an exit-and-resume in the same browser.
	useEffect( () => {
		const timer = window.setTimeout( () => {
			// Checked when the timer actually fires, not just when it's scheduled:
			// finishing doesn't change `state`, so it can't re-run this effect to
			// cancel a write already in flight — only the callback itself sees it.
			if ( isCompletedRef.current ) {
				return;
			}
			writePersistedState( state );
		}, PERSIST_DEBOUNCE_MS );

		return () => window.clearTimeout( timer );
	}, [ state ] );

	const markOnboardingComplete = () => {
		isCompletedRef.current = true;
		clearPersistedState();
	};

	// What this visit to the wizard has installed so far, keyed by plugin slug.
	//
	// Lives here rather than in `state` (persisted to localStorage) or as a plain
	// module-level object in AddOns.js: Back from the Done screen remounts that
	// step, and a fresh mount seeded only from the page-load status would report
	// a plugin this session just installed as its old, stale status. Tied to this
	// Provider instance — not the module — so it never outlives one wizard visit
	// and isn't mistaken for state that should survive a page reload.
	const pluginInstallStatusRef = useRef( {} );

	const value = {
		state,
		dispatch,
		markOnboardingComplete,
		pluginInstallStatusRef,
	};

	return (
		<OnboardingContext.Provider value={ value }>
			{ children }
		</OnboardingContext.Provider>
	);
};

export const useOnboardingContext = () => {
	const context = useContext( OnboardingContext );
	if ( ! context ) {
		throw new Error(
			'useOnboardingContext must be used within OnboardingProvider'
		);
	}
	return context;
};
