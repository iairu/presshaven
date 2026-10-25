import { Title } from '@bsf/force-ui';
import { CompactLabelContext } from '@Components/common/FieldWrapper';

const TabWrapper = ( { title, children } ) => {
	return (
		<div>
			<Title
				size="md"
				tag="h2"
				title={ title }
				className="mb-6 [&_h2]:text-gray-900 text-xl"
			/>
			<div className="h-auto px-6 bg-background-primary rounded-xl shadow-sm">
				<CompactLabelContext.Provider value={ true }>
					{ children }
				</CompactLabelContext.Provider>
			</div>
		</div>
	);
};

export default TabWrapper;
