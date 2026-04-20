import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { MapPin, ChevronDown } from 'lucide-react';
import { useFarms } from '../hooks/useFarms';

export default function FarmSelector({ value, onChange }) {
  const { data: farms, isLoading } = useFarms();
  const [localFarmId, setLocalFarmId] = useState(value || '');

  useEffect(() => {
    if (value) {
      setLocalFarmId(value);
      localStorage.setItem('krishi_farm_id', value);
    }
  }, [value]);

  const handleChange = (e) => {
    const newVal = e.target.value;
    setLocalFarmId(newVal);
    localStorage.setItem('krishi_farm_id', newVal);
    if (onChange) onChange(newVal);
  };

  return (
    <div className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-lg border border-neutral-200 shadow-sm focus-within:border-emerald-500 focus-within:ring-1 focus-within:ring-emerald-500 transition-all">
      <MapPin className="w-4 h-4 text-emerald-600" />
      {farms && farms.length > 0 ? (
        <div className="relative flex items-center">
          <select
            value={localFarmId}
            onChange={handleChange}
            className="appearance-none bg-transparent text-sm font-medium text-neutral-800 focus:outline-none pr-6 cursor-pointer min-w-[150px]"
          >
            <option value="" disabled>Select Farm</option>
            {farms.map((f) => (
              <option key={f.farm_id} value={f.farm_id}>
                {f.farmer_name} ({f.farm_id.slice(0, 8)})
              </option>
            ))}
          </select>
          <ChevronDown className="w-4 h-4 text-neutral-400 absolute right-0 pointer-events-none" />
        </div>
      ) : (
        <input
          type="text"
          placeholder="Enter Farm ID..."
          value={localFarmId}
          onChange={handleChange}
          className="border-none bg-transparent text-sm font-medium text-neutral-800 placeholder:text-neutral-400 focus:outline-none w-32 sm:w-48"
        />
      )}
      {isLoading && <div className="w-3 h-3 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>}
    </div>
  );
}

FarmSelector.propTypes = {
  value: PropTypes.string,
  onChange: PropTypes.func,
};
