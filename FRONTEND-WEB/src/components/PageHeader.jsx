import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';

export default function PageHeader({ titleKey, descKey, icon: Icon }) {
  const { t } = useTranslation();

  return (
    <div
      className="w-full flex items-center px-6 py-4 bg-white border-b border-neutral-200"
      style={{ animation: 'fadeIn 200ms ease-out both' }}
    >
      <div className="flex gap-3">
        {Icon && (
          <div className="mt-1">
            <Icon size={24} className="text-primary-600" />
          </div>
        )}
        <div>
          <h1 className="text-[20px] font-medium text-neutral-800 leading-tight">
            {t(titleKey)}
          </h1>
          <p className="text-[14px] text-neutral-500 mt-1 max-w-full truncate md:whitespace-normal">
            {t(descKey)}
          </p>
        </div>
      </div>
    </div>
  );
}

PageHeader.propTypes = {
  titleKey: PropTypes.string.isRequired,
  descKey: PropTypes.string.isRequired,
  icon: PropTypes.elementType,
};
