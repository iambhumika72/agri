import PropTypes from 'prop-types';
import {
  LineChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ComposedChart,
} from 'recharts';

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white border border-neutral-200 rounded-lg p-3 text-xs shadow-md">
        <p className="font-semibold text-neutral-700 mb-1">{label}</p>
        {payload.map((entry) => (
          <p key={entry.dataKey} style={{ color: entry.color }}>
            {entry.name}: {Number(entry.value).toFixed(1)} t/ha
          </p>
        ))}
      </div>
    );
  }
  return null;
};

CustomTooltip.propTypes = {
  active: PropTypes.bool,
  payload: PropTypes.array,
  label: PropTypes.string,
};

/**
 * 7-day rolling yield forecast line chart with confidence band.
 */
export default function YieldChart({ data }) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-neutral-400 text-sm">
        No yield data available.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <ComposedChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
        <defs>
          <linearGradient id="confidenceFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3B6D11" stopOpacity={0.15} />
            <stop offset="100%" stopColor="#3B6D11" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#EEEEED" />
        <XAxis
          dataKey="day"
          tick={{ fontSize: 11, fill: '#5F5E5A' }}
          axisLine={{ stroke: '#D8D8D6' }}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 11, fill: '#5F5E5A' }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `${v}t`}
          domain={['auto', 'auto']}
          label={{ value: 't/ha', angle: -90, position: 'insideLeft', fontSize: 10, fill: '#8F8E8B', dy: 20 }}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend
          wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }}
          iconType="circle"
          iconSize={8}
        />
        {/* Confidence band */}
        <Area
          dataKey="upper"
          fill="url(#confidenceFill)"
          stroke="none"
          name="Upper CI"
          legendType="none"
        />
        <Area
          dataKey="lower"
          fill="white"
          stroke="none"
          name="Lower CI"
          legendType="none"
        />
        <Line
          type="monotone"
          dataKey="yield"
          stroke="#3B6D11"
          strokeWidth={2}
          dot={{ fill: '#3B6D11', r: 3 }}
          activeDot={{ r: 5 }}
          name="Yield Forecast"
        />
        <Line
          type="monotone"
          dataKey="upper"
          stroke="#3B6D11"
          strokeWidth={1}
          strokeDasharray="4 4"
          dot={false}
          name="Upper CI"
        />
        <Line
          type="monotone"
          dataKey="lower"
          stroke="#3B6D11"
          strokeWidth={1}
          strokeDasharray="4 4"
          dot={false}
          name="Lower CI"
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

YieldChart.propTypes = {
  data: PropTypes.arrayOf(
    PropTypes.shape({
      day: PropTypes.string.isRequired,
      yield: PropTypes.number.isRequired,
      lower: PropTypes.number.isRequired,
      upper: PropTypes.number.isRequired,
    })
  ).isRequired,
};
