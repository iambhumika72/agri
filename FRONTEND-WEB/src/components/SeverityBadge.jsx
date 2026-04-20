import PropTypes from 'prop-types';

export default function SeverityBadge({ level }) {
  const norm = (level || '').toLowerCase();
  let bg = 'bg-neutral-100 text-neutral-800 border-neutral-200';

  if (norm === 'early' || norm === 'low') {
    bg = 'bg-blue-50 text-blue-700 border-blue-200';
  } else if (norm === 'moderate' || norm === 'medium') {
    bg = 'bg-yellow-50 text-yellow-800 border-yellow-200';
  } else if (norm === 'severe' || norm === 'high') {
    bg = 'bg-orange-50 text-orange-800 border-orange-200';
  } else if (norm === 'critical' || norm === 'immediate') {
    bg = 'bg-red-50 text-red-700 border-red-200';
  }

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${bg}`}>
      {level ? level.toUpperCase() : 'UNKNOWN'}
    </span>
  );
}

SeverityBadge.propTypes = {
  level: PropTypes.string,
};
