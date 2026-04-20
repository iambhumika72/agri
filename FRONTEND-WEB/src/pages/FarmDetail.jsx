import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowLeft, Phone, MapPin, Crop, Ruler, Activity,
  Bug, CloudRain, AlertTriangle, Leaf
} from 'lucide-react';
import FarmSelector from '../components/FarmSelector';
import StatCard from '../components/StatCard';
import FarmMap from '../components/FarmMap';
import WeatherWidget from '../components/WeatherWidget';
import AlertBadge from '../components/AlertBadge';
import SMSPreview from '../components/SMSPreview';
import SoilHealthRadar from '../components/SoilHealthRadar';
import PageHeader from '../components/PageHeader';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorBanner from '../components/ErrorBanner';
import EmptyState from '../components/EmptyState';
import { historyAPI, alertsAPI } from '../api/client';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';

const TABS = ['Overview', 'Weather', 'AI Insights', 'Alert History'];

function DroughtBar({ score }) {
  const color = score > 70 ? 'bg-danger-500' : score > 45 ? 'bg-amber-400' : 'bg-teal-400';
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-neutral-500 font-medium">Drought Risk Score</span>
        <span className={`font-bold ${score > 70 ? 'text-danger-600' : 'text-neutral-700'}`}>
          {Math.round(score)} / 100
        </span>
      </div>
      <div className="h-3 bg-neutral-100 rounded-full overflow-hidden">
        <div
          className={`h-3 rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${score}%` }}
        />
      </div>
      {score > 70 && (
        <p className="text-xs text-danger-500 font-medium mt-1 flex items-center gap-1">
          <AlertTriangle size={12} /> High drought risk — immediate irrigation recommended
        </p>
      )}
    </div>
  );
}

