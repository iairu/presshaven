import { useCallback, useEffect, useRef } from '@wordpress/element';
import { Button, Drawer } from '@bsf/force-ui';
import { CheckIcon } from '@heroicons/react/24/outline';
import { __ } from '@wordpress/i18n';

import { truncateText } from './templateDrawerUtils';
import { useTemplateDrawer } from './TemplateDrawerShell';

// How long after opening focus may still be redirected to the name field. Force UI hands the
// panel to its focus manager 0.3s after opening.
const FOCUS_REDIRECT_MS = 700;

/**
 * Title bar of a template drawer: the template's name, Save, and Close.
 *
 * Also names the drawer for assistive tech and, once the drawer has settled, puts focus on the
 * template-name field rather than leaving it on Save.
 *
 * @param {Object}   props
 * @param {string}   props.title        Heading text.
 * @param {boolean}  props.isSubmitting Whether a save is in flight.
 * @param {Function} props.onSave       Called when Save is pressed.
 * @return {JSX.Element} The drawer header.
 */
const TemplateDrawerHeader = ( { title, isSubmitting, onSave } ) => {
	const { titleId, isDiscarding, isSaved, keepEditing, discardChanges } =
		useTemplateDrawer();
	const anchor = useRef( null );
	const keepRef = useRef( null );
	const askedFrom = useRef( null );

	// Force UI's panel is labelled just "drawer" and takes no ARIA props, so name it from the
	// title here (the same approach ConfirmDialog takes for its dialog).
	const nameDialog = useCallback(
		( node ) => {
			anchor.current = node;
			const panel = node?.closest( '[role="dialog"]' );
			if ( ! panel ) {
				return;
			}
			panel.removeAttribute( 'aria-label' );
			panel.setAttribute( 'aria-labelledby', titleId );
		},
		[ titleId ]
	);

	useEffect( () => {
		const doc = anchor.current?.ownerDocument;
		if ( ! doc ) {
			return undefined;
		}
		const focusName = () =>
			doc
				.querySelector( '[role="dialog"] input[name="template_name"]' )
				?.focus( { preventScroll: true } );

		// Force UI's focus manager lands on the first control, which is Save, once the slide-in
		// ends. Hand that straight to the name field so focus moves once, not Save then name.
		const redirectFromSave = ( event ) => {
			if ( event.target.hasAttribute?.( 'data-template-save' ) ) {
				focusName();
			}
		};
		doc.addEventListener( 'focusin', redirectFromSave, true );
		const stopRedirect = setTimeout(
			() => doc.removeEventListener( 'focusin', redirectFromSave, true ),
			FOCUS_REDIRECT_MS
		);

		// Fallback for when focus was never moved into the drawer.
		const timer = setTimeout( () => {
			if ( ! doc.activeElement?.closest( '[role="dialog"]' ) ) {
				focusName();
			}
		}, FOCUS_REDIRECT_MS );

		return () => {
			doc.removeEventListener( 'focusin', redirectFromSave, true );
			clearTimeout( stopRedirect );
			clearTimeout( timer );
		};
	}, [] );

	// Move focus onto the question when it appears, and back to where it was when it goes.
	useEffect( () => {
		const doc = anchor.current?.ownerDocument;
		if ( isDiscarding ) {
			askedFrom.current = doc?.activeElement;
			keepRef.current?.focus();
		} else if ( askedFrom.current ) {
			askedFrom.current.focus?.();
			askedFrom.current = null;
		}
	}, [ isDiscarding ] );

	let saveLabel = __( 'Save Changes', 'woo-cart-abandonment-recovery' );
	if ( isSubmitting ) {
		saveLabel = __( 'Saving…', 'woo-cart-abandonment-recovery' );
	} else if ( isSaved ) {
		saveLabel = __( 'Saved', 'woo-cart-abandonment-recovery' );
	}

	// Only confirms a save that just went through; it goes again after a few seconds.
	const saveIcon = isSaved ? (
		<CheckIcon className="h-4 w-4" aria-hidden="true" />
	) : null;

	return (
		<Drawer.Header className="flex flex-col gap-2 z-10 bg-white">
			<span ref={ nameDialog } hidden />
			<div className="flex items-center justify-between">
				<Drawer.Title id={ titleId } className="text-lg text-gray-900 z-10">
					{ truncateText( title ) }
				</Drawer.Title>
				<div className="flex items-center gap-3">
					<Button
						className="whitespace-nowrap hidden xs:flex [@media(pointer:coarse)]:min-h-11"
						icon={ saveIcon }
						iconPosition="left"
						size="sm"
						tag="button"
						type="button"
						variant="primary"
						data-template-save=""
						onClick={ onSave }
						disabled={ isSubmitting }
					>
						{ saveLabel }
					</Button>
					<Drawer.CloseButton className="rounded-md [@media(pointer:coarse)]:p-3.5 focus-visible:ring-2 focus-visible:ring-focus" />
				</div>
			</div>
			{ isDiscarding && (
				<div
					role="alertdialog"
					aria-labelledby={ `${ titleId }-discard` }
					className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-solid border-support-error bg-field-background-error px-3 py-2"
				>
					<p
						id={ `${ titleId }-discard` }
						className="m-0 text-sm text-text-primary"
					>
						{ __(
							'Discard your changes? They have not been saved.',
							'woo-cart-abandonment-recovery'
						) }
					</p>
					<div className="flex gap-2">
						<Button
							ref={ keepRef }
							className="[@media(pointer:coarse)]:min-h-11"
							size="xs"
							type="button"
							variant="outline"
							onClick={ keepEditing }
						>
							{ __( 'Keep editing', 'woo-cart-abandonment-recovery' ) }
						</Button>
						<Button
							className="[@media(pointer:coarse)]:min-h-11"
							size="xs"
							type="button"
							variant="primary"
							destructive
							onClick={ discardChanges }
						>
							{ __(
								'Discard changes',
								'woo-cart-abandonment-recovery'
							) }
						</Button>
					</div>
				</div>
			) }
			<Button
				className="xs:hidden min-h-11"
				icon={ saveIcon }
				iconPosition="left"
				size="sm"
				tag="button"
				type="button"
				variant="primary"
				data-template-save=""
				onClick={ onSave }
				disabled={ isSubmitting }
			>
				{ saveLabel }
			</Button>
		</Drawer.Header>
	);
};

export default TemplateDrawerHeader;
