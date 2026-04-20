import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { LineChart as ChartIcon } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import FarmSelector from '../components/FarmSelector';
import YieldChart from '../components/YieldChart';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorBanner from '../components/ErrorBanner';
import EmptyState from '../components/EmptyState';
import { historyAPI } from '../api/client';

export default function YieldHistoryPage() {
  const { t } = useTranslation();
  const [farmId, setFarmId] = useState('');
  
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!farmId) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

    // Provide a dummy crop_id for now as it is required by the backend schema
    const dummyCropId = '00000000-0000-0000-0000-000000000000';

    historyAPI.getYieldHistory(farmId, dummyCropId, 5)
      .then(data => {
        if (!isMounted) return;
        setRecords(data || []);
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
    const current = farmId;
    setFarmId('');
    setTimeout(() => setFarmId(current), 10);
  };

  // Convert kg/hectare to tons/hectare for the chart
  const chartData = records
    .sort((a, b) => a.year - b.year)
    .map(r => {
      const yieldTons = r.yield_kg_per_hectare / 1000;
      return {
        day: `${r.season} ${r.year}`,
        yield: yieldTons,
        lower: yieldTons * 0.9, // mock confidence interval for visual consistency
        upper: yieldTons * 1.1,
      };
    });

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-24 md:pb-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <PageHeader 
          titleKey="page.yield.title" 
          descKey="page.yield.desc" 
          icon={ChartIcon} 
        />
        <FarmSelector value={farmId} onChange={setFarmId} />
      </div>

      {!farmId && (
        <EmptyState message="Please select a Farm ID to view yield history." />
      )}

      {farmId && loading && <LoadingSpinner message="Fetching yield records..." />}

      {farmId && error && <ErrorBanner message={error} onRetry={handleRetry} />}

      {farmId && !loading && !error && (
        <div className="space-y-6">
          <div className="card">
            <h2 className="text-sm font-semibold text-neutral-700 mb-4">Yield Over Seasons</h2>
            {records.length > 0 ? (
              <YieldChart data={chartData} />
            ) : (
              <EmptyState message="No yield history available for this farm." />
            )}
          </div>

          {records.length > 0 && (
            <div className="card overflow-hidden p-0">
              <div className="px-5 py-4 border-b border-neutral-100 flex items-center justify-between">
                <h2 className="text-base font-semibold text-neutral-800">Raw Records</h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-neutral-50 border-b border-neutral-100">
                      <th className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wider">Season</th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wider">Year</th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wider">Crop</th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wider">Harvest Date</th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wider">Yield (kg/ha)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-50">
                    {records.map((r) => (
                      <tr key={r.record_id} className="hover:bg-neutral-50 transition-colors">
                        <td className="px-4 py-3 text-neutral-800 font-medium">{r.season}</td>
                        <td className="px-4 py-3 text-neutral-600">{r.year}</td>
                        <td className="px-4 py-3 text-neutral-600">{r.crop_name || 'Unknown'}</td>
                        <td className="px-4 py-3 text-neutral-400 text-xs whitespace-nowrap">
                          {new Date(r.harvest_date).toLocaleDateString('en-IN')}
                        </td>
                        <td className="px-4 py-3 font-medium text-emerald-600">
                          {r.yield_kg_per_hectare.toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