export default function FarmDetail() {
  const [farmId, setFarmId] = useState('');
  const [activeTab, setActiveTab] = useState('Overview');
  const [severityFilter, setSeverityFilter] = useState('all');
  
  const [summary, setSummary] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [soil, setSoil] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchFarmData = async () => {
    if (!farmId) return;
    setLoading(true);
    setError(null);
    try {
      const [summaryData, alertsData, soilData] = await Promise.all([
        historyAPI.getFarmSummary(farmId),
        alertsAPI.getAlerts(farmId).catch(() => ({ recent_alerts: [] })),
        historyAPI.getSoilHealth(farmId, 24).catch(() => [])
      ]);
      setSummary(summaryData);
      setAlerts(alertsData?.recent_alerts || []);
      setSoil(soilData || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFarmData();
  }, [farmId]);

  const filteredAlerts = alerts.filter(
    (a) => severityFilter === 'all' || a.severity === severityFilter
  );

  const hourlySoil = soil.map((s, i) => ({
    hour: `${i}:00`,
    moisture: s.moisture_pct || 0
  }));

  return (
    <div className="max-w-7xl mx-auto space-y-5 pb-24 md:pb-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <PageHeader 
          titleKey="page.farms.title" 
          descKey="page.farms.desc" 
          icon={Leaf} 
        />
        <FarmSelector value={farmId} onChange={setFarmId} />
      </div>

      <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-neutral-400 hover:text-neutral-700">
        <ArrowLeft size={15} />
        Dashboard
      </Link>

      {!farmId && (
        <EmptyState message="Please select a Farm ID to view details." />
      )}

      {farmId && loading && <LoadingSpinner message="Loading farm details..." />}

      {farmId && error && <ErrorBanner message={error} onRetry={fetchFarmData} />}

      {farmId && !loading && !error && summary && (
        <>
          {/* Header Card */}
          <div className="card">
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <h1 className="text-xl font-bold text-neutral-800">{farmId}</h1>
                  <span className="bg-primary-50 text-primary-700 text-xs font-medium px-2.5 py-0.5 rounded-full">
                    Active
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex border-b border-neutral-200 gap-1">
            {TABS.map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2.5 text-sm transition-colors ${
                  activeTab === tab ? 'tab-active border-b-2 border-emerald-500 text-emerald-600 font-medium' : 'text-neutral-500 hover:text-neutral-700'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          {/* TAB: Overview */}
          {activeTab === 'Overview' && (
            <div className='space-y-5'>
              <div className='grid grid-cols-1 lg:grid-cols-5 gap-4'>
                <div className='lg:col-span-3 card'>
                  <FarmMap zones={[]} farmName={farmId} />
                </div>
                <div className='lg:col-span-2 grid grid-cols-1 gap-4'>
                  <StatCard
                    title='Pest Risk Score'
                    value={summary.pest_risk_score !== null ? summary.pest_risk_score.toFixed(2) : '0.00'}
                    icon={Bug}
                    colorClass='bg-amber-50'
                    trend={summary.pest_risk_score > 0.5 ? 'up' : 'down'}
                    trendLabel={summary.pest_risk_score > 0.5 ? 'High Risk' : 'Low Risk'}
                  />
                  <StatCard
                    title='Irrigation Efficiency'
                    value={summary.irrigation_efficiency ? `${Math.round(summary.irrigation_efficiency * 100)}%` : 'N/A'}
                    icon={CloudRain}
                    colorClass='bg-blue-50'
                  />
                </div>
              </div>
              <div className='card'>
                <SoilHealthRadar
                  soilData={{
                    nitrogen: 50,
                    phosphorus: 50,
                    potassium: 50,
                    ph: 50,
                    organic_matter: 50,
                    moisture: 50,
                  }}
                />
              </div>
            </div>
          )}

          {/* TAB: Weather */}
          {activeTab === 'Weather' && (
            <div className="space-y-5">
              <div className="card">
                <h2 className="text-sm font-semibold text-neutral-700 mb-4">
                  Today — Hourly Soil Moisture
                </h2>
                {hourlySoil && hourlySoil.length > 0 ? (
                  <ResponsiveContainer width="100%" height={180}>
                    <LineChart data={hourlySoil} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#EEEEED" />
                      <XAxis dataKey="hour" tick={{ fontSize: 10, fill: '#5F5E5A' }} axisLine={{ stroke: '#D8D8D6' }} tickLine={false} />
                      <YAxis tick={{ fontSize: 10, fill: '#5F5E5A' }} axisLine={false} tickLine={false} domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
                      <Tooltip formatter={(v) => [`${Math.round(v)}%`, 'Soil Moisture']} />
                      <Line type="monotone" dataKey="moisture" stroke="#1D9E75" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <EmptyState message="No hourly soil data available." />
                )}
              </div>
              <div className="card">
                <DroughtBar score={35} />
              </div>
            </div>
          )}

          {/* TAB: AI Insights */}
          {activeTab === 'AI Insights' && (
            <div className="space-y-4">
              <div className="card flex flex-col items-center justify-center py-16 text-neutral-400 gap-3">
                <Activity size={32} />
                <p className="text-sm">No new AI insights available for this farm yet.</p>
              </div>
            </div>
          )}

          {/* TAB: Alert History */}
          {activeTab === 'Alert History' && (
            <div className="card overflow-hidden p-0">
              <div className="px-5 py-4 border-b border-neutral-100 flex items-center gap-3 flex-wrap">
                <h2 className="text-sm font-semibold text-neutral-700">Alert History</h2>
                <div className="ml-auto flex gap-2">
                  {['all', 'critical', 'warning', 'info'].map((s) => (
                    <button
                      key={s}
                      onClick={() => setSeverityFilter(s)}
                      className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                        severityFilter === s
                          ? 'bg-primary-500 text-white border-primary-500'
                          : 'bg-white text-neutral-500 border-neutral-200 hover:border-neutral-300'
                      }`}
                    >
                      {s.charAt(0).toUpperCase() + s.slice(1)}
                    </button>
                  ))}
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-neutral-50 border-b border-neutral-100">
                      {['Date', 'Alert Type', 'Message'].map((h) => (
                        <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-50">
                    {filteredAlerts.length === 0 ? (
                      <tr>
                        <td colSpan={3} className="px-4 py-12 text-center">
                          <div className="flex flex-col items-center gap-2 text-neutral-400">
                            <AlertTriangle size={28} />
                            <p className="text-sm">No {severityFilter !== 'all' ? severityFilter : ''} alerts for this farm.</p>
                          </div>
                        </td>
                      </tr>
                    ) : (
                      filteredAlerts.map((a) => (
                        <tr key={a.alert_id} className="hover:bg-neutral-50">
                          <td className="px-4 py-3 text-xs text-neutral-400 whitespace-nowrap">
                            {new Date(a.triggered_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                          </td>
                          <td className="px-4 py-3 font-medium text-neutral-700 whitespace-nowrap">
                            <AlertBadge severity={a.severity} /> {a.alert_type}
                          </td>
                          <td className="px-4 py-3 text-neutral-600 max-w-xs truncate" title={a.message}>{a.message}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
