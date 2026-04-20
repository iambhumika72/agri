import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { BugOff } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import FarmSelector from '../components/FarmSelector';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorBanner from '../components/ErrorBanner';
import EmptyState from '../components/EmptyState';
import SeverityBadge from '../components/SeverityBadge';
import { historyAPI } from '../api/client';

export default function PestHistoryPage() {
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

    // Look back 1 year for history
    const endDate = new Date().toISOString().split('T')[0];
    const startDate = new Date(Date.now() - 365 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

    historyAPI.getPestHistory(farmId, startDate, endDate)
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

  const getSeverityLabel = (num) => {
    if (num <= 1) return 'Low';
    if (num <= 2) return 'Moderate';
    if (num <= 3) return 'Severe';
    return 'Critical';
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-24 md:pb-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <PageHeader 
          titleKey="Pest History Timeline" 
          descKey="Past pest outbreaks and severity." 
          icon={BugOff} 
        />
        <FarmSelector value={farmId} onChange={setFarmId} />
      </div>

      {!farmId && (
        <EmptyState message="Please select a Farm ID to view pest history." />
      )}

      {farmId && loading && <LoadingSpinner message="Fetching pest records..." />}

      {farmId && error && <ErrorBanner message={error} onRetry={handleRetry} />}

      {farmId && !loading && !error && (
        <div className="card overflow-hidden p-0">
          <div className="px-5 py-4 border-b border-neutral-100 flex items-center justify-between">
            <h2 className="text-base font-semibold text-neutral-800">Timeline (Last 12 Months)</h2>
          </div>
          
          {records.length > 0 ? (
            <div className="p-6">
              <div className="relative border-l-2 border-neutral-200 ml-3 space-y-8">
                {records.sort((a, b) => new Date(b.detected_date) - new Date(a.detected_date)).map((r) => (
                  <div key={r.pest_id} className="relative pl-6">
                    <div className="absolute w-3 h-3 bg-white border-2 border-primary-500 rounded-full -left-[7px] top-1.5" />
                    <div className="flex flex-col sm:flex-row sm:items-center gap-2 mb-1">
                      <h3 className="text-sm font-bold text-neutral-800">{r.pest_name}</h3>
                      <SeverityBadge level={getSeverityLabel(r.severity)} />
                    </div>
                    <p className="text-xs text-neutral-500 mb-2">
                      Detected: {new Date(r.detected_date).toLocaleDateString('en-IN')} 
                      {r.resolved_date && ` • Resolved: ${new Date(r.resolved_date).toLocaleDateString('en-IN')}`}
                    </p>
                    <p className="text-sm text-neutral-600">
                      <strong>Affected Area:</strong> {r.affected_area_pct}%
                    </p>
                    {r.treatment_applied && (
                      <p className="text-sm text-neutral-600">
                        <strong>Treatment:</strong> {r.treatment_applied}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <EmptyState message="No pest outbreaks recorded in the last year." />
          )}
        </div>
      )}
    </div>
  );
}
