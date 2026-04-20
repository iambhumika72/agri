import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Activity, Server, Database, BrainCircuit, RefreshCw } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorBanner from '../components/ErrorBanner';
import { systemHealthAPI, visionAPI } from '../api/client';

export default function SystemHealthPage() {
  const { t } = useTranslation();
  const [health, setHealth] = useState(null);
  const [visionHealth, setVisionHealth] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastRefreshed, setLastRefreshed] = useState(new Date());

  const fetchHealth = async (showLoading = false) => {
    if (showLoading) setLoading(true);
    setError(null);
    try {
      const [sys, vis] = await Promise.all([
        systemHealthAPI.getSystemHealth(),
        visionAPI.getHealth().catch(() => null) // Mocked
      ]);
      setHealth(sys);
      setVisionHealth(vis);
      setLastRefreshed(new Date());
    } catch (err) {
      setError(err.message);
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth(true);
    const interval = setInterval(() => fetchHealth(false), 60000);
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (status) => {
    return status === 'ok' || status === 'online' || status === 'healthy' || status === 'available' ? 'bg-emerald-500' : 'bg-red-500';
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-24 md:pb-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <PageHeader 
          titleKey="page.system_health.title" 
          descKey="page.system_health.desc" 
          icon={Activity} 
        />
        <div className="flex items-center gap-2 text-xs text-neutral-500 bg-white px-3 py-1.5 rounded-full border border-neutral-200">
          <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
          Last updated: {lastRefreshed.toLocaleTimeString()}
        </div>
      </div>

      {loading && !health && <LoadingSpinner message="Checking system status..." />}

      {error && <ErrorBanner message={error} onRetry={() => fetchHealth(true)} />}

      {!loading && !error && health && (
        <div className="space-y-6">
          <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-2 rounded-lg text-sm font-medium text-center shadow-sm">
            🛰️ Satellite analysis coming soon (Showing mock vision data)
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            
            {/* Core API Status */}
            <div className="card flex items-start gap-4">
              <div className="p-3 bg-neutral-100 rounded-lg">
                <Server className="w-6 h-6 text-neutral-600" />
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between mb-1">
                  <h3 className="font-bold text-neutral-800">Core API</h3>
                  <span className="relative flex h-3 w-3">
                    <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${getStatusColor(health.status)}`}></span>
                    <span className={`relative inline-flex rounded-full h-3 w-3 ${getStatusColor(health.status)}`}></span>
                  </span>
                </div>
                <p className="text-xs text-neutral-500 mb-2">Version {health.version}</p>
                <div className="text-sm">
                  <p>Status: <span className="capitalize font-medium">{health.status}</span></p>
                </div>
              </div>
            </div>

            {/* DB Status */}
            <div className="card flex items-start gap-4">
              <div className="p-3 bg-neutral-100 rounded-lg">
                <Database className="w-6 h-6 text-neutral-600" />
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between mb-1">
                  <h3 className="font-bold text-neutral-800">Dependencies</h3>
                  <span className={`rounded-full h-3 w-3 ${getStatusColor('healthy')}`}></span>
                </div>
                <p className="text-xs text-neutral-500 mb-2">External Services</p>
                <div className="text-xs space-y-1">
                  {Object.entries(health.dependencies || {}).map(([key, val]) => (
                    <div key={key} className="flex justify-between border-b border-neutral-50 pb-1">
                      <span className="text-neutral-400 capitalize">{key.replace(/_/g, ' ')}:</span>
                      <span className={val === 'available' ? 'text-emerald-600' : 'text-red-500'}>{val}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Vision AI Status */}
            <div className="card flex items-start gap-4">
              <div className="p-3 bg-neutral-100 rounded-lg">
                <BrainCircuit className="w-6 h-6 text-neutral-600" />
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between mb-1">
                  <h3 className="font-bold text-neutral-800">Vision AI Pipeline</h3>
                  <span className={`rounded-full h-3 w-3 ${getStatusColor(visionHealth?.gemini_status)}`}></span>
                </div>
                <p className="text-xs text-neutral-500 mb-2">Gemini Pro & FAISS</p>
                {visionHealth && (
                  <div className="text-sm">
                    <p>Gemini: {visionHealth.gemini_status}</p>
                    <p>FAISS: {visionHealth.faiss_status}</p>
                    <p className="mt-1 text-xs text-neutral-400">Total Analyses: {visionHealth.total_analyses}</p>
                  </div>
                )}
              </div>
            </div>

          </div>
        </div>
      )}
    </div>
  );
}
