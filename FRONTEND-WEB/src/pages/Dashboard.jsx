import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, LayoutDashboard, Target, Droplets, Activity, Leaf } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import FarmSelector from '../components/FarmSelector';
import FarmHealthScore from '../components/FarmHealthScore';
import StatCard from '../components/StatCard';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorBanner from '../components/ErrorBanner';
import EmptyState from '../components/EmptyState';
import { historyAPI, visionAPI } from '../api/client';

export default function Dashboard() {
  const { t } = useTranslation();
  const [farmId, setFarmId] = useState('');
  
  const [summary, setSummary] = useState(null);
  const [vision, setVision] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!farmId) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

    Promise.all([
      historyAPI.getFarmSummary(farmId).catch(e => { throw new Error(`Summary: ${e.message}`); }),
      visionAPI.getAnalysisResult(farmId).catch(e => null) // Mocked, shouldn't fail
    ])
      .then(([summaryData, visionData]) => {
        if (!isMounted) return;
        setSummary(summaryData);
        setVision(visionData);
      })
      .catch(err => {
        if (!isMounted) return;
        setError(err.message);
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => { isMounted = false; };
  }, [farmId]);

  const handleRetry = () => {
    // Trigger re-fetch by toggling farmId temporarily if needed, or just let user re-select
    const current = farmId;
    setFarmId('');
    setTimeout(() => setFarmId(current), 10);
  };

  const hasUrgentIssue = vision && ['immediate', 'within_3_days'].includes(vision.urgency_level);

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-24 md:pb-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <PageHeader 
          titleKey="page.dashboard.title" 
          descKey="page.dashboard.desc" 
          icon={LayoutDashboard} 
        />
        <FarmSelector value={farmId} onChange={setFarmId} />
      </div>

      {!farmId && (
        <EmptyState message="Please enter or select a Farm ID to view dashboard data." />
      )}

      {farmId && loading && <LoadingSpinner message="Fetching farm data..." />}

      {farmId && error && <ErrorBanner message={error} onRetry={handleRetry} />}

      {farmId && !loading && !error && summary && (
        <>
          {hasUrgentIssue && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-3 animate-pulse">
              <AlertTriangle className="w-5 h-5 text-red-500" />
              <div className="flex-1">
                <p className="font-bold">Urgent Action Required</p>
                <p className="text-sm">Vision analysis detected an issue that requires your immediate attention.</p>
              </div>
            </div>
          )}

          {vision && (
            <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-2 rounded-lg text-sm font-medium text-center shadow-sm">
              🛰️ Satellite analysis coming soon (Showing mock data)
            </div>
          )}

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard 
              title="Pest Risk Score" 
              value={summary.pest_risk_score !== null ? summary.pest_risk_score.toFixed(2) : 'N/A'} 
              icon={Target} 
              colorClass="bg-red-50" 
              trend={summary.pest_risk_score > 0.5 ? 'up' : 'down'}
              trendLabel={summary.pest_risk_score > 0.5 ? 'High Risk' : 'Low Risk'}
            />
            <StatCard 
              title="Irrigation Efficiency" 
              value={summary.irrigation_efficiency ? `${Math.round(summary.irrigation_efficiency * 100)}%` : 'N/A'} 
              icon={Droplets} 
              colorClass="bg-blue-50" 
            />
            <StatCard 
              title="Soil Deficiencies" 
              value={summary.soil_deficiencies?.length || 0} 
              icon={Activity} 
              colorClass="bg-orange-50" 
              trendLabel={summary.soil_deficiencies?.join(', ') || 'None'}
            />
            <StatCard 
              title="Yield Trend" 
              value={summary.yield_history?.length ? `${summary.yield_history[0].yield_kg_per_hectare} kg/ha` : 'N/A'} 
              icon={Leaf} 
              colorClass="bg-emerald-50" 
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="card">
              <h2 className="text-sm font-semibold text-neutral-700 mb-4">Farm Health Overview</h2>
              {vision ? (
                <FarmHealthScore 
                  score={vision.health_score} 
                  subScores={[
                    { label: 'Crop Vigour', value: 80, color: '#1D9E75' },
                    { label: 'Pest Risk', value: Math.round((1 - (summary.pest_risk_score || 0)) * 100), color: '#A32D2D' }
                  ]} 
                />
              ) : (
                <EmptyState message="No vision analysis available." />
              )}
            </div>
            <div className="card">
               <h2 className="text-sm font-semibold text-neutral-700 mb-4">LLM Summary</h2>
               <pre className="text-xs bg-neutral-50 p-4 rounded-md overflow-x-auto border border-neutral-100 text-neutral-600">
                 {JSON.stringify(summary, null, 2)}
               </pre>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
