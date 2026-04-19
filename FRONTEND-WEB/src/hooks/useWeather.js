import { useQuery } from '@tanstack/react-query';
import { getWeatherForecast, getHourlySoilMoisture, getAllWeatherForecasts } from '../api/weather';

/**
 * Hook to fetch 7-day weather forecast for a specific farm.
 * @param {string} farmId - Farm ID
 * @returns {Object} React Query result with weather data
 */
export function useWeather(farmId) {
  return useQuery({
    queryKey: ['weather', farmId],
    queryFn: () => getWeatherForecast(farmId),
    enabled: Boolean(farmId),
    staleTime: 30 * 60 * 1000, // 30 minutes
    retry: 2,
  });
}

/**
 * Hook to fetch hourly soil moisture for today.
 * @param {string} farmId - Farm ID
 * @returns {Object} React Query result with hourly data
 */
export function useHourlySoilMoisture(farmId) {
  return useQuery({
    queryKey: ['weather', farmId, 'hourly'],
    queryFn: () => getHourlySoilMoisture(farmId),
    enabled: Boolean(farmId),
    staleTime: 15 * 60 * 1000, // 15 minutes
  });
}

/**
 * Hook to fetch weather for all farms (used on dashboard).
 * @returns {Object} React Query result with all weather data
 */
export function useAllWeather() {
  return useQuery({
    queryKey: ['weather', 'all'],
    queryFn: getAllWeatherForecasts,
    staleTime: 30 * 60 * 1000,
    retry: 2,
  });
}
