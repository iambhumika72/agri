import { useState } from 'react';
import { MapPin, X, Navigation } from 'lucide-react';
import { useLocation_ } from '../context/LocationContext';

export default function LocationBanner() {
  const { showBanner, status, requestLocation, setManualLocation, dismissBanner } = useLocation_();
  const [manualInput, setManualInput] = useState('');
  const [showManual, setShowManual] = useState(false);

  if (!showBanner || status === 'granted' || status === 'manual') return null;

  const handleManualSubmit = (e) => {
    e.preventDefault();
    if (manualInput.trim()) {
      setManualLocation(manualInput.trim());
      setShowManual(false);
    }
  };

  return (
    <div
      className="fixed bottom-20 md:bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-96 
                 bg-white border border-neutral-100 rounded-xl shadow-xl z-50 overflow-hidden"
      style={{ animation: 'slideInUp 350ms ease-out both' }}
      role="banner"
      aria-label="Location access request"
    >
      <div className="h-1 bg-primary-500" />
      <div className="p-4">
        <div className="flex items-start gap-3">
          <div className="w-9 h-9 bg-primary-50 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
            <MapPin size={18} className="text-primary-600" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-neutral-800">Enable Location</p>
            <p className="text-xs text-neutral-500 mt-0.5 leading-relaxed">
              Get accurate weather forecasts and local farming advice for your area.
            </p>
            {!showManual ? (
              <div className="flex items-center gap-2 mt-3 flex-wrap">
                <button
                  onClick={requestLocation}
                  disabled={status === 'requesting'}
                  className="btn-primary flex items-center gap-1.5 text-xs py-1.5 px-3 disabled:opacity-60"
                >
                  <Navigation size={12} />
                  {status === 'requesting' ? 'Locating…' : 'Allow Location'}
                </button>
                <button
                  onClick={() => setShowManual(true)}
                  className="text-xs text-primary-600 hover:underline font-medium"
                >
                  Enter manually
                </button>
                <button
                  onClick={dismissBanner}
                  className="text-xs text-neutral-400 hover:text-neutral-600 ml-auto"
                >
                  Skip for now
                </button>
              </div>
            ) : (
              <form onSubmit={handleManualSubmit} className="flex gap-2 mt-3">
                <input
                  type="text"
                  className="input text-xs h-8 flex-1"
                  placeholder="e.g. Ludhiana, Punjab"
                  value={manualInput}
                  onChange={(e) => setManualInput(e.target.value)}
                  autoFocus
                />
                <button type="submit" className="btn-primary text-xs py-1.5 px-3">Set</button>
                <button type="button" onClick={() => setShowManual(false)} className="btn-secondary text-xs py-1.5 px-3">Back</button>
              </form>
            )}
            {status === 'denied' && (
              <p className="text-xs text-danger-500 mt-2">
                Location access was denied. Please use manual entry or enable in browser settings.
              </p>
            )}
          </div>
          <button onClick={dismissBanner} className="text-neutral-300 hover:text-neutral-500 flex-shrink-0">
            <X size={15} />
          </button>
        </div>
      </div>
    </div>
  );
}
