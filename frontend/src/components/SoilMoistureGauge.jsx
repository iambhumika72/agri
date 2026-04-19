import PropTypes from 'prop-types';
import {
  RadialBarChart,
  RadialBar,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Cell,
} from 'recharts';

function getMoistureColor(moisture) {
  if (moisture < 35) return '#A32D2D';   // dry → danger red
  if (moisture < 60) return '#BA7517';   // low → amber
  if (moisture <= 80) return '#1D9E75';  // ok → teal
  return '#2563eb';                       // wet → blue
}

const CustomTooltip = ({ active, payload }) => {
  if (active && payload && payload.length) {
    const d = payload[0].payload;
    return (
      <div className="bg-white border border-neutral-200 rounded-lg p-2.5 text-xs shadow-md">
        <p className="font-semibold text-neutral-700">{d.name}</p>
        <p className="text-neutral-500">Moisture: <strong>{Math.round(d.value)}%</strong></p>
      </div>
    );
  }
  return null;
};

CustomTooltip.propTypes = {
  active: PropTypes.bool,
  payload: PropTypes.array,
};

/**
 * Radial bar chart showing soil moisture per farm (up to 5 farms).
 */
export default function SoilMoistureGauge({ farms }) {
  const displayFarms = (farms || []).slice(0, 5);

  if (displayFarms.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-neutral-400 text-sm">
        No farm moisture data.
      </div>
    );
  }

  const chartData = displayFarms.map((f) => ({
    name: f.name,
    value: Math.round(f.soil_moisture_avg),
    fill: getMoistureColor(f.soil_moisture_avg),
  }));

  return (
    <div className="flex flex-col items-center">
      <ResponsiveContainer width="100%" height={220}>
        <RadialBarChart
          cx="50%"
          cy="50%"
          innerRadius="20%"
          outerRadius="90%"
          data={chartData}
          startAngle={90}
          endAngle={-270}
        >
          <RadialBar dataKey="value" background={{ fill: '#EEEEED' }} cornerRadius={4} label={false}>
            {chartData.map((entry, idx) => (
              <Cell key={idx} fill={entry.fill} />
            ))}
          </RadialBar>
          <Tooltip content={<CustomTooltip />} />
          <Legend
            iconType="circle"
            iconSize={8}
            wrapperStyle={{ fontSize: '10px', paddingTop: '4px' }}
            formatter={(value) => <span className="text-neutral-600">{value}</span>}
          />
        </RadialBarChart>
      </ResponsiveContainer>
      <div className="flex items-center gap-3 mt-1 text-xs text-neutral-500">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-danger-500 inline-block" /> Dry &lt;35%</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500 inline-block" /> Low</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-teal-400 inline-block" /> OK</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-500 inline-block" /> Wet</span>
      </div>
    </div>
  );
}

SoilMoistureGauge.propTypes = {
  farms: PropTypes.arrayOf(
    PropTypes.shape({
      name: PropTypes.string.isRequired,
      soil_moisture_avg: PropTypes.number.isRequired,
    })
  ).isRequired,
};
