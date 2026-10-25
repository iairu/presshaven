import { Switch } from '@bsf/force-ui';
import { __, sprintf } from '@wordpress/i18n';

const TemplateStatusSwitch = ( { item, name, onToggle } ) => {
	const isActive = 'on' === item?.is_activated;

	return (
		<Switch
			aria-label={ sprintf(
				/* translators: %s: template name */
				__( 'Activate %s', 'woo-cart-abandonment-recovery' ),
				item.template_name
			) }
			aria-checked={ isActive }
			value={ isActive }
			name={ name }
			onChange={ ( val ) => onToggle( item.id, val ) }
			size="md"
			className="border-none"
			role="switch"
		/>
	);
};

export default TemplateStatusSwitch;
