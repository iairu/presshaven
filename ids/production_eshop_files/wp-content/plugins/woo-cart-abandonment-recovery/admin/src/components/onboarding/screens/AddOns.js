import { useEffect, useRef, useState } from 'react';
import { Checkbox, Loader } from '@bsf/force-ui';
import { __, sprintf } from '@wordpress/i18n';
import { CheckIcon, PuzzlePieceIcon } from '@heroicons/react/24/outline';

import ErrorBanner from '@Components/onboarding/ErrorBanner';
import Header from '@Components/onboarding/Header';
import NavigationButtons from '@Components/onboarding/NavigationButtons';
import { doApiFetch } from '@Store';
import { useOnboardingContext } from '../OnboardingContext';
import { useOnboardingNavigation } from '../hooks';

const addonsPlugins = cart_abandonment_admin.extend_plugins;

const STATUS_DISPLAY = {
	'not-installed': {
		label: __( 'Not installed', 'woo-cart-abandonment-recovery' ),
		dot: '',
		text: 'text-text-secondary',
	},
	inactive: {
		label: __( 'Not activated', 'woo-cart-abandonment-recovery' ),
		dot: 'bg-support-warning',
		text: 'text-text-secondary',
	},
	installing: {
		label: __( 'Installing…', 'woo-cart-abandonment-recovery' ),
		dot: '',
		text: 'text-flamingo-500',
	},
	'install-failed': {
		label: __( 'Install failed', 'woo-cart-abandonment-recovery' ),
		dot: 'bg-support-error',
		text: 'text-support-error',
	},
	'activate-failed': {
		label: __( 'Activation failed', 'woo-cart-abandonment-recovery' ),
		dot: 'bg-support-error',
		text: 'text-support-error',
	},
	active: {
		label: __( 'Active', 'woo-cart-abandonment-recovery' ),
		dot: 'bg-support-success',
		text: 'text-support-success',
	},
};

const PluginRow = ( { plugin, isLast } ) => {
	const display =
		STATUS_DISPLAY[ plugin.status ] || STATUS_DISPLAY[ 'not-installed' ];
	const isActive = 'active' === plugin.status;
	const isWorking = 'installing' === plugin.status;
	// While the run is under way the list is a progress report, not a form.
	const isLocked = isActive || plugin.busy;

	let indicator = (
		// eslint-disable-next-line jsx-a11y/no-static-element-interactions -- only stops the click from also bubbling to the row's own toggle handler below.
		<span
			className="flex"
			onClick={ ( event ) => event.stopPropagation() }
			role="presentation"
		>
			<Checkbox
				size="sm"
				checked={ !! plugin.checked }
				disabled={ plugin.busy }
				onChange={ plugin.onChange }
				aria-label={ sprintf(
					/* translators: %s: plugin name. */
					__( 'Install %s', 'woo-cart-abandonment-recovery' ),
					plugin.title
				) }
			/>
		</span>
	);

	if ( isWorking ) {
		indicator = <Loader variant="primary" size="sm" />;
	} else if ( isActive ) {
		// A circle, where the selection control is a rounded square: the shape
		// is what separates "already done, nothing to do" from "you chose
		// this, it will be installed".
		indicator = (
			<span className="size-5 rounded-full bg-badge-background-green flex items-center justify-center">
				<CheckIcon
					className="size-3 stroke-[3] text-support-success"
					aria-hidden="true"
				/>
			</span>
		);
	}

	return (
		// eslint-disable-next-line jsx-a11y/no-static-element-interactions, jsx-a11y/click-events-have-key-events -- the row is a click-to-toggle convenience alongside the checkbox, not the only way to reach it.
		<div
			className={ `flex items-start sm:items-center gap-3.5 px-4 py-3.5 ${
				! isLast
					? 'border-0 border-b border-solid border-border-subtle'
					: ''
			} ${ isActive ? 'opacity-70' : '' } ${
				! isLocked
					? 'cursor-pointer hover:bg-background-secondary'
					: ''
			}` }
			onClick={ () => {
				if ( ! isLocked ) {
					plugin.onChange( ! plugin.checked );
				}
			} }
			role="presentation"
		>
			<span className="size-5 shrink-0 flex items-center justify-center">
				{ indicator }
			</span>

			{ /* Fixed tile so a transparent glyph and a solid square read as the
			     same weight, and the row never reflows while logos load. */ }
			<span className="relative size-8 shrink-0 rounded-lg border border-solid border-border-subtle bg-background-primary flex items-center justify-center overflow-hidden">
				<PuzzlePieceIcon
					className="size-4 text-icon-secondary"
					aria-hidden="true"
				/>
				<img
					src={ plugin.logo }
					alt=""
					width={ 32 }
					height={ 32 }
					loading="lazy"
					className="absolute inset-0 size-full object-contain p-0.5 box-border bg-background-primary"
					onError={ ( event ) => {
						event.currentTarget.style.display = 'none';
					} }
				/>
			</span>

			{ /* The status keeps its own column from `sm` up, and drops below
			     the description on a phone rather than squeezing it into a
			     multi-line ribbon. */ }
			<span className="flex-1 min-w-0 flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-3">
				<span className="flex-1 min-w-0 flex flex-col gap-0.5">
					<span className="text-sm font-semibold text-text-primary">
						{ plugin.title }
					</span>
					<span className="text-sm font-normal text-text-secondary">
						{ plugin.desc }
					</span>
					{ plugin.error && (
						<span className="text-xs font-normal text-support-error">
							{ plugin.error }
						</span>
					) }
				</span>

				<span
					className={ `shrink-0 flex items-center gap-1.5 text-xs font-medium whitespace-nowrap ${ display.text }` }
				>
					{ display.dot && (
						<span
							className={ `size-1.5 rounded-full ${ display.dot }` }
							aria-hidden="true"
						/>
					) }
					{ display.label }
				</span>
			</span>
		</div>
	);
};

