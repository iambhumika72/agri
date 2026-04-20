import PropTypes from 'prop-types';

export default function LoadingSpinner({ message = 'Loading...' }) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-neutral-500">
      <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-emerald-600 mb-4"></div>
      <p className="text-sm font-medium">{message}</p>
    </div>
  );
}

LoadingSpinner.propTypes = {
  message: PropTypes.string,
};
