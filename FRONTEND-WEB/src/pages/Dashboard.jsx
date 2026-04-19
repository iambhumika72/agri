import { Tractor, Droplets, Bell, Clock, AlertTriangle, Leaf } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import StatCard from '../components/StatCard';
import YieldChart from '../components/YieldChart';
import SoilMoistureGauge from '../components/SoilMoistureGauge';
import WeatherWidget from '../components/WeatherWidget';
import AlertBadge from '../components/AlertBadge';
import FarmHealthScore from '../components/FarmHealthScore';
import CropCalendarStrip from '../components/CropCalendarStrip';
import DataFreshnessBar from '../components/DataFreshnessBar';
import PageHeader from '../components/PageHeader';
import { LayoutDashboard } from 'lucide-react';
import { useFarms } from '../hooks/useFarms';
import { useAlerts } from '../hooks/useAlerts';
import { useAllWeather } from '../hooks/useWeather';

const CROP_CALENDAR = [
  { name: 'Rice (Kharif)', sowMonth: 6, harvestMonth: 10 },
  { name: 'Wheat (Rabi)', sowMonth: 11, harvestMonth: 3 },
  { name: 'Cotton (Kharif)', sowMonth: 5, harvestMonth: 11 },
  { name: 'Mustard (Rabi)', sowMonth: 10, harvestMonth: 2 },
  { name: 'Moong (Zaid)', sowMonth: 4, harvestMonth: 6 },
];

// Mock farm health sub-scores
const HEALTH_SUBSCORES = [
  { label: 'Soil Health', value: 74, color: '#3B6D11' },
  { label: 'Crop Vigour', value: 68, color: '#1D9E75' },
  { label: 'Water Status', value: 52, color: '#2563eb' },
  { label: 'Pest Risk', value: 38, color: '#A32D2D' },
];

function SkeletonCard() {
  return <div className="card skeleton h-24" />;
}

function LoadingRow() {
  return (
    <tr>
      <td colSpan={6} className="px-4 py-8 text-center">
        <div className="flex items-center justify-center gap-2 text-neutral-400 text-sm">
          <div className="w-4 h-4 border-2 border-primary-300 border-t-primary-500 rounded-full animate-spin" />
          Loading…
        </div>
      </td>
    </tr>
  );
}

