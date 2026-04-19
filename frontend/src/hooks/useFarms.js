import { useQuery } from '@tanstack/react-query';
import { getFarms, getFarm } from '../api/farms';

/**
 * Hook to fetch all farms.
 * @returns {Object} React Query result with farms data, loading, and error states
 */
export function useFarms() {
  return useQuery({
    queryKey: ['farms'],
    queryFn: getFarms,
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: 2,
  });
}

/**
 * Hook to fetch a single farm by ID.
 * @param {string} farmId - The farm's unique identifier
 * @returns {Object} React Query result with farm data, loading, and error states
 */
export function useFarm(farmId) {
  return useQuery({
    queryKey: ['farms', farmId],
    queryFn: () => getFarm(farmId),
    enabled: Boolean(farmId),
    staleTime: 5 * 60 * 1000,
    retry: 2,
  });
}
