import PropTypes from 'prop-types';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const PHASE_COLORS = {
  sowing: '#1D9E75',
  growing: '#3B6D11',
  harvest: '#BA7517',
  off: '#D8D8D6',
};

/**
 * Horizontal scrollable 12-month crop calendar strip.
 * Current month highlighted. Color bands show sow → harvest per crop.
 */
export default function CropCalendarStrip({ crops }) {
  const currentMonth = new Date().getMonth(); // 0-indexed

  const getPhase = (crop, monthIdx) => {
    const { sowMonth, harvestMonth } = crop;
    const sow = sowMonth - 1;
    const harvest = harvestMonth - 1;
    const extra = harvest < sow ? harvest + 12 : harvest;
    const mAdj = monthIdx < sow ? monthIdx + 12 : monthIdx;

    if (mAdj === sow) return 'sowing';
    if (mAdj === extra) return 'harvest';
    if (mAdj > sow && mAdj < extra) return 'growing';
    return 'off';
  };

  return (
    <div>
      <div className="overflow-x-auto scrollbar-thin pb-2">
        <div className="min-w-[700px]">
          {/* Month headers */}
          <div className="grid grid-cols-12 gap-1 mb-2">
            {MONTHS.map((m, idx) => (
              <div
                key={m}
                className={`text-center text-xs font-semibold py-1.5 rounded-md ${
                  idx === currentMonth
                    ? 'bg-primary-500 text-white'
                    : 'text-neutral-400'
                }`}
              >
                {m}
              </div>
            ))}
          </div>
          {/* Crop rows */}
          {(crops || []).map((crop, ci) => (
            <div key={crop.name} className="mb-2" style={{ animation: `slideInRight 300ms ease-out both`, animationDelay: `${ci * 80}ms` }}>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-medium text-neutral-600 w-32 truncate flex-shrink-0">{crop.name}</span>
              </div>
              <div className="grid grid-cols-12 gap-1">
                {MONTHS.map((_, monthIdx) => {
                  const phase = getPhase(crop, monthIdx);
                  const isCurrentMonth = monthIdx === currentMonth;
                  return (
                    <div
                      key={monthIdx}
                      title={`${MONTHS[monthIdx]}: ${phase}`}
                      className={`h-6 rounded-md transition-all ${isCurrentMonth ? 'ring-2 ring-offset-1 ring-primary-400' : ''}`}
                      style={{ backgroundColor: PHASE_COLORS[phase], opacity: phase === 'off' ? 0.3 : 1 }}
                    />
                  );
                })}
              </div>
            </div>
          ))}
          {/* Legend */}
          <div className="flex items-center gap-4 mt-2 pt-2 border-t border-neutral-100">
            {Object.entries(PHASE_COLORS).map(([phase, color]) => (
              <div key={phase} className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: color }} />
                <span className="text-xs text-neutral-500 capitalize">{phase}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

CropCalendarStrip.propTypes = {
  crops: PropTypes.arrayOf(PropTypes.shape({
    name: PropTypes.string.isRequired,
    sowMonth: PropTypes.number.isRequired,
    harvestMonth: PropTypes.number.isRequired,
  })).isRequired,
};
