import PropTypes from 'prop-types';
import { CloudRain, Sun, Cloud, CloudSnow, Zap, Droplets } from 'lucide-react';

function getWeatherIcon(wmoCode, size = 20) {
  if (wmoCode === 0) return <Sun size={size} className="text-amber-400" />;
  if (wmoCode <= 2) return <Sun size={size} className="text-amber-300" />;
  if (wmoCode === 3) return <Cloud size={size} className="text-neutral-400" />;
  if (wmoCode >= 51 && wmoCode <= 67) return <Droplets size={size} className="text-blue-400" />;
  if (wmoCode >= 61 && wmoCode <= 67) return <CloudRain size={size} className="text-blue-500" />;
  if (wmoCode >= 71 && wmoCode <= 77) return <CloudSnow size={size} className="text-blue-200" />;
  if (wmoCode >= 80 && wmoCode <= 82) return <CloudRain size={size} className="text-blue-500" />;
  if (wmoCode >= 95) return <Zap size={size} className="text-amber-500" />;
  return <Cloud size={size} className="text-neutral-400" />;
}

/**
 * 7-day weather forecast strip component.
 */
export default function WeatherWidget({ forecast }) {
  if (!forecast || forecast.length === 0) {
    return (
      <div className="flex items-center justify-center h-24 text-neutral-400 text-sm">
        No forecast data available.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto scrollbar-thin">
      <div className="flex gap-3 min-w-max pb-1">
        {forecast.map((day, idx) => (
          <div
            key={day.date || idx}
            className="flex flex-col items-center gap-1.5 bg-neutral-50 border border-neutral-100 rounded-xl px-3 py-3 min-w-[88px]"
          >
            <p className="text-xs font-semibold text-neutral-600">{day.day}</p>
            <div>{getWeatherIcon(day.wmo_code, 22)}</div>
            <div className="text-center">
              <p className="text-sm font-bold text-neutral-800">{Math.round(day.temp_max)}°</p>
              <p className="text-xs text-neutral-400">{Math.round(day.temp_min)}°</p>
            </div>
            {day.precip_mm > 0 && (
              <div className="flex items-center gap-0.5 text-blue-500">
                <Droplets size={10} />
                <span className="text-xs font-medium">{Math.round(day.precip_mm)}mm</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

WeatherWidget.propTypes = {
  forecast: PropTypes.arrayOf(
    PropTypes.shape({
      date: PropTypes.string,
      day: PropTypes.string.isRequired,
      wmo_code: PropTypes.number.isRequired,
      condition: PropTypes.string,
      temp_max: PropTypes.number.isRequired,
      temp_min: PropTypes.number.isRequired,
      precip_mm: PropTypes.number,
    })
  ).isRequired,
};
