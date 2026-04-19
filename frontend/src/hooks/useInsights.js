import { useQuery } from '@tanstack/react-query';
import { getInsights, getFarmInsights, getModelStatus } from '../api/insights';

/**
 * Hook to fetch all AI insights with optional filters.
 * @param {Object} filters - Optional { farmId, category, priority }
 * @returns {Object} React Query result with insights array
 */
export function useInsights(filters = {}) {
  return useQuery({
    queryKey: ['insights', filters],
    queryFn: () => getInsights(filters),
    staleTime: 10 * 60 * 1000, // 10 minutes
    retry: 2,
  });
}

/**
 * Hook to fetch insights for one specific farm.
 * @param {string} farmId - Farm ID
 * @returns {Object} React Query result with farm-specific insights
 */
export function useFarmInsights(farmId) {
  return useQuery({
    queryKey: ['insights', 'farm', farmId],
    queryFn: () => getFarmInsights(farmId),
    enabled: Boolean(farmId),
    staleTime: 10 * 60 * 1000,
    retry: 2,
  });
}

/**
 * Hook to fetch AI model status.
 * @returns {Object} React Query result with model status data
 */
export function useModelStatus() {
  return useQuery({
    queryKey: ['insights', 'model-status'],
    queryFn: getModelStatus,
    staleTime: 60 * 1000, // 1 minute
    refetchInterval: 60 * 1000,
  });
}