/**
 * An Error that records which step failed, so a retry starts from that step.
 *
 * @param {string} stage   `install` or `activate`.
 * @param {string} message Server message, if it sent one.
 * @return {Error} The error, with `stage` set.
 */
const stageError = ( stage, message ) =>
	Object.assign( new Error( message || '' ), { stage } );

/**
 * Activate an already-installed plugin.
 *
 * Shares the same AJAX action (and the same silent-activation guard) as the
 * dashboard's "Extend Your Website" cards, rather than a wizard-only endpoint.
 *
 * @param {string} path Plugin file path, e.g. `cartflows/cartflows.php`.
 * @return {Promise<void>} Resolves on success, rejects with an Error tagged `stage: 'activate'` otherwise.
 */
const activatePlugin = ( path ) =>
	new Promise( ( resolve, reject ) => {
		const formData = new window.FormData();
		formData.append( 'action', 'cart_abandonment_activate_plugin' );
		formData.append( 'init', path );
		formData.append(
			'security',
			cart_abandonment_admin.plugin_activation_nonce
		);

		doApiFetch(
			cart_abandonment_admin.ajax_url,
			formData,
			'POST',
			( response ) => {
				if ( response?.success ) {
					resolve();
					return;
				}
				reject( stageError( 'activate', response?.data?.message ) );
			},
			( error ) =>
				reject( stageError( 'activate', error?.data?.message ) ),
			true
		).catch( () => {} ); // Rejection already reaches us through `reject`.
	} );

/**
 * Install, then activate, one plugin.
 *
 * One request per plugin — and per step — is what makes the progress real: a
 * single request for the whole list left the merchant watching a disabled
 * button with no idea which plugin was being fetched, or whether anything was
 * happening at all.
 *
 * @param {Object} plugin Entry from `cart_abandonment_admin.extend_plugins`.
 * @return {Promise<void>} Resolves once the plugin is active, rejects with an Error that records the failed `stage`.
 */
const installPlugin = ( plugin ) => {
	// A download that failed has nothing on disk to activate, so it starts over.
	if (
		'not-installed' !== plugin.status &&
		'install-failed' !== plugin.status
	) {
		return activatePlugin( plugin.path );
	}

	return new Promise( ( resolve, reject ) => {
		const formData = new window.FormData();
		formData.append( 'action', 'cart_abandonment_install_plugin' );
		formData.append( 'slug', plugin.slug );
		formData.append(
			'_ajax_nonce',
			cart_abandonment_admin.plugin_installer_nonce
		);

		doApiFetch(
			cart_abandonment_admin.ajax_url,
			formData,
			'POST',
			( response ) => {
				if ( ! response?.success ) {
					reject( stageError( 'install', response?.data?.errorMessage ) );
					return;
				}
				resolve( activatePlugin( plugin.path ) );
			},
			( error ) =>
				reject( stageError( 'install', error?.data?.errorMessage ) ),
			true
		).catch( () => {} ); // Rejection already reaches us through `reject`.
	} );
};

/**
 * Screen-reader-only progress announcement.
 *
 * The row spinners and the button label are both silent to a screen reader —
 * a changed button label is not announced. This is the only running
 * commentary those merchants get on the one step that writes to their site.
 *
 * @param {Object} progress `{ done, total }`.
 * @return {string} Announcement text.
 */
