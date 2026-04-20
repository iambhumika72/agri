import PropTypes from 'prop-types';

export default function ConfidenceBadge({ score, label }) {
  let bg = 'bg-neutral-100 text-neutral-800 border-neutral-200';
  
  if (score >= 0.70) {
    bg = 'bg-emerald-50 text-emerald-700 border-emerald-200';
  } else if (score >= 0.50) {
    bg = 'bg-yellow-50 text-yellow-800 border-yellow-200';
  } else {
    bg = 'bg-red-50 text-red-700 border-red-200';
  }

  const displayScore = `${Math.round(score * 100)}%`;

  return (
    <div className={`inline-flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-2 px-3 py-1 rounded-md border ${bg}`}>
      <span className="text-sm font-bold">{displayScore}</span>
      <span className="text-xs font-medium opacity-90">{label || 'Confidence'}</span>
    </div>
  );
}

ConfidenceBadge.propTypes = {
  score: PropTypes.number.isRequired,
  label: PropTypes.string,
};
