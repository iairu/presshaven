import { useCallback, useId } from '@wordpress/element';
import { Button, Dialog, Loader } from '@bsf/force-ui';
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline';
import { __ } from '@wordpress/i18n';

import { cn } from '@Utils/helper';

/**
 * @param {Object}   props
 * @param {boolean}  props.open
 * @param {Function} props.setOpen
 * @param {Object}   [props.trigger]       Element that opens the dialog. Passing it (rather than
 *                                         opening via `open` alone) lets the dialog return focus
 *                                         to it on close.
 * @param {string}   props.title
 * @param {string}   props.description
 * @param {string}   props.confirmLabel
 * @param {Function} props.onConfirm
 * @param {string}   [props.cancelLabel]
 * @param {Function} [props.onCancel]      Defaults to just closing the dialog.
 * @param {boolean}  [props.isConfirming]  Loading state for the confirm button, shown as a spinner.
 *                                         While set, the dialog can't be dismissed, so the
 *                                         merchant can't "cancel" an action that's already running.
 * @param {boolean}  [props.isDestructive] Red confirm button and a warning icon beside the title,
 *                                         for deletes and other actions that can't be undone.
 */
const ConfirmDialog = ( {
	open,
	setOpen,
	trigger,
	title,
	description,
	confirmLabel,
	onConfirm,
	cancelLabel = __( 'Cancel', 'woo-cart-abandonment-recovery' ),
	onCancel,
	isConfirming = false,
	isDestructive = false,
} ) => {
	// Tailwind is scoped to #wcar-admin-app, so a portal to <body> renders unstyled.
	const portalRoot = document.getElementById( 'wcar-admin-app' );
	const titleId = useId();
	const descriptionId = useId();

	const requestOpen = ( next ) => {
		if ( isConfirming && ! next ) {
			return;
		}
		setOpen( next );
	};

	// Force UI's Dialog.Panel takes no ARIA props and nests two role="dialog" nodes, neither
	// named, so screen readers announce a bare "dialog" twice. Name the inner one — it holds
	// focus and the content — and demote the outer wrapper to presentation.
	const labelDialog = useCallback(
		( node ) => {
			const panel = node?.closest( '[role="dialog"][id]' );
			if ( ! panel ) {
				return;
			}
			panel.setAttribute( 'aria-labelledby', titleId );
			panel.setAttribute( 'aria-describedby', descriptionId );
			panel.setAttribute( 'aria-modal', 'true' );

			const outer = panel.parentElement?.closest( '[role="dialog"]' );
			if ( outer ) {
				outer.setAttribute( 'role', 'presentation' );
				outer.removeAttribute( 'aria-modal' );
			}
		},
		[ titleId, descriptionId ]
	);

	return (
		<Dialog
			exitOnEsc
			exitOnClickOutside={ false }
			scrollLock
			design="simple"
			open={ open }
			setOpen={ requestOpen }
			{ ...( trigger && { trigger } ) }
		>
			<Dialog.Portal root={ portalRoot }>
				<Dialog.Panel className="relative max-w-[calc(100vw-2.5rem)]">
					<Dialog.Header>
						<Dialog.Title
							id={ titleId }
							className={ cn(
								'pr-9',
								isDestructive && 'flex items-start gap-2'
							) }
						>
							{ isDestructive && (
								<ExclamationTriangleIcon
									className="mt-0.5 size-5 shrink-0 text-support-error"
									aria-hidden="true"
								/>
							) }
							{ title }
						</Dialog.Title>
						<Dialog.Description id={ descriptionId }>
							{ description }
						</Dialog.Description>
					</Dialog.Header>
					<Dialog.Footer className="flex-wrap">
						<Button
							variant="outline"
							size="sm"
							className="max-sm:grow max-sm:min-h-11"
							disabled={ isConfirming }
							onClick={ onCancel || ( () => setOpen( false ) ) }
						>
							{ cancelLabel }
						</Button>
						<Button
							variant="primary"
							size="sm"
							destructive={ isDestructive }
							className={ cn(
								'max-sm:grow max-sm:min-h-11',
								isConfirming && 'cursor-wait opacity-80'
							) }
							icon={
								isConfirming ? (
									<Loader variant="secondary" size="sm" />
								) : null
							}
							iconPosition="left"
							// Not `disabled`: Force UI greys a disabled button out, which would drop the
							// red of a destructive action and drag focus off it. Clicks are ignored instead.
							aria-disabled={ isConfirming }
							aria-busy={ isConfirming }
							onClick={ isConfirming ? undefined : onConfirm }
						>
							{ confirmLabel }
						</Button>
					</Dialog.Footer>
					{ /* After the footer in the DOM, so focus lands on Cancel when the dialog
					     opens rather than on this; positioned back into the header corner. */ }
					<div
						ref={ labelDialog }
						className="absolute top-5 right-5 max-sm:top-2 max-sm:right-2"
					>
						<Dialog.CloseButton
							className="rounded-md max-sm:p-3.5 focus-visible:ring-2 focus-visible:ring-focus disabled:cursor-not-allowed disabled:opacity-50"
							disabled={ isConfirming }
							aria-label={ __(
								'Close dialog',
								'woo-cart-abandonment-recovery'
							) }
						/>
					</div>
				</Dialog.Panel>
				<Dialog.Backdrop />
			</Dialog.Portal>
		</Dialog>
	);
};

export default ConfirmDialog;
