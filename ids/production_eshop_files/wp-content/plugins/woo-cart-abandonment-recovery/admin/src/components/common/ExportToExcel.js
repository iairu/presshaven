import { useState } from '@wordpress/element';
import { Button, Loader, toast } from '@bsf/force-ui';
import { CloudArrowDownIcon } from '@heroicons/react/24/outline';
import { __ } from '@wordpress/i18n';

// Makes Excel read the file as UTF-8, so accented and non-Latin names survive.
const UTF8_BOM = '\uFEFF';

// How long the file's temporary address stays valid. Some browsers read it after the click returns.
const REVOKE_DELAY_MS = 10000;

// A cell that starts with one of these is run as a formula by Excel and Sheets. Customers type
// their own names at checkout, so a leading quote keeps such a value as plain text.
const FORMULA_START = /^[=+\-@\t\r]/;

const escapeCell = ( value ) => {
	let text = value === null || value === undefined ? '' : String( value );

	if ( FORMULA_START.test( text ) ) {
		text = `'${ text }`;
	}
	if ( /[",\r\n]/.test( text ) ) {
		text = '"' + text.replace( /"/g, '""' ) + '"';
	}
	return text;
};

/**
 * Turn rows into CSV text.
 *
 * @param {Object[]} rows    The rows to write.
 * @param {Object[]} columns Which fields to write, in order: `{ key, label, format? }`. The label
 *                           is the header; `format( value, row )` turns the stored value into
 *                           what the file shows.
 * @return {string} CSV text.
 */
const convertToCSV = ( rows, columns ) => {
	const lines = [ columns.map( ( column ) => escapeCell( column.label ) ) ];

	rows.forEach( ( row ) => {
		lines.push(
			columns.map( ( column ) =>
				escapeCell(
					column.format
						? column.format( row[ column.key ], row )
						: row[ column.key ]
				)
			)
		);
	} );

	return lines.map( ( line ) => line.join( ',' ) ).join( '\r\n' ) + '\r\n';
};

const downloadCSV = ( csv, fileName ) => {
	const blob = new Blob( [ UTF8_BOM + csv ], {
		type: 'text/csv;charset=utf-8;',
	} );
	const url = URL.createObjectURL( blob );
	const link = document.createElement( 'a' );

	link.setAttribute( 'href', url );
	link.setAttribute( 'download', fileName );
	link.style.visibility = 'hidden';
	document.body.appendChild( link );
	link.click();
	document.body.removeChild( link );
	setTimeout( () => URL.revokeObjectURL( url ), REVOKE_DELAY_MS );
};

/**
 * Button that downloads rows as a CSV file.
 *
 * @param {Object}   props
 * @param {Object[]} props.columns     Fields to write: `{ key, label, format? }`.
 * @param {Object[]} [props.data]      Rows to export, when they are already in the browser.
 * @param {Function} [props.fetchData] Returns a promise of the rows instead, for lists the server
 *                                     pages. Called when the button is pressed.
 * @param {string}   [props.filename]  File name, without the date or extension.
 * @param {string}   [props.className]
 * @param {boolean}  [props.disabled]
 * @return {JSX.Element} The button.
 */
const ExportToExcel = ( {
	columns,
	data,
	fetchData,
	filename = 'export',
	className = '',
	disabled = false,
} ) => {
	const [ isExporting, setIsExporting ] = useState( false );

	const handleExport = async () => {
		setIsExporting( true );
		try {
			const rows = fetchData ? await fetchData() : data;
			if ( ! rows || ! rows.length ) {
				toast.error(
					__( 'Nothing to export', 'woo-cart-abandonment-recovery' )
				);
				return;
			}

			const today = new Date();
			const stamp = [
				String( today.getDate() ).padStart( 2, '0' ),
				String( today.getMonth() + 1 ).padStart( 2, '0' ),
				today.getFullYear(),
			].join( '-' );
			downloadCSV( convertToCSV( rows, columns ), `${ filename }_${ stamp }.csv` );
		} catch ( error ) {
			toast.error(
				__( 'Export failed', 'woo-cart-abandonment-recovery' )
			);
		} finally {
			setIsExporting( false );
		}
	};

	return (
		<Button
			className={ className }
			iconPosition="left"
			size="sm"
			tag="button"
			type="button"
			variant="primary"
			onClick={ handleExport }
			disabled={
				disabled || isExporting || ( ! fetchData && ! data?.length )
			}
			icon={
				isExporting ? (
					<Loader className="p-0" icon={ null } size="sm" />
				) : (
					<CloudArrowDownIcon aria-hidden="true" />
				)
			}
		>
			{ __( 'Export', 'woo-cart-abandonment-recovery' ) }
		</Button>
	);
};

export default ExportToExcel;
