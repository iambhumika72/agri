import PropTypes from 'prop-types';
import { PackageOpen } from 'lucide-react';

export default function EmptyState({ message = 'No data available' }) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-neutral-400">
      <PackageOpen className="w-12 h-12 mb-3 text-neutral-300" />
      <p className="text-sm font-medium">{message}</p>
    </div>
  );
}

EmptyState.propTypes = {
  message: PropTypes.string,
};
