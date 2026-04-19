import { useState } from 'react';
import { CloudSun, AlertTriangle, Flame, Snowflake, Wind, Droplets, Thermometer, Cloud, MapPin } from 'lucide-react';
import { useFarms } from '../hooks/useFarms';
import { useWeather } from '../hooks/useWeather';
import PageHeader from '../components/PageHeader';
import DataFreshnessBar from '../components/DataFreshnessBar';

const WMO_LABELS = {
  0: 'Clear Sky', 1: 'Mainly Clear', 2: 'Partly Cloudy', 3: 'Overcast',
  45: 'Foggy', 48: 'Depositing Rime Fog',
  51: 'Light Drizzle', 53: 'Moderate Drizzle', 55: 'Dense Drizzle',
  61: 'Slight Rain', 63: 'Moderate Rain', 65: 'Heavy Rain',
  71: 'Slight Snow', 73: 'Moderate Snow', 75: 'Heavy Snow',
  80: 'Rain Showers', 81: 'Moderate Showers', 82: 'Violent Showers',
  95: 'Thunderstorm', 96: 'Thunderstorm + Hail', 99: 'Heavy Thunderstorm',
};

const SEASON_COLORS = {
  Kharif: 'bg-green-100 text-green-700',
  Rabi: 'bg-blue-100 text-blue-700',
  Zaid: 'bg-orange-100 text-orange-700',
};

function WeatherDayCard({ day }) {
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <div>
          <p className="font-bold text-neutral-800">{day.day}</p>
          <p className="text-xs text-neutral-400">{day.date}</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          {day.frost_risk && (
            <span className="flex items-center gap-1 text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full font-medium">
              <Snowflake size={10} /> Frost Risk
            </span>
          )}
          {day.heat_stress && (
            <span className="flex items-center gap-1 text-xs text-orange-600 bg-orange-50 px-2 py-0.5 rounded-full font-medium">
              <Flame size={10} /> Heat Stress
            </span>
          )}
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${SEASON_COLORS[day.season] || 'bg-neutral-100 text-neutral-600'}`}>
            {day.season}
          </span>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-neutral-50 rounded-lg p-3">
          <p className="text-xs text-neutral-400 mb-1">Condition</p>
          <p className="text-sm font-semibold text-neutral-700">{WMO_LABELS[day.wmo_code] || day.condition}</p>
        </div>
        <div className="bg-neutral-50 rounded-lg p-3">
          <p className="text-xs text-neutral-400 mb-1">Temperature</p>
          <p className="text-sm font-semibold text-neutral-700">
            <span className="text-danger-500">{Math.round(day.temp_max)}°</span>
            <span className="text-neutral-300 mx-1">/</span>
            <span className="text-blue-500">{Math.round(day.temp_min)}°</span>
            <span className="text-neutral-300 text-xs ml-1">C</span>
          </p>
        </div>
        <div className="bg-neutral-50 rounded-lg p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <Droplets size={11} className="text-blue-400" />
            <p className="text-xs text-neutral-400">Precipitation</p>
          </div>
          <p className="text-sm font-semibold text-neutral-700">{Math.round(day.precip_mm)} mm</p>
        </div>
        <div className="bg-neutral-50 rounded-lg p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <Wind size={11} className="text-neutral-400" />
            <p className="text-xs text-neutral-400">Wind</p>
          </div>
          <p className="text-sm font-semibold text-neutral-700">{Math.round(day.wind_kmh)} km/h</p>
        </div>
        <div className="bg-neutral-50 rounded-lg p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <Thermometer size={11} className="text-amber-400" />
            <p className="text-xs text-neutral-400">ET₀</p>
          </div>
          <p className="text-sm font-semibold text-neutral-700">{day.et0_mm.toFixed(1)} mm/day</p>
        </div>
        <div className="bg-neutral-50 rounded-lg p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <Droplets size={11} className="text-teal-400" />
            <p className="text-xs text-neutral-400">Soil Moisture</p>
          </div>
          <p className="text-sm font-semibold text-neutral-700">{Math.round(day.soil_moisture_avg)}%</p>
        </div>
      </div>
    </div>
  );
}

export default function WeatherPage() {
  const { data: farms } = useFarms();
  const [selectedFarmId, setSelectedFarmId] = useState('farm-001');
  const { data: weather, isLoading, error } = useWeather(selectedFarmId);

  const selectedFarm = farms?.find((f) => f.id === selectedFarmId);

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-24 md:pb-8">
      <PageHeader 
        titleKey="page.weather.title" 
        descKey="page.weather.desc" 
        icon={Cloud} 
      />

      <DataFreshnessBar />

      {/* Farm selector */}
      <div className="card flex items-center gap-4 flex-wrap">
        <label className="text-sm font-medium text-neutral-600 flex items-center gap-2 flex-shrink-0">
          <CloudSun size={15} className="text-teal-400" />
          Select Farm:
        </label>
        <select
          id="farm-weather-selector"
          className="select flex-1 min-w-[200px]"
          value={selectedFarmId}
          onChange={(e) => setSelectedFarmId(e.target.value)}
        >
          {(farms || []).map((f) => (
            <option key={f.id} value={f.id}>
              {f.name} — {f.location}
            </option>
          ))}
        </select>
        {selectedFarm && (
          <div className="flex items-center gap-3 text-xs text-neutral-500">
            <span className="font-medium">{selectedFarm.crop_type}</span>
            <span>·</span>
            <span>{selectedFarm.area_ha} ha</span>
          </div>
        )}
      </div>

      {/* Error state */}
      {error && (
        <div className="card flex items-center gap-3 text-danger-500 border-danger-200 bg-danger-50">
          <AlertTriangle size={18} />
          <p className="text-sm">{error.message}</p>
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="card animate-pulse h-64 bg-neutral-100" />
          ))}
        </div>
      )}

      {/* Forecast day cards */}
      {!isLoading && weather?.daily && weather.daily.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {weather.daily.map((day, idx) => (
            <WeatherDayCard key={day.date || idx} day={day} />
          ))}
        </div>
      )}

      {!isLoading && (!weather?.daily || weather.daily.length === 0) && (
        <div className="card flex flex-col items-center justify-center py-16 text-neutral-400 gap-3">
          <CloudSun size={36} />
          <p className="text-sm">No forecast data available for this farm.</p>
        </div>
      )}
    </div>
  );
}
