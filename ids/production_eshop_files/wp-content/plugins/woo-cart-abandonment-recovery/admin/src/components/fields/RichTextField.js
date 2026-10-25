import { useEffect, useState } from 'react';
import { Label, Button, Tabs } from '@bsf/force-ui';
import { ArrowUpTrayIcon } from '@heroicons/react/24/outline';
import { __ } from '@wordpress/i18n';

import SkeletonLoader from '@Components/common/skeletons/SkeletonLoader';
import { cn } from '@Utils/helper';
import { FieldError } from '@Components/common/fieldA11y';

// Height of the booted editor (toolbar plus the 17-row textarea it takes its size from), held
// by the placeholder so the page doesn't jump when TinyMCE replaces it.
const EDITOR_PLACEHOLDER_HEIGHT = '28rem';

// `initDelay` (ms) holds back booting TinyMCE, the heaviest thing on the main thread, so a
// field inside a sliding drawer can wait for the slide to finish.
const RichTextField = ( {
	title,
	name,
	id,
	value,
	handleChange,
	size = 'normal',
	initDelay = 0,
	error,
} ) => {
	const [ activeTab, setActiveTab ] = useState( 'visual' );
	const [ isEditorReady, setIsEditorReady ] = useState( false );
	useEffect( () => {
		const onEditorSetup = function ( event, editor ) {
			if ( editor.id !== id ) {
				return;
			}
			// TinyMCE normalises the HTML it is given, so compare against what it reported once
			// booted: otherwise a bare keypress (an arrow key) reads as an edit.
			let lastContent = '';
			editor.on( 'init', () => {
				lastContent = editor.getContent();
				setIsEditorReady( true );
			} );
			const report = () => {
				const content = editor.getContent();
				if ( content !== lastContent ) {
					lastContent = content;
					handleChange( name, content );
				}
			};
			editor.settings.toolbar1 =
						'formatselect,wcar_fields,bold,italic,underline,blockquote,strikethrough,bullist,numlist,alignleft,aligncenter,alignright,undo,redo,link,unlink,spellchecker,fullscreen';
			editor.on( 'change', report );
			editor.on( 'keyup', report );
			editor.settings.forced_root_block = false;

			if ( 'email_body' === name ) {
				editor.addButton( 'wcar_fields', {
					type: 'menubutton',
					text: 'WCAR Fields',
					icon: '',
					classes: 'listbox',
					menu: [
						{
							text: 'Abandoned Product Details Table',
							value: '{{cart.product.table}}',
							onclick() {
								editor.insertContent( this.value() );
							},
						},
						{
							text: 'Abandoned Product Names',
							value: '{{cart.product.names}}',
							onclick() {
								editor.insertContent( this.value() );
							},
						},
						{
							text: 'Admin Firstname',
							value: '{{admin.firstname}}',
							onclick() {
								editor.insertContent( this.value() );
							},
						},
						{
							text: 'Admin Company',
							value: '{{admin.company}}',
							onclick() {
								editor.insertContent( this.value() );
							},
						},
						{
							text: 'Cart Checkout URL',
							value: '{{cart.checkout_url}}',
							onclick() {
								editor.insertContent( this.value() );
							},
						},
						{
							text: 'Coupon Code',
							value: '{{cart.coupon_code}}',
							onclick() {
								editor.insertContent( this.value() );
							},
						},
						{
							text: 'Customer First Name',
							value: '{{customer.firstname}}',
							onclick() {
								editor.insertContent( this.value() );
							},
						},
						{
							text: 'Customer Last Name',
							value: '{{customer.lastname}}',
							onclick() {
								editor.insertContent( this.value() );
							},
						},
						{
							text: 'Customer Full Name',
							value: '{{customer.fullname}}',
							onclick() {
								editor.insertContent( this.value() );
							},
						},
						{
							text: 'Cart Abandonment Date',
							value: '{{cart.abandoned_date}}',
							onclick() {
								editor.insertContent( this.value() );
							},
						},
						{
							text: 'Site URL',
							value: '{{site.url}}',
							onclick() {
								editor.insertContent( this.value() );
							},
						},
						{
							text: 'Unsubscribe Link',
							value: '{{cart.unsubscribe}}',
							onclick() {
								editor.insertContent( this.value() );
							},
						},
					].sort( function ( a, b ) {
						return a.text.localeCompare( b.text );
					} ),
				} );
			}
		};

		// Registered per mount, so it has to be removed again: otherwise each open of the
		// drawer stacks another copy that runs for every editor.
		jQuery( document ).on( 'tinymce-editor-setup', onEditorSetup );

		const timer = setTimeout( () => {
			wp.editor.initialize( id, {
				tinymce: true,
				quicktags: true,
				mediaButtons: false,
			} );
		}, initDelay );

		return () => {
			clearTimeout( timer );
			jQuery( document ).off( 'tinymce-editor-setup', onEditorSetup );
			tinymce.get( id )?.destroy();
		};
	}, [] );

	useEffect( () => {
		const editor = tinymce.get( id );
		if ( editor && editor.getContent() !== value ) {
			editor.setContent( value || '' );
		}
	}, [ value, id ] );

	const handleTabChange = ( tab ) => {
		setActiveTab( tab );
		const editor = tinymce.get( id );
		if ( editor ) {
			const container = editor.getContainer();
			const wrapper = container.closest( `#wp-${ id }-wrap` );
			if ( wrapper ) {
				const switchClass =
					tab === 'visual' ? 'switch-tmce' : 'switch-html';
				const modeButton = wrapper.querySelector( `.${ switchClass }` );
				if ( modeButton ) {
					modeButton.click();
				}
			}
		}
	};

	function updateValue( e ) {
		handleChange( name, e.target.value );
	}

	const handleAddMedia = () => {
		if ( typeof wp !== 'undefined' && wp.media ) {
			const mediaUploader = wp.media( {
				title: __( 'Select Media', 'woo-cart-abandonment-recovery' ),
				button: {
					text: __( 'Insert Media', 'woo-cart-abandonment-recovery' ),
				},
				multiple: false,
			} );

			mediaUploader.on( 'select', () => {
				const attachment = mediaUploader
					.state()
					.get( 'selection' )
					.first()
					.toJSON();
				const editor = tinymce.get( id );

				if ( editor ) {
					if (
						attachment.type === 'image' ||
						attachment.subtype === 'gif'
					) {
						editor.insertContent(
							`<img src="${ attachment.url }" alt="${
								attachment.alt || attachment.title || ''
							}" />`
						);
					} else if ( attachment.type === 'video' ) {
						editor.insertContent(
							`<video controls><source src="${ attachment.url }" type="${ attachment.mime }">Your browser does not support the video tag.</video>`
						);
					} else {
						const linkText =
							attachment.title ||
							attachment.filename ||
							'Click to view file';
						editor.insertContent(
							`<a href="${ attachment.url }" target="_blank">${ linkText }</a>`
						);
					}
				}
			} );

			mediaUploader.open();
		} else {
			console.warn( 'wp.media is not available.' );
		}
	};

	const titleId = `${ id }-title`;
	const errorId = `${ id }-error`;

	return (
		<section
			className="flex flex-col py-5 justify-between gap-2 lg:gap-5 border-0 border-b border-solid border-gray-200 last:border-b-0"
			aria-labelledby={ title ? titleId : undefined }
		>
			<div className="flex flex-wrap justify-between items-center gap-2">
				<Label
					className="font-semibold mb-1"
					htmlFor={ id }
					size={ `${ size === 'normal' ? 'md' : 'sm' }` }
					id={ titleId }
				>
					{ title.replace( /\b\w/g, ( char ) =>
						char.toLocaleUpperCase()
					) }
				</Label>
				<div className="flex items-center gap-2 w-fit">
					<Tabs.Group
						variant="rounded"
						size="sm"
						className="p-0 bg-white"
						onChange={ ( { value: val } ) => {
							handleTabChange( val.slug );
						} }
					>
						<Tabs.Tab
							className={ `text-sm font-medium hover:text-primary-600 [@media(pointer:coarse)]:min-h-11 ${
								activeTab === 'visual'
									? 'text-primary-600 bg-primary-25 outline outline-1 outline-primary-300 focus:outline-1'
									: ''
							}` }
							key={ 'visual' }
							text={ __( 'Visual', 'woo-cart-abandonment-recovery' ) }
							slug={ 'visual' }
						/>
						<Tabs.Tab
							className={ `text-sm font-medium hover:text-primary-600 [@media(pointer:coarse)]:min-h-11 ${
								activeTab === 'html'
									? 'text-primary-600 bg-primary-25 outline outline-1 outline-primary-300 focus:outline-1'
									: ''
							}` }
							key={ 'html' }
							text={ __( 'HTML', 'woo-cart-abandonment-recovery' ) }
							slug={ 'html' }
						/>
					</Tabs.Group>
					<Button
						className="px-4 bg-primary-25 text-primary-600 outline-primary-300 hover:bg-primary-25 hover:outline-primary-300 whitespace-nowrap [@media(pointer:coarse)]:min-h-11"
						size="sm"
						tag="button"
						icon={ <ArrowUpTrayIcon className="h-4 w-4" aria-hidden="true" /> }
						iconPosition="left"
						variant="outline"
						onClick={ handleAddMedia }
					>
						{ __( 'Add Media', 'woo-cart-abandonment-recovery' ) }
					</Button>
				</div>
			</div>

			<div
				className={ cn( 'relative', ! isEditorReady && 'overflow-hidden' ) }
				style={ {
					height: isEditorReady ? undefined : EDITOR_PLACEHOLDER_HEIGHT,
				} }
			>
				{ /* TinyMCE takes a moment to boot; show a placeholder of its size rather than a raw HTML textarea that then jumps. The textarea stays laid out (invisible, not display:none) because TinyMCE sizes the editor from it. */ }
				{ ! isEditorReady && (
					<SkeletonLoader
						height="100%"
						className="absolute inset-0 z-10"
					/>
				) }
				<textarea
					name={ name }
					id={ id }
					value={ value }
					rows="17"
					onChange={ updateValue }
					aria-invalid={ error ? true : undefined }
					aria-describedby={ error ? errorId : undefined }
					className={ cn(
						'w-full focus:border-flamingo-400 focus:shadow-sm focus:shadow-flamingo-400 focus:outline-0',
						! isEditorReady && 'invisible'
					) }
				></textarea>
			</div>
			<FieldError id={ errorId }>{ error }</FieldError>
		</section>
	);
};

export default RichTextField;

