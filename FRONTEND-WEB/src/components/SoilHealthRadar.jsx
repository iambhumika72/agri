import PropTypes from 'prop-types';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Tooltip
} from 'recharts';

/**
 * Soil health radar chart with 6 axes: N, P, K, pH, Organic Matter, Moisture.
 */
export default function SoilHealthRadar({ soilData }) {
  const data = [
    { axis: 'Nitrogen (N)', value: Math.round(soilData?.nitrogen ?? 62) },
    { axis: 'Phosphorus (P)', value: Math.round(soilData?.phosphorus ?? 48) },
    { axis: 'Potassium (K)', value: Math.round(soilData?.potassium ?? 71) },
    { axis: 'pH Score', value: Math.round(soilData?.ph ?? 65) },
    { axis: 'Organic Matter', value: Math.round(soilData?.organic_matter ?? 55) },
    { axis: 'Moisture', value: Math.round(soilData?.moisture ?? 67) },
  ];

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload?.length) {
      const d = payload[0].payload;
      return (
        <div className="bg-white border border-neutral-200 rounded-lg p-2.5 text-xs shadow-md">
          <p className="font-semibold text-neutral-700">{d.axis}</p>
          <p className="text-primary-600 font-bold">{d.value} / 100</p>
        </div>
      );
    }
    return null;
  };

  return (
    <div>
      <p className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-3">Soil Health Profile</p>
      <ResponsiveContainer width="100%" height={240}>
        <RadarChart data={data} margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
          <PolarGrid stroke="#EEEEED" />
          <PolarAngleAxis
            dataKey="axis"
            tick={{ fontSize: 10, fill: '#5F5E5A', fontWeight: 500 }}
          />
          <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 9, fill: '#B8B8B5' }} axisLine={false} />
          <Radar
            name="Soil Health"
            dataKey="value"
            stroke="#3B6D11"
            fill="#3B6D11"
            fillOpacity={0.15}
            strokeWidth={2}
            dot={{ fill: '#3B6D11', r: 3 }}
          />
          <Tooltip content={<CustomTooltip />} />
        </RadarChart>
      </ResponsiveContainer>
      {/* Score badges */}
      <div className="grid grid-cols-3 gap-2 mt-2">
        {data.map((d) => (
          <div key={d.axis} className="text-center bg-neutral-50 rounded-lg py-1.5">
            <p className="text-xs font-bold text-neutral-800">{d.value}</p>
            <p className="text-[10px] text-neutral-400 leading-tight">{d.axis.split(' ')[0]}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

SoilHealthRadar.propTypes = {
  soilData: PropTypes.shape({
    nitrogen: PropTypes.number,
    phosphorus: PropTypes.number,
    potassium: PropTypes.number,
    ph: PropTypes.number,
    organic_matter: PropTypes.number,
    moisture: PropTypes.number,
  }),
};
