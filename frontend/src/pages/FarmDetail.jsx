import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft, Phone, MapPin, Crop, Ruler, Activity,
  Bug, CloudRain, AlertTriangle, Leaf
} from 'lucide-react';
import { useFarm } from '../hooks/useFarms';
import { useWeather, useHourlySoilMoisture } from '../hooks/useWeather';
import { useFarmInsights } from '../hooks/useInsights';
import { useFarmAlerts } from '../hooks/useAlerts';
import StatCard from '../components/StatCard';
import FarmMap from '../components/FarmMap';
import WeatherWidget from '../components/WeatherWidget';
import InsightCard from '../components/InsightCard';
import AlertBadge from '../components/AlertBadge';
import SMSPreview from '../components/SMSPreview';
import SoilHealthRadar from '../components/SoilHealthRadar';
import { sendInsightSMS } from '../api/insights';
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
  const { farmId } = useParams();
  const [activeTab, setActiveTab] = useState('Overview');
  const [severityFilter, setSeverityFilter] = useState('all');
  const [smsFarm, setSMSFarm] = useState(null);

  const { data: farm, isLoading, error } = useFarm(farmId);
  const { data: weather } = useWeather(farmId);
  const { data: hourlySoil } = useHourlySoilMoisture(farmId);
  const { data: insights } = useFarmInsights(farmId);
  const { data: alerts } = useFarmAlerts(farmId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-primary-300 border-t-primary-500 rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !farm) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3 text-danger-500">
        <AlertTriangle size={36} />
        <p className="font-medium">{error?.message || 'Farm not found'}</p>
        <Link to="/" className="text-sm text-primary-500 hover:underline">← Back to Dashboard</Link>
      </div>
    );
  }

  const filteredAlerts = (alerts || []).filter(
    (a) => severityFilter === 'all' || a.severity === severityFilter
  );

  return (
    <div className="space-y-5">
      {/* Back link */}
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-neutral-400 hover:text-neutral-700">
        <ArrowLeft size={15} />
        All Farms
      </Link>

      {/* Header Card */}
      <div className="card">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h1 className="text-xl font-bold text-neutral-800">{farm.name}</h1>
              <span className="bg-primary-50 text-primary-700 text-xs font-medium px-2.5 py-0.5 rounded-full">
                {farm.season}
              </span>
            </div>
            <div className="flex flex-wrap gap-4 mt-2 text-sm text-neutral-500">
              <span className="flex items-center gap-1.5">
                <MapPin size={13} /> {farm.location}
              </span>
              <span className="flex items-center gap-1.5">
                <Leaf size={13} /> {farm.crop_type}
              </span>
              <span className="flex items-center gap-1.5">
                <Ruler size={13} /> {farm.area_ha} ha
              </span>
              <span className="flex items-center gap-1.5">
                <Phone size={13} />
                <a href={`tel:${farm.farmer_phone}`} className="hover:text-primary-600">
                  {farm.farmer_name} · {farm.farmer_phone}
                </a>
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
            id={`tab-${tab.replace(/\s+/g, '-').toLowerCase()}`}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2.5 text-sm transition-colors ${
              activeTab === tab ? 'tab-active' : 'tab-inactive'
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
              <FarmMap zones={farm.zones} farmName={farm.name} />
            </div>
            <div className='lg:col-span-2 grid grid-cols-1 gap-4'>
              <StatCard
                title='Current NDVI'
                value={farm.current_ndvi.toFixed(2)}
                icon={Activity}
                colorClass='bg-teal-50'
                trend={farm.current_ndvi > 0.6 ? 'up' : 'down'}
                trendLabel={farm.current_ndvi > 0.7 ? 'Healthy canopy' : 'Moderate stress'}
              />
              <StatCard
                title='Last Pest Detection'
                value={new Date(farm.last_pest_detection).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
                icon={Bug}
                colorClass='bg-amber-50'
                trend='flat'
                trendLabel={`${Math.floor((new Date() - new Date(farm.last_pest_detection)) / 86400000)} days ago`}
              />
              <StatCard
                title='Days Since Last Rain'
                value={farm.days_since_last_rain}
                unit='days'
                icon={CloudRain}
                colorClass='bg-blue-50'
                danger={farm.days_since_last_rain > 10}
                trend={farm.days_since_last_rain > 7 ? 'down' : 'flat'}
                trendLabel={farm.days_since_last_rain > 10 ? 'Critical dry spell' : 'Within normal range'}
              />
            </div>
          </div>
          {/* Soil Health Radar */}
          <div className='card'>
            <SoilHealthRadar
              soilData={{
                nitrogen: Math.round(farm.soil_moisture_avg * 0.9),
                phosphorus: Math.round(farm.soil_moisture_avg * 0.7),
                potassium: Math.round(farm.current_ndvi * 100 * 0.85),
                ph: 65,
                organic_matter: Math.round(farm.current_ndvi * 100 * 0.65),
                moisture: farm.soil_moisture_avg,
              }}
            />
          </div>
        </div>
      )}

      {/* TAB: Weather */}
      {activeTab === 'Weather' && (
        <div className="space-y-5">
          <div className="card">
            <h2 className="text-sm font-semibold text-neutral-700 mb-4">7-Day Forecast</h2>
            {weather?.daily ? (
              <WeatherWidget forecast={weather.daily} />
            ) : (
              <p className="text-sm text-neutral-400">No forecast data available.</p>
            )}
          </div>
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
              <p className="text-sm text-neutral-400">No hourly data available.</p>
            )}
          </div>
          <div className="card">
            <DroughtBar score={farm.drought_risk_score} />
          </div>
        </div>
      )}

      {/* TAB: AI Insights */}
      {activeTab === 'AI Insights' && (
        <div className="space-y-4">
          {!insights || insights.length === 0 ? (
            <div className="card flex flex-col items-center justify-center py-16 text-neutral-400 gap-3">
              <Activity size={32} />
              <p className="text-sm">No AI insights available for this farm yet.</p>
            </div>
          ) : (
            insights.map((insight) => (
              <InsightCard
                key={insight.id}
                insight={insight}
                onSendSMS={() => setSMSFarm(insight)}
              />
            ))
          )}
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
                  id={`filter-${s}`}
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
                  {['Date', 'Alert Type', 'Message', 'Delivery', 'Acknowledged'].map((h) => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-50">
                {filteredAlerts.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-12 text-center">
                      <div className="flex flex-col items-center gap-2 text-neutral-400">
                        <AlertTriangle size={28} />
                        <p className="text-sm">No {severityFilter !== 'all' ? severityFilter : ''} alerts for this farm.</p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  filteredAlerts.map((a) => (
                    <tr key={a.id} className="hover:bg-neutral-50">
                      <td className="px-4 py-3 text-xs text-neutral-400 whitespace-nowrap">
                        {new Date(a.timestamp).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                      </td>
                      <td className="px-4 py-3 font-medium text-neutral-700 whitespace-nowrap">{a.alert_type}</td>
                      <td className="px-4 py-3 text-neutral-600 max-w-xs truncate" title={a.message}>{a.message}</td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className={
                          a.delivery_status === 'delivered' ? 'badge-success' :
                          a.delivery_status === 'failed' ? 'badge-critical' :
                          a.delivery_status === 'pending' ? 'badge-warning' : 'text-xs text-neutral-300'
                        }>
                          {a.delivery_status.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {a.farmer_acknowledged
                          ? <span className="badge-success">Yes</span>
                          : <span className="text-xs text-neutral-300">No</span>}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* SMS Modal */}
      {smsFarm && (
        <SMSPreview
          message={smsFarm.sms_template}
          farmName={farm.name}
          onConfirm={async (msg) => {
            await sendInsightSMS(smsFarm.id, farmId);
          }}
          onClose={() => setSMSFarm(null)}
        />
      )}
    </div>
  );
}
