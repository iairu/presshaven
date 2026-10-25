// Example usage:
// <ProductSearchField
//   title="..."
//   description="..."
//   name="wcf_exclude_product_ids[]"
//   value={value}
//   handleChange={handleChange}
// />
// To prefill, pass a comma-separated string or array of product IDs as value.

import FieldWrapper from '@Components/common/FieldWrapper';
import { Badge, SearchBox } from '@bsf/force-ui';
import { useEffect, useState } from 'react';
import { __ } from '@wordpress/i18n';
import { useFieldA11y } from '@Components/common/fieldA11y';
import { useProAccess } from '@Components/pro/useProAccess';

const ProductSearchField = ( {
	title,
	description,
	name,
	value,
	handleChange,
	disableStyle = false,
	isPro = false,
	proUpgradeMessage = '',
} ) => {
	const a11y = useFieldA11y( { description } );
	const { shouldBlockProFeatures } = useProAccess();
	const isFeatureBlocked = shouldBlockProFeatures();
	const [ selectedProductIDs, setSelectedProductIDs ] = useState( [] );
	const [ selectedProducts, setSelectedProducts ] = useState( [] );
	const [ searchTerm, setSearchTerm ] = useState( '' );
	const [ products, setProducts ] = useState( [] );
	const [ loading, setLoading ] = useState( false );
	const [ open, setOpen ] = useState( false );

	// Load selected products on mount or value change
	useEffect( () => {
		let valueIds = [];
		if ( value && typeof value === 'string' ) {
			valueIds = value.split( ',' );
		}
		setSelectedProductIDs( valueIds );
		loadSelectedProducts( valueIds );
	}, [ value ] );

	useEffect( () => {
		if ( searchTerm.length > 2 ) {
			searchProducts( searchTerm );
		}
	}, [ searchTerm ] );

	const searchProducts = async ( term ) => {
		setLoading( true );
		try {
			const formData = new FormData();
			formData.append( 'action', 'wcar_search_products' );
			formData.append( 'term', term );
			formData.append(
				'security',
				cart_abandonment_admin?.search_products_nonce || ''
			);

			const response = await fetch( cart_abandonment_admin?.ajax_url, {
				method: 'POST',
				body: formData,
			} );
			const result = await response.json();
			if ( result.success ) {
				// Map { value, label } to { id, name }
				const mapped = result.data.map( ( item ) => ( {
					id: item.value,
					name: item.label,
					image: item.image || null,
				} ) );
				setProducts( mapped );
			}
		} catch ( error ) {
			console.error( 'Error searching products:', error );
		}
		setLoading( false );
	};

	const loadSelectedProducts = async ( productIds ) => {
		if ( ! productIds || productIds.length === 0 ) {
			return;
		}
		try {
			const formData = new FormData();
			formData.append( 'action', 'wcar_search_products' );
			formData.append( 'product_ids', productIds.join( ',' ) );
			formData.append(
				'security',
				cart_abandonment_admin?.search_products_nonce || ''
			);

			const response = await fetch( cart_abandonment_admin?.ajax_url, {
				method: 'POST',
				body: formData,
			} );
			const result = await response.json();
			if ( result.success ) {
				const mapped = result.data.map( ( item ) => ( {
					id: item.value,
					name: item.label,
					image: item.image || null,
				} ) );
				setSelectedProducts( mapped );
			}
		} catch ( error ) {
			console.error( 'Error loading products:', error );
		}
	};

	const addProduct = ( product ) => {
		if ( ! selectedProducts.find( ( p ) => p.id === product.id ) ) {
			const newSelected = [ ...selectedProducts, product ];
			setSelectedProducts( newSelected );
			const newIDs = [ ...selectedProductIDs, String( product.id ) ];
			setSelectedProductIDs( newIDs );
			updateValue( newSelected );
		}
	};

	const removeProduct = ( productId ) => {
		const newSelected = selectedProducts.filter(
			( p ) => p.id !== productId
		);
		setSelectedProducts( newSelected );
		const newIDs = selectedProductIDs.filter(
			( id ) => id !== String( productId )
		);
		setSelectedProductIDs( newIDs );
		updateValue( newSelected );
	};

	const updateValue = ( _products ) => {
		const ids = _products.map( ( p ) => p.id ).join( ',' );
		handleChange( name, ids );
	};

	// Shown under the help text, after the search box, so the order reads: control, help, choices.
	const selectedChips = selectedProducts.length > 0 && (
		// Capped so a long list scrolls instead of pushing the rest of the form down.
		<div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto p-1 -mx-1 -mb-1">
			{ selectedProducts.map( ( product ) => (
				<Badge
					closable
					onClose={ () => removeProduct( product.id ) }
					key={ product.id }
					label={ product.name }
					size="md"
					type="pill"
					variant="neutral"
					className="[&_[role=button]]:-m-1.5 [&_[role=button]]:p-1.5"
				/>
			) ) }
		</div>
	);

	return (
		<FieldWrapper
			type="block"
			title={ title }
			description={ description }
			fieldId={ a11y.id }
			name={ name }
			afterControl={ selectedChips || null }
			disableStyle={ disableStyle }
			isPro={ isPro }
			proUpgradeMessage={ proUpgradeMessage }
		>
			{ ! ( isPro && isFeatureBlocked ) && (
				<SearchBox
					variant="secondary"
					closeAfterSelect={ false }
					loading={ loading }
					setOpen={ setOpen }
					open={ open }
					size="md"
				>
					<SearchBox.Input
						id={ a11y.id }
						name={ name }
						aria-describedby={ a11y.controlProps[ 'aria-describedby' ] }
						className="w-full box-border [&_span]:hidden"
						onChange={ ( val ) =>
							setSearchTerm(
								val && val.target ? val.target.value : val
							)
						}
						value={ searchTerm }
					/>
					<SearchBox.Portal id={ `wcar-${ name }` }>
						<SearchBox.Content className="z-10">
							<SearchBox.List>
								{ products ? (
									products.map( ( product ) => {
										const isSelected =
											selectedProductIDs.includes(
												String( product.id )
											);
										return (
											<SearchBox.Item
												className={
													isSelected &&
													'opacity-50 cursor-not-allowed'
												}
												key={ product.id }
												onClick={ () => {
													if ( ! isSelected ) {
														addProduct( product );
													}
												} }
												icon={
													product.image && (
														<img
															src={
																product.image
															}
															alt={ product.name }
															className="w-10 h-10 object-cover rounded"
														/>
													)
												}
											>
												{ product.name }
											</SearchBox.Item>
										);
									} )
								) : (
									<SearchBox.Empty>
										{ searchTerm.length < 3
											? __(
												'Type at least 3 letters to search',
												'woo-cart-abandonment-recovery'
											)
											: __(
												'No products found',
												'woo-cart-abandonment-recovery'
											) }
									</SearchBox.Empty>
								) }
							</SearchBox.List>
						</SearchBox.Content>
					</SearchBox.Portal>
				</SearchBox>
			) }

		</FieldWrapper>
	);
};

export default ProductSearchField;
