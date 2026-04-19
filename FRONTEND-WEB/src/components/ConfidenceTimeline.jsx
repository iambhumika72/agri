import PropTypes from 'prop-types';
import { LineChart, Line, Tooltip, ResponsiveContainer } from 'recharts';

// Generate mock 7-day confidence history for a given insight
function mockConfidenceHistory(baseConfidence) {
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  let val = Math.max(40, baseConfidence - 15);
  return days.map((day) => {
    val = Math.min(99, Math.max(40, val + (Math.random() * 10 - 4)));
    return { day, confidence: Math.round(val) };
  }).concat([{ day: 'Now', confidence: baseConfidence }]);
}

/**
 * Micro sparkline showing AI model confidence over last 7 days.
 * Green if trending up, amber if trending down.
 */
export default function ConfidenceTimeline({ confidence }) {
  const data = mockConfidenceHistory(confidence);
  const first = data[0].confidence;
  const last = data[data.length - 1].confidence;
  const trending = last >= first;
  const lineColor = trending ? '#1D9E75' : '#BA7517';

  return (
    <div className="flex items-center gap-3 pt-2 border-t border-neutral-100 mt-2">
      <div>
        <p className="text-[10px] text-neutral-400 leading-none mb-0.5">Confidence trend</p>
        <p className="text-xs font-bold" style={{ color: lineColor }}>
          {trending ? '↑' : '↓'} {Math.round(confidence)}%
        </p>
      </div>
      <div className="flex-1" style={{ height: 36 }}>
        <ResponsiveContainer width="100%" height={36}>
          <LineChart data={data}>
            <Line
              type="monotone"
              dataKey="confidence"
              stroke={lineColor}
              strokeWidth={1.5}
              dot={false}
              activeDot={{ r: 3 }}
            />
            <Tooltip
              contentStyle={{ fontSize: 10, padding: '2px 8px' }}
              formatter={(v) => [`${v}%`, 'Confidence']}
              labelFormatter={(l) => l}
              wrapperStyle={{ zIndex: 100 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

ConfidenceTimeline.propTypes = {
  confidence: PropTypes.number.isRequired,
};
