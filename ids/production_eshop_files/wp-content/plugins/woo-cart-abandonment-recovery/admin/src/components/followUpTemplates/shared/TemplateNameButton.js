import AppTooltip from '@Components/common/AppTooltip';
import TableLinkButton from '@Components/common/TableLinkButton';
import { truncateText } from './utils';

const TemplateNameButton = ( { name, onClick } ) => (
	<AppTooltip content={ name }>
		<TableLinkButton onClick={ onClick }>
			{ truncateText( name, 30 ) }
		</TableLinkButton>
	</AppTooltip>
);

export default TemplateNameButton;
