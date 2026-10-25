import { useId } from '@wordpress/element';
import { cn } from '@Utils/helper';

/**
 * Ids and ARIA attributes that tie a field's control to its label, help text and error.
 *
 * Spread `controlProps` onto the control (`<Input>`, `<Select>`, `<Switch>`...) and pass `id`
 * to `FieldWrapper` as `fieldId`, so the label points at the control it names. Without that
 * the label's `for` matches nothing and the control has no accessible name.
 *
 * @param {Object} [options]
 * @param {string} [options.description] Help text shown under the label, if any.
 * @param {string} [options.error]       Validation message for this field, if any.
 * @return {Object} `{ id, errorId, controlProps }`.
 */
export const useFieldA11y = ( { description, error } = {} ) => {
	const id = useId();
	const errorId = error ? `${ id }-error` : undefined;
	const describedBy =
		[ description ? `${ id }-description` : null, errorId ]
			.filter( Boolean )
			.join( ' ' ) || undefined;

	return {
		id,
		errorId,
		controlProps: {
			id,
			'aria-describedby': describedBy,
			'aria-invalid': error ? true : undefined,
		},
	};
};

/**
 * Inline validation message, announced when it appears and linked to its control by
 * `aria-describedby` (see `useFieldA11y`).
 *
 * @param {Object} props
 * @param {string} props.id          Id from `useFieldA11y().errorId`.
 * @param {string} props.children    Message.
 * @param {string} [props.className] Extra classes, e.g. to keep a short message on one line.
 * @return {JSX.Element|null} The message, or nothing when there is none.
 */
export const FieldError = ( { id, children, className = '' } ) =>
	children ? (
		<p
			id={ id }
			role="alert"
			className={ cn( 'm-0 mt-1 text-sm text-support-error', className ) }
		>
			{ children }
		</p>
	) : null;
