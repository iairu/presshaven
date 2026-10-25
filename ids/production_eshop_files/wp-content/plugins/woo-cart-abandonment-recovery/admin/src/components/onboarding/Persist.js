/**
 * Client-only snapshot of in-progress onboarding answers.
 *
 * Only what the wizard can't already recover from the server: the settings
 * steps save to the database on Next, but the user-details fields and the
 * add-ons selection live in OnboardingContext only, so an exit-and-resume in
 * the same browser needs somewhere to keep them.
 *
 * Versioned so a snapshot from a previous release with a different shape is
 * ignored rather than fed into state it doesn't match.
 */
const STORAGE_KEY = 'wcar_onboarding_answers';
const SCHEMA_VERSION = 1;

/**
 * @return {Object} The persisted answers, or `{}` if there is nothing usable.
 */
export const readPersistedState = () => {
	try {
		const raw = window.localStorage.getItem( STORAGE_KEY );

		if ( ! raw ) {
			return {};
		}

		const parsed = JSON.parse( raw );

		if ( parsed?.schemaVersion !== SCHEMA_VERSION ) {
			return {};
		}

		return parsed;
	} catch ( error ) {
		return {};
	}
};

/**
 * @param {Object} state Answers to persist.
 */
export const writePersistedState = ( state ) => {
	try {
		window.localStorage.setItem(
			STORAGE_KEY,
			JSON.stringify( { ...state, schemaVersion: SCHEMA_VERSION } )
		);
	} catch ( error ) {
		// Private browsing, storage disabled, or quota exceeded — the wizard still
		// works, it just won't survive an exit-and-resume in this browser.
	}
};

export const clearPersistedState = () => {
	try {
		window.localStorage.removeItem( STORAGE_KEY );
	} catch ( error ) {
		// Nothing to clean up if it couldn't be read in the first place.
	}
};
