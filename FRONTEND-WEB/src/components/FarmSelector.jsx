import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { MapPin } from 'lucide-react';

export default function FarmSelector({ value, onChange }) {
  const [localFarmId, setLocalFarmId] = useState(value || '');

  useEffect(() => {
    if (!value) {
      const stored = localStorage.getItem('krishi_farm_id');
      if (stored) {
        setLocalFarmId(stored);
        if (onChange) onChange(stored);
      }
    } else {
      setLocalFarmId(value);
      localStorage.setItem('krishi_farm_id', value);
    }
  }, [value, onChange]);

  const handleChange = (e) => {
    const newVal = e.target.value;
    setLocalFarmId(newVal);
    localStorage.setItem('krishi_farm_id', newVal);
    if (onChange) onChange(newVal);
  };

  return (
    <div className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-lg border border-neutral-200 shadow-sm focus-within:border-emerald-500 focus-within:ring-1 focus-within:ring-emerald-500 transition-all">
      <MapPin className="w-4 h-4 text-emerald-600" />
      <input
        type="text"
        placeholder="Enter Farm ID..."
        value={localFarmId}
        onChange={handleChange}
        className="border-none bg-transparent text-sm font-medium text-neutral-800 placeholder:text-neutral-400 focus:outline-none w-32 sm:w-48"
      />
    </div>
  );
}

FarmSelector.propTypes = {
  value: PropTypes.string,
  onChange: PropTypes.func,
};
