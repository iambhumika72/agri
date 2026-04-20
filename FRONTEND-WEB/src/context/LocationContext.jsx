import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';

const LocationContext = createContext(null);
const STORAGE_KEY = 'agri_user_location';

export function LocationProvider({ children }) {
  const [location, setLocation] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved ? JSON.parse(saved) : null;
    } catch { return null; }
  });
  const [status, setStatus] = useState('idle'); // 'idle' | 'requesting' | 'granted' | 'denied' | 'unavailable' | 'manual'
  const [showBanner, setShowBanner] = useState(false);

  // Show banner on first load if no location saved
  useEffect(() => {
    if (!localStorage.getItem(STORAGE_KEY)) {
      const timer = setTimeout(() => setShowBanner(true), 1500); // slight delay for UX
      return () => clearTimeout(timer);
    }
  }, []);

  const requestLocation = useCallback(async () => {
    if (!navigator.geolocation) {
      setStatus('unavailable');
      return;
    }
    setStatus('requesting');
    setShowBanner(false);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude: lat, longitude: lon } = pos.coords;
        // Reverse geocode via OpenStreetMap Nominatim (free, no API key)
        try {
          const res = await fetch(
            `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=json`,
            { headers: { 'Accept-Language': 'en' } }
          );
          const data = await res.json();
          const display = [
            data.address?.city || data.address?.town || data.address?.village || data.address?.county,
            data.address?.state,
          ].filter(Boolean).join(', ');

          const loc = {
            lat,
            lon,
            display_name: display || data.display_name?.split(',').slice(0, 2).join(', ') || 'Unknown location',
            full_address: data.display_name,
            timestamp: Date.now(),
          };
          localStorage.setItem(STORAGE_KEY, JSON.stringify(loc));
          setLocation(loc);
          setStatus('granted');
        } catch {
          // Geocoding failed but we still have coords
          const loc = { lat, lon, display_name: `${lat.toFixed(3)}, ${lon.toFixed(3)}`, timestamp: Date.now() };
          localStorage.setItem(STORAGE_KEY, JSON.stringify(loc));
          setLocation(loc);
          setStatus('granted');
        }
      },
      (err) => {
        if (err.code === 1) setStatus('denied');
        else if (err.code === 2) setStatus('unavailable');
        else setStatus('denied');
      },
      { timeout: 10000, maximumAge: 300000 }
    );
  }, []);

  const setManualLocation = useCallback((displayName) => {
    const loc = { lat: null, lon: null, display_name: displayName, timestamp: Date.now(), manual: true };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(loc));
    setLocation(loc);
    setStatus('manual');
    setShowBanner(false);
  }, []);

  const clearLocation = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setLocation(null);
    setStatus('idle');
    setShowBanner(true);
  }, []);

  const dismissBanner = useCallback(() => setShowBanner(false), []);

  return (
    <LocationContext.Provider value={{ location, status, showBanner, requestLocation, setManualLocation, clearLocation, dismissBanner }}>
      {children}
    </LocationContext.Provider>
  );
}

LocationProvider.propTypes = { children: PropTypes.node.isRequired };
export const useLocation_ = () => {
  const ctx = useContext(LocationContext);
  if (!ctx) throw new Error('useLocation_ must be used inside LocationProvider');
  return ctx;
};