const installProgressAnnouncement = ( progress ) =>
	sprintf(
		/* translators: 1: plugin being installed, 2: total to install. */
		__( 'Installing plugin %1$d of %2$d.', 'woo-cart-abandonment-recovery' ),
		Math.min( progress.done + 1, progress.total ),
		progress.total
	);

const AddOns = () => {
	const { state, dispatch, markOnboardingComplete, pluginInstallStatusRef } =
		useOnboardingContext();
	const plugins = state.plugins;
	const { completeOnboarding, navigateToNextRoute } =
		useOnboardingNavigation();

	// Live state per plugin, seeded from what this session already installed
	// and then from what the server found on page load.
	const [ statuses, setStatuses ] = useState( () =>
		Object.fromEntries(
			addonsPlugins.map( ( plugin ) => [
				plugin.slug,
				pluginInstallStatusRef.current[ plugin.slug ] || plugin.status,
			] )
		)
	);
	// { done, total } while installing, null otherwise.
	const [ progress, setProgress ] = useState( null );
	const [ isFinishing, setIsFinishing ] = useState( false );
	const [ finishError, setFinishError ] = useState( '' );
	// Server message per plugin that failed, and the names to list in the banner.
	const [ pluginErrors, setPluginErrors ] = useState( {} );
	const [ failedTitles, setFailedTitles ] = useState( [] );

	// Nothing to install — save the answers and move on rather than showing
	// an actionless step.
	const allAddonsActive = addonsPlugins.every(
		( plugin ) => 'active' === plugin.status
	);
	const autoAdvanceStarted = useRef( false );

	const finish = ( onboardingState ) => {
		setIsFinishing( true );
		setFinishError( '' );
		completeOnboarding( onboardingState )
			.then( ( response ) => {
				// admin-ajax answers a refusal with HTTP 200 and success:false, which
				// apiFetch resolves normally — without this check a rejected save would
				// still navigate to Done as if onboarding had actually completed.
				if ( false === response?.success ) {
					throw new Error( response?.data?.message || '' );
				}
				markOnboardingComplete();
				navigateToNextRoute( { replace: true } );
			} )
			.catch( () => {
				setIsFinishing( false );
				setFinishError(
					__(
						'Check your connection and try again.',
						'woo-cart-abandonment-recovery'
					)
				);
			} );
	};

	useEffect( () => {
		if ( ! allAddonsActive || autoAdvanceStarted.current ) {
			return;
		}
		autoAdvanceStarted.current = true;
		finish( state );
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [] );

	// The auto-advance above is one-shot, so a refused save used to leave the
	// spinner turning for good with nothing on the step able to move.
	if ( allAddonsActive && finishError ) {
		return (
			<>
				<Header
					heading={ __( 'Almost There', 'woo-cart-abandonment-recovery' ) }
					subHeading={ __(
						'Every recommended plugin is already active, so there was nothing to install. Saving your answers is all that is left.',
						'woo-cart-abandonment-recovery'
					) }
				/>
				<ErrorBanner
					title={ __(
						'Could not finish setup',
						'woo-cart-abandonment-recovery'
					) }
					content={ finishError }
				/>
				<NavigationButtons
					nextLabel={ __( 'Try Again', 'woo-cart-abandonment-recovery' ) }
					nextLoading={ isFinishing }
					onNext={ () => finish( state ) }
				/>
			</>
		);
	}

	if ( allAddonsActive ) {
		return (
			<div className="flex flex-col items-center justify-center gap-3 p-8">
				<Loader variant="primary" size="lg" />
				<p className="m-0 text-sm text-text-secondary">
					{ __( 'Finishing setup…', 'woo-cart-abandonment-recovery' ) }
				</p>
			</div>
		);
	}

	const selectable = addonsPlugins.filter(
		( plugin ) => 'active' !== statuses[ plugin.slug ]
	);
	const selectedCount = selectable.filter(
		( plugin ) => plugins[ plugin.slug ]
	).length;

	/**
	 * Install the chosen plugins one at a time, then finish onboarding.
	 */
	const installThenFinish = async () => {
		// Carries the *live* status (not `selectable`'s page-load snapshot) into
		// installPlugin(), so retrying after a failed activation only retries the
		// activation instead of running the full install again.
		const queue = selectable
			.filter( ( plugin ) => plugins[ plugin.slug ] )
			.map( ( plugin ) => ( {
				...plugin,
				status: statuses[ plugin.slug ],
			} ) );

		setProgress( { done: 0, total: queue.length } );
		setFailedTitles( [] );
		setPluginErrors( {} );

		const failed = [];

		for ( let index = 0; index < queue.length; index++ ) {
			const plugin = queue[ index ];

			setStatuses( ( prev ) => ( {
				...prev,
				[ plugin.slug ]: 'installing',
			} ) );

			try {
				// eslint-disable-next-line no-await-in-loop
				await installPlugin( plugin );
				pluginInstallStatusRef.current[ plugin.slug ] = 'active';
				setStatuses( ( prev ) => ( {
					...prev,
					[ plugin.slug ]: 'active',
				} ) );
			} catch ( error ) {
				const failedStatus =
					'install' === error?.stage
						? 'install-failed'
						: 'activate-failed';
				pluginInstallStatusRef.current[ plugin.slug ] = failedStatus;
				setStatuses( ( prev ) => ( {
					...prev,
					[ plugin.slug ]: failedStatus,
				} ) );
				setPluginErrors( ( prev ) => ( {
					...prev,
					[ plugin.slug ]: error?.message || '',
				} ) );
				failed.push( plugin.title );
				// Untick it so the next press doesn't retry it behind a spinner:
				// the merchant ticks it again to try once more.
				dispatch( {
					type: 'UPDATE_PLUGIN_DATA',
					payload: { option: plugin.slug, value: false },
				} );
			}

			setProgress( { done: index + 1, total: queue.length } );
		}

		setProgress( null );

		// Stay here: moving on to Done would bury the failure under a success page.
		if ( failed.length ) {
			setFailedTitles( failed );
			return;
		}

		finish( state );
	};

	/**
	 * Label the primary button with whatever the wizard is doing right now.
	 *
	 * @return {string} Button label.
	 */
	const nextLabel = () => {
		if ( progress ) {
			return sprintf(
				/* translators: 1: plugin being installed, 2: total to install. */
				__( 'Installing %1$d of %2$d…', 'woo-cart-abandonment-recovery' ),
				Math.min( progress.done + 1, progress.total ),
				progress.total
			);
		}

		if ( isFinishing ) {
			return __( 'Setting things up…', 'woo-cart-abandonment-recovery' );
		}

		if ( selectedCount ) {
			return sprintf(
				/* translators: %d: number of selected plugins. */
				__( 'Install %d & Finish', 'woo-cart-abandonment-recovery' ),
				selectedCount
			);
		}

		return __( 'Finish Setup', 'woo-cart-abandonment-recovery' );
	};

	return (
		<>
			<Header
				heading={ __(
					'Add More Power to Your Website',
					'woo-cart-abandonment-recovery'
				) }
				subHeading={ __(
					'These tools can help you build your website faster and easier. Try them out and see how they can help your website grow.',
					'woo-cart-abandonment-recovery'
				) }
			/>

			{ failedTitles.length > 0 && (
				<ErrorBanner
					title={ __(
						'Some plugins could not be set up',
						'woo-cart-abandonment-recovery'
					) }
					content={ sprintf(
						/* translators: %s: comma-separated plugin names. */
						__(
							'%s. Tick a plugin to try it again, or select Finish Setup to continue without it.',
							'woo-cart-abandonment-recovery'
						),
						failedTitles.join( ', ' )
					) }
				/>
			) }

			{ finishError && (
				<ErrorBanner
					title={ __(
						'Could not finish setup',
						'woo-cart-abandonment-recovery'
					) }
					content={ finishError }
				/>
			) }

			<div className="border border-solid border-border-subtle rounded-lg overflow-hidden">
				{ addonsPlugins.map( ( plugin, index ) => (
					<PluginRow
						key={ plugin.slug }
						isLast={ index === addonsPlugins.length - 1 }
						plugin={ {
							...plugin,
							status: statuses[ plugin.slug ],
							error: pluginErrors[ plugin.slug ],
							busy: !! progress || isFinishing,
							checked: !! plugins[ plugin.slug ],
							onChange: ( value ) =>
								dispatch( {
									type: 'UPDATE_PLUGIN_DATA',
									payload: { option: plugin.slug, value },
								} ),
						} }
					/>
				) ) }
			</div>

			<span className="sr-only" role="status" aria-live="polite">
				{ progress && installProgressAnnouncement( progress ) }
			</span>

			<NavigationButtons
				nextLoading={ !! progress || isFinishing }
				nextLabel={ nextLabel() }
				onNext={ installThenFinish }
			/>
		</>
	);
};

export default AddOns;
