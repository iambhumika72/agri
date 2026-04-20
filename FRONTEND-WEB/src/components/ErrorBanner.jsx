import PropTypes from 'prop-types';
import { AlertCircle, RefreshCw } from 'lucide-react';

export default function ErrorBanner({ message, onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center p-6 bg-red-50/50 rounded-xl border border-red-100">
      <AlertCircle className="w-8 h-8 text-red-500 mb-3" />
      <p className="text-red-800 text-center font-medium mb-4">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-2 px-4 py-2 bg-white text-red-600 rounded-lg shadow-sm border border-red-200 hover:bg-red-50 transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          <span>Try Again</span>
        </button>
      )}
    </div>
  );
}

ErrorBanner.propTypes = {
  message: PropTypes.string.isRequired,
  onRetry: PropTypes.func,
};
