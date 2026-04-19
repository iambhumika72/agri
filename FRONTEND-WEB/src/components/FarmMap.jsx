import PropTypes from 'prop-types';

function getMoistureColor(moisture) {
  if (moisture < 35) return '#BA7517';   // dry → amber
  if (moisture <= 70) return '#1D9E75'; // ok → green
  return '#2563eb';                      // wet → blue
}

function getMoistureFillClass(moisture) {
  if (moisture < 35) return 'fill-amber-100 stroke-amber-400';
  if (moisture <= 70) return 'fill-green-100 stroke-green-400';
  return 'fill-blue-100 stroke-blue-400';
}

function getMoistureTextClass(moisture) {
  if (moisture < 35) return 'text-amber-700';
  if (moisture <= 70) return 'text-green-700';
  return 'text-blue-700';
}

/**
 * SVG schematic farm map showing field zones coloured by soil moisture.
 * Dry = amber, OK = green, Wet = blue.
 */
export default function FarmMap({ zones, farmName }) {
  if (!zones || zones.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-neutral-400 text-sm">
        No zone data available.
      </div>
    );
  }

  // Layout configurations for up to 4 zones
  const layouts = {
    1: [{ x: 40, y: 40, w: 220, h: 180 }],
    2: [
      { x: 40, y: 40, w: 105, h: 180 },
      { x: 155, y: 40, w: 105, h: 180 },
    ],
    3: [
      { x: 40, y: 40, w: 220, h: 85 },
      { x: 40, y: 135, w: 105, h: 85 },
      { x: 155, y: 135, w: 105, h: 85 },
    ],
    4: [
      { x: 40, y: 40, w: 105, h: 85 },
      { x: 155, y: 40, w: 105, h: 85 },
      { x: 40, y: 135, w: 105, h: 85 },
      { x: 155, y: 135, w: 105, h: 85 },
    ],
  };

  const n = Math.min(zones.length, 4);
  const rects = layouts[n] || layouts[4];

  return (
    <div>
      <p className="text-xs font-medium text-neutral-500 mb-2 uppercase tracking-wider">{farmName} — Field Zones</p>
      <svg viewBox="0 0 300 260" xmlns="http://www.w3.org/2000/svg" className="w-full rounded-xl border border-neutral-100" style={{ maxHeight: 260 }}>
        {/* Background */}
        <rect width="300" height="260" fill="#F9F9F7" rx="12" />
        {/* Zones */}
        {zones.slice(0, n).map((zone, idx) => {
          const rect = rects[idx];
          const color = getMoistureColor(zone.moisture);
          const labelColor = zone.moisture < 35 ? '#92400e' : zone.moisture <= 70 ? '#14532d' : '#1e3a8a';
          return (
            <g key={zone.id}>
              <rect
                x={rect.x}
                y={rect.y}
                width={rect.w}
                height={rect.h}
                rx={8}
                fill={color}
                fillOpacity={0.18}
                stroke={color}
                strokeWidth={1.5}
              />
              <text
                x={rect.x + rect.w / 2}
                y={rect.y + rect.h / 2 - 8}
                textAnchor="middle"
                fontSize={10}
                fontWeight={600}
                fill={labelColor}
              >
                {zone.name}
              </text>
              <text
                x={rect.x + rect.w / 2}
                y={rect.y + rect.h / 2 + 6}
                textAnchor="middle"
                fontSize={13}
                fontWeight={700}
                fill={labelColor}
              >
                {Math.round(zone.moisture)}%
              </text>
              <text
                x={rect.x + rect.w / 2}
                y={rect.y + rect.h / 2 + 18}
                textAnchor="middle"
                fontSize={8}
                fill={labelColor}
                opacity={0.8}
              >
                {zone.moisture < 35 ? 'DRY' : zone.moisture <= 70 ? 'OPTIMAL' : 'WET'}
              </text>
            </g>
          );
        })}
        {/* Legend */}
        <rect x={8} y={232} width={10} height={10} fill="#BA7517" fillOpacity={0.5} rx={2} />
        <text x={21} y={241} fontSize={8} fill="#5F5E5A">Dry</text>
        <rect x={45} y={232} width={10} height={10} fill="#1D9E75" fillOpacity={0.5} rx={2} />
        <text x={58} y={241} fontSize={8} fill="#5F5E5A">OK</text>
        <rect x={78} y={232} width={10} height={10} fill="#2563eb" fillOpacity={0.5} rx={2} />
        <text x={91} y={241} fontSize={8} fill="#5F5E5A">Wet</text>
      </svg>
    </div>
  );
}

FarmMap.propTypes = {
  zones: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      name: PropTypes.string.isRequired,
      moisture: PropTypes.number.isRequired,
    })
  ).isRequired,
  farmName: PropTypes.string.isRequired,
};
