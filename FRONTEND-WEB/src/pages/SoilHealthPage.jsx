import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { FlaskConical } from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import PageHeader from '../components/PageHeader';
import FarmSelector from '../components/FarmSelector';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorBanner from '../components/ErrorBanner';
import EmptyState from '../components/EmptyState';
import SeverityBadge from '../components/SeverityBadge';
import { historyAPI } from '../api/client';

export default function SoilHealthPage() {
  const { t } = useTranslation();
  const [farmId, setFarmId] = useState('');
  
  const [records, setRecords] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!farmId) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

    Promise.all([
      historyAPI.getSoilHealth(farmId, 10),
      historyAPI.getFarmSummary(farmId).catch(() => null)
    ])
      .then(([soilData, summaryData]) => {
        if (!isMounted) return;
        setRecords(soilData || []);
        setSummary(summaryData);
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

  const chartData = records.map(r => ({
    date: new Date(r.recorded_date).toLocaleDateString('en-IN', { month: 'short', year: '2-digit' }),
    N: r.nitrogen_ppm || 0,
    P: r.phosphorus_ppm || 0,
    K: r.potassium_ppm || 0,
  })).reverse();

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-24 md:pb-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <PageHeader 
          titleKey="Soil Health" 
          descKey="Track NPK trends and soil deficiencies." 
          icon={FlaskConical} 
        />
        <FarmSelector value={farmId} onChange={setFarmId} />
      </div>

      {!farmId && (
        <EmptyState message="Please select a Farm ID to view soil health." />
      )}

      {farmId && loading && <LoadingSpinner message="Fetching soil records..." />}

      {farmId && error && <ErrorBanner message={error} onRetry={handleRetry} />}

      {farmId && !loading && !error && (
        <div className="space-y-6">
          
          {summary && summary.soil_deficiencies && summary.soil_deficiencies.length > 0 && (
            <div className="bg-orange-50 border border-orange-200 p-4 rounded-lg flex flex-col gap-2">
              <h3 className="text-orange-800 font-bold text-sm">Identified Deficiencies</h3>
              <div className="flex flex-wrap gap-2">
                {summary.soil_deficiencies.map(def => (
                  <SeverityBadge key={def} level="moderate" /> 
                ))}
              </div>
            </div>
          )}

          <div className="card">
            <h2 className="text-sm font-semibold text-neutral-700 mb-4">NPK Trends Over Time</h2>
            {records.length > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#EEEEED" />
                    <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#5F5E5A' }} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: '#5F5E5A' }} tickLine={false} axisLine={false} />
                    <Tooltip contentStyle={{ fontSize: '12px', borderRadius: '8px' }} />
                    <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
                    <Line type="monotone" dataKey="N" name="Nitrogen (ppm)" stroke="#3B82F6" strokeWidth={2} dot={{ r: 3 }} />
                    <Line type="monotone" dataKey="P" name="Phosphorus (ppm)" stroke="#F59E0B" strokeWidth={2} dot={{ r: 3 }} />
                    <Line type="monotone" dataKey="K" name="Potassium (ppm)" stroke="#8B5CF6" strokeWidth={2} dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <EmptyState message="No soil health data available for this farm." />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