export default function Dashboard() {
  const { t } = useTranslation();
  const { data: farms, isLoading: farmsLoading, error: farmsError } = useFarms();
  const { data: alerts, isLoading: alertsLoading } = useAlerts();
  const { data: allWeather, dataUpdatedAt } = useAllWeather();

  const totalFarms = farms?.length || 0;
  const avgMoisture = farms
    ? Math.round(farms.reduce((sum, f) => sum + f.soil_moisture_avg, 0) / farms.length)
    : 0;

  const todayAlerts = alerts?.filter((a) => {
    const d = new Date(a.timestamp);
    const now = new Date();
    return d.toDateString() === now.toDateString();
  }) || [];

  const nextIrrigation = farms
    ? [...farms].sort((a, b) => a.next_irrigation_hours - b.next_irrigation_hours)[0]
    : null;

  const aggregatedYield = farms
    ? farms[0]?.yield_forecast?.map((day, idx) => ({
        day: day.day,
        yield: parseFloat((farms.reduce((sum, f) => sum + (f.yield_forecast[idx]?.yield || 0), 0) / farms.length).toFixed(2)),
        lower: parseFloat((farms.reduce((sum, f) => sum + (f.yield_forecast[idx]?.lower || 0), 0) / farms.length).toFixed(2)),
        upper: parseFloat((farms.reduce((sum, f) => sum + (f.yield_forecast[idx]?.upper || 0), 0) / farms.length).toFixed(2)),
      }))
    : [];

  const dashboardWeather = allWeather?.['farm-001']?.daily || [];

  // Compute aggregate health score
  const avgNdvi = farms ? farms.reduce((s, f) => s + f.current_ndvi, 0) / farms.length : 0;
  const healthScore = farms
    ? Math.round(avgMoisture * 0.3 + avgNdvi * 100 * 0.4 + (100 - (todayAlerts.length * 10)) * 0.3)
    : 0;

  if (farmsError) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3 text-danger-500">
        <AlertTriangle size={36} />
        <p className="font-medium">{t('common.error')}</p>
        <p className="text-sm text-neutral-400">{farmsError.message}</p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-24 md:pb-8">
      <PageHeader 
        titleKey="page.dashboard.title" 
        descKey="page.dashboard.desc" 
        icon={LayoutDashboard} 
      />

      {/* Live data pulse indicator */}
      <div className="flex items-center justify-end px-6 md:px-0" style={{ animation: 'fadeIn 300ms ease-out both' }}>
        <div className="flex items-center gap-2 text-xs text-teal-600 font-medium bg-teal-50 px-3 py-1.5 rounded-full">
          <Leaf size={12} />
          <span>{totalFarms} {t('dashboard.activeFarms')}</span>
        </div>
      </div>

      {/* Stat Cards Row — staggered slideInUp */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {farmsLoading ? (
          Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)
        ) : (
          <>
            {[
              { title: t('dashboard.activeFarms'), value: totalFarms, icon: Tractor, colorClass: 'bg-primary-50', trend: 'flat', trendLabel: t('common.allRegistered') },
              { title: t('dashboard.avgMoisture'), value: avgMoisture, unit: '%', icon: Droplets, colorClass: 'bg-blue-50', trend: avgMoisture > 60 ? 'up' : avgMoisture < 35 ? 'down' : 'flat', trendLabel: avgMoisture > 60 ? 'Above optimal' : avgMoisture < 35 ? 'Below threshold' : t('common.withinRange') },
              { title: t('dashboard.alertsToday'), value: todayAlerts.length, icon: Bell, colorClass: 'bg-danger-50', danger: todayAlerts.length > 0, trend: todayAlerts.length > 0 ? 'up' : 'flat', trendLabel: todayAlerts.length > 0 ? `${todayAlerts.filter((a) => a.severity === 'critical').length} ${t('common.criticalCount')}` : t('common.noAlerts') },
              { title: t('dashboard.nextIrrigation'), value: nextIrrigation ? `${Math.round(nextIrrigation.next_irrigation_hours)}h` : '—', icon: Clock, colorClass: 'bg-amber-50', trendLabel: nextIrrigation?.name || '', trend: 'flat' },
            ].map((props, i) => (
              <div key={props.title} style={{ animation: 'slideInUp 400ms ease-out both', animationDelay: `${i * 100}ms` }}>
                <StatCard {...props} />
              </div>
            ))}
          </>
        )}
      </div>

      {/* Farm Health Score — spans 2 cols */}
      {!farmsLoading && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <FarmHealthScore score={Math.min(100, Math.max(0, healthScore))} subScores={HEALTH_SUBSCORES} />
        </div>
      )}

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="card lg:col-span-3">
          <h2 className="text-sm font-semibold text-neutral-700 mb-4">{t('dashboard.yieldForecast')}</h2>
          {farmsLoading ? <div className="skeleton h-48 rounded-lg" /> : <YieldChart data={aggregatedYield} />}
        </div>
        <div className="card lg:col-span-2">
          <h2 className="text-sm font-semibold text-neutral-700 mb-2">{t('dashboard.soilMoisture')}</h2>
          {farmsLoading ? <div className="skeleton h-48 rounded-lg" /> : <SoilMoistureGauge farms={farms || []} />}
        </div>
      </div>

      {/* Weather Widget */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-neutral-700">{t('dashboard.weatherForecast')} — Krishnamurthy Fields</h2>
          <DataFreshnessBar updatedAt={dataUpdatedAt ? new Date(dataUpdatedAt).toISOString() : undefined} label="Weather" />
        </div>
        <div style={{ animation: 'slideInRight 400ms ease-out both' }}>
          <WeatherWidget forecast={dashboardWeather} />
        </div>
      </div>

      {/* Crop Calendar Strip */}
      <div className="card">
        <h2 className="text-sm font-semibold text-neutral-700 mb-4">{t('weather.crop_season')}</h2>
        <CropCalendarStrip crops={CROP_CALENDAR} />
      </div>

      {/* Recent Alerts Table */}
      <div className="card overflow-hidden p-0">
        <div className="px-5 py-4 border-b border-neutral-100 flex items-center justify-between">
          <h2 className="text-base font-semibold text-neutral-800">{t('nav.farms')}</h2>
          <Link to="/farms" className="text-sm text-primary-600 font-medium hover:text-primary-700">
            {t('dashboard.viewAll')} &rarr;
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-neutral-50 border-b border-neutral-100">
                {['Farm', 'Alert Type', 'Severity', 'Time', 'SMS Sent'].map((h) => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wider whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-50">
              {alertsLoading ? (
                <LoadingRow />
              ) : !alerts || alerts.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center">
                    <div className="flex flex-col items-center gap-2 text-neutral-400">
                      <Bell size={28} />
                      <p className="text-sm">{t('dashboard.noAlerts')}</p>
                    </div>
                  </td>
                </tr>
              ) : (
                alerts.slice(0, 8).map((alert) => (
                  <tr key={alert.id} className="hover:bg-neutral-50 transition-colors">
                    <td className="px-4 py-3 text-neutral-800 font-medium whitespace-nowrap">
                      <Link to={`/farms/${alert.farm_id}`} className="hover:text-primary-600 hover:underline">{alert.farm_name}</Link>
                    </td>
                    <td className="px-4 py-3 text-neutral-600 whitespace-nowrap">{alert.alert_type}</td>
                    <td className="px-4 py-3"><AlertBadge severity={alert.severity} /></td>
                    <td className="px-4 py-3 text-neutral-400 text-xs whitespace-nowrap">
                      {new Date(alert.timestamp).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                    </td>
                    <td className="px-4 py-3">
                      <span className={alert.sms_sent ? 'badge-success' : 'text-xs text-neutral-300'}>{alert.sms_sent ? 'Yes' : 'No'}</span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
