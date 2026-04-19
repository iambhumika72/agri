import PropTypes from 'prop-types';
import { useEffect, useRef, useState } from 'react';

/**
 * Circular health score SVG arc with animated stroke-dashoffset on mount.
 * Sub-scores as mini progress bars below.
 */
export default function FarmHealthScore({ score, subScores }) {
  const [displayed, setDisplayed] = useState(0);
  const animRef = useRef(null);

  // Animate score 0 → actual on mount
  useEffect(() => {
    let start = null;
    const duration = 1000;
    const target = Math.min(100, Math.max(0, score || 0));
    const step = (ts) => {
      if (!start) start = ts;
      const progress = Math.min((ts - start) / duration, 1);
      setDisplayed(Math.round(target * progress));
      if (progress < 1) animRef.current = requestAnimationFrame(step);
    };
    animRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(animRef.current);
  }, [score]);

  const r = 40;
  const circumference = 2 * Math.PI * r;
  const offset = circumference - (displayed / 100) * circumference;
  const color = score >= 71 ? '#1D9E75' : score >= 41 ? '#BA7517' : '#A32D2D';

  return (
    <div className="card col-span-2 flex flex-col sm:flex-row items-center gap-6"
      style={{ animation: 'slideInUp 400ms ease-out both', animationDelay: '400ms' }}>
      {/* Arc */}
      <div className="flex flex-col items-center flex-shrink-0">
        <p className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-3">Farm Health Score</p>
        <svg width={110} height={110} viewBox="-5 -5 110 110">
          <circle cx="50" cy="50" r={r} fill="none" stroke="#EEEEED" strokeWidth={10} />
          <circle
            cx="50" cy="50" r={r}
            fill="none"
            stroke={color}
            strokeWidth={10}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            transform="rotate(-90 50 50)"
            style={{ transition: 'stroke-dashoffset 1s ease-out' }}
          />
          <text x="50" y="54" textAnchor="middle" fontSize="22" fontWeight="700" fill={color}>{displayed}</text>
          <text x="50" y="66" textAnchor="middle" fontSize="9" fill="#8F8E8B">/100</text>
        </svg>
        <div className={`text-xs font-medium mt-1 px-2.5 py-0.5 rounded-full ${score >= 71 ? 'text-teal-700 bg-teal-50' : score >= 41 ? 'text-amber-700 bg-amber-50' : 'text-danger-700 bg-danger-50'}`}>
          {score >= 71 ? 'Healthy' : score >= 41 ? 'Moderate' : 'At Risk'}
        </div>
      </div>

      {/* Sub-scores */}
      <div className="flex-1 w-full space-y-3">
        {(subScores || []).map(({ label, value, color: sc }) => (
          <div key={label}>
            <div className="flex justify-between text-xs mb-1">
              <span className="font-medium text-neutral-600">{label}</span>
              <span className="font-semibold text-neutral-800">{Math.round(value)}</span>
            </div>
            <div className="h-2 bg-neutral-100 rounded-full overflow-hidden">
              <div
                className="h-2 rounded-full transition-all duration-700"
                style={{ width: `${value}%`, backgroundColor: sc || '#3B6D11' }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

FarmHealthScore.propTypes = {
  score: PropTypes.number.isRequired,
  subScores: PropTypes.arrayOf(PropTypes.shape({
    label: PropTypes.string.isRequired,
    value: PropTypes.number.isRequired,
    color: PropTypes.string,
  })).isRequired,
};
