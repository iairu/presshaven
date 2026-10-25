import { Alert } from '@bsf/force-ui';

/**
 * Inline error for a wizard step.
 *
 * Force UI's `Alert` has no live-region role, so a screen reader would not announce it
 * when it appears. The wrapper does that. Keep `title` and `content` different: the title
 * says what happened, the content says what to do about it.
 *
 * @param {Object} props
 * @param {string} props.title   What went wrong.
 * @param {string} props.content What the merchant can do next.
 * @return {JSX.Element} The banner.
 */
const ErrorBanner = ( { title, content } ) => (
	<div role="alert">
		<Alert
			content={ content }
			variant="error"
			design="inline"
			className="shadow-none"
			title={ title }
		/>
	</div>
);

export default ErrorBanner;
