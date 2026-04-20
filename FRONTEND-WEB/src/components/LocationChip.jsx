import { MapPin, ChevronDown, X } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import { useLocation_ } from '../context/LocationContext';

export default function LocationChip() {
  const { location, status, requestLocation, clearLocation, setManualLocation } = useLocation_();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [input, setInput] = useState('');
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) { setOpen(false); setEditing(false); } };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  if (!location && status !== 'requesting') return null;

  if (status === 'requesting') {
    return (
      <div className="flex items-center gap-1.5 text-xs text-neutral-400 bg-neutral-50 border border-neutral-200 px-2.5 py-1 rounded-full">
        <div className="w-3 h-3 border-2 border-primary-300 border-t-primary-500 rounded-full animate-spin" />
        Locating…
      </div>
    );
  }

  const handleManual = (e) => {
    e.preventDefault();
    if (input.trim()) { setManualLocation(input.trim()); setEditing(false); setOpen(false); }
  };

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-1.5 text-xs text-primary-700 bg-primary-50 border border-primary-100 
                   hover:bg-primary-100 px-2.5 py-1 rounded-full transition-colors max-w-[140px]"
        title={location?.full_address || location?.display_name}
      >
        <MapPin size={11} className="flex-shrink-0" />
        <span className="truncate">{location?.display_name}</span>
        <ChevronDown size={11} className="flex-shrink-0" />
      </button>

      {open && (
        <div
          className="absolute top-8 right-0 w-64 bg-white border border-neutral-200 rounded-xl shadow-xl z-50 p-3"
          style={{ animation: 'slideInUp 200ms ease-out both' }}
        >
          <p className="text-xs font-semibold text-neutral-700 mb-2 flex items-center gap-1.5">
            <MapPin size={12} className="text-primary-500" />
            Your Location
          </p>
          {!editing ? (
            <>
              <p className="text-xs text-neutral-600 bg-neutral-50 rounded-lg px-3 py-2 mb-3 leading-relaxed">
                {location?.full_address || location?.display_name}
                {location?.manual && <span className="text-neutral-400 ml-1">(manual)</span>}
              </p>
              <div className="flex gap-2">
                <button onClick={requestLocation} className="btn-primary text-xs py-1.5 flex-1">Refresh GPS</button>
                <button onClick={() => setEditing(true)} className="btn-secondary text-xs py-1.5 flex-1">Change</button>
              </div>
              <button onClick={clearLocation} className="text-xs text-danger-500 hover:underline mt-2 w-full text-center">Clear location</button>
            </>
          ) : (
            <form onSubmit={handleManual} className="space-y-2">
              <input
                type="text"
                className="input text-xs"
                placeholder="e.g. Kharar, Punjab"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                autoFocus
              />
              <div className="flex gap-2">
                <button type="submit" className="btn-primary text-xs py-1.5 flex-1">Save</button>
                <button type="button" onClick={() => setEditing(false)} className="btn-secondary text-xs py-1.5 flex-1">Cancel</button>
              </div>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
