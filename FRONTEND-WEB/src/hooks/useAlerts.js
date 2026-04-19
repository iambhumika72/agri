import { useQuery } from '@tanstack/react-query';
import { getAlerts, getFarmAlerts, getSMSStats } from '../api/alerts';

/**
 * Hook to fetch all alerts with optional filters.
 * @param {Object} filters - Optional { farmId, severity, alert_type }
 * @returns {Object} React Query result with alerts array
 */
export function useAlerts(filters = {}) {
  return useQuery({
    queryKey: ['alerts', filters],
    queryFn: () => getAlerts(filters),
    staleTime: 2 * 60 * 1000, // 2 minutes — alerts refresh frequently
    refetchInterval: 2 * 60 * 1000,
    retry: 2,
  });
}

/**
 * Hook to fetch alerts for a specific farm.
 * @param {string} farmId - Farm ID
 * @returns {Object} React Query result with farm-specific alerts
 */
export function useFarmAlerts(farmId) {
  return useQuery({
    queryKey: ['alerts', 'farm', farmId],
    queryFn: () => getFarmAlerts(farmId),
    enabled: Boolean(farmId),
    staleTime: 2 * 60 * 1000,
    retry: 2,
  });
}

/**
 * Hook to fetch SMS delivery statistics for today.
 * @returns {Object} React Query result with SMS stats
 */
export function useSMSStats() {
  return useQuery({
    queryKey: ['alerts', 'sms-stats'],
    queryFn: getSMSStats,
    staleTime: 5 * 60 * 1000,
    retry: 2,
  });
}
