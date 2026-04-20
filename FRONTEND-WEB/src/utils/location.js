const STORAGE_KEY = 'agri_user_location';

export function getStoredLocation() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

export function getLocationPayload() {
  const loc = getStoredLocation();
  if (!loc) return {};
  return {
    latitude: loc.lat,
    longitude: loc.lon,
    location_name: loc.display_name,
  };
}
