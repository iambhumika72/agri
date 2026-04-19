import PropTypes from 'prop-types';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

/**
 * Reusable metric card for displaying a single KPI.
 */
export default function StatCard({ title, value, unit, trend, trendLabel, icon: Icon, colorClass, danger }) {
  const trendIcon =
    trend === 'up' ? (
      <TrendingUp size={13} className={danger ? 'text-danger-500' : 'text-teal-400'} />
    ) : trend === 'down' ? (
      <TrendingDown size={13} className={danger ? 'text-teal-400' : 'text-danger-500'} />
    ) : (
      <Minus size={13} className="text-neutral-400" />
    );

  return (
    <div className={`card flex items-start gap-4 ${danger ? 'border-danger-200 bg-danger-50' : ''}`}>
      {Icon && (
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${colorClass || 'bg-primary-50'}`}>
          <Icon size={18} className={danger ? 'text-danger-500' : 'text-primary-500'} />
        </div>
      )}
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-neutral-400 uppercase tracking-wider truncate">{title}</p>
        <p className={`text-2xl font-bold mt-0.5 leading-tight ${danger ? 'text-danger-600' : 'text-neutral-800'}`}>
          {value}
          {unit && <span className="text-sm font-medium text-neutral-400 ml-1">{unit}</span>}
        </p>
        {trendLabel && (
          <div className="flex items-center gap-1 mt-1">
            {trendIcon}
            <span className="text-xs text-neutral-500">{trendLabel}</span>
          </div>
        )}
      </div>
    </div>
  );
}

StatCard.propTypes = {
  title: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  unit: PropTypes.string,
  trend: PropTypes.oneOf(['up', 'down', 'flat']),
  trendLabel: PropTypes.string,
  icon: PropTypes.elementType,
  colorClass: PropTypes.string,
  danger: PropTypes.bool,
};
