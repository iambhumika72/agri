import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Bell, RefreshCw, Send, Users, CheckCircle, AlertTriangle, Search, CloudRain, ThermometerSun, Leaf } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import FarmSelector from '../components/FarmSelector';
import AlertBadge from '../components/AlertBadge';
import SMSPreview from '../components/SMSPreview';
import StatCard from '../components/StatCard';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorBanner from '../components/ErrorBanner';
import EmptyState from '../components/EmptyState';
import { alertsAPI } from '../api/client';

const ALERT_TYPES = ['Drought', 'Irrigation', 'Pest', 'Disease', 'Weather', 'Heat Stress', 'Nutrient', 'Harvest'];

export default function AlertsPage() {
  const { t } = useTranslation();
  const [farmId, setFarmId] = useState('');
  
  const [severityFilter, setSeverityFilter] = useState('all');
  const [composerAlertType, setComposerAlertType] = useState('Irrigation');
  const [composerMessage, setComposerMessage] = useState('');
  const [showSMSPreview, setShowSMSPreview] = useState(false);
  const [sendSuccess, setSendSuccess] = useState(false);
  
  const [alertSummary, setAlertSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchAlerts = async (isRefresh = false) => {
    if (!farmId) return;
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const data = await alertsAPI.getAlerts(farmId);
      setAlertSummary(data);
    } catch (err) {
      setError(err.message);
    } finally {
      if (isRefresh) setRefreshing(false);
      else setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, [farmId]);

  const handleSend = async (msg) => {
    try {
      await alertsAPI.triggerAlert({ farm_id: farmId, alert_type: composerAlertType, severity: 'warning', message: msg, trigger_sms: true });
      setSendSuccess(true);
      setShowSMSPreview(false);
      setComposerMessage('');
      setTimeout(() => setSendSuccess(false), 3000);
      fetchAlerts(true);
    } catch (err) {
      alert(`Failed to send SMS: ${err.message}`);
    }
  };

  const charCount = composerMessage.length;
  
  let alerts = alertSummary?.recent_alerts || [];
  if (severityFilter !== 'all') {
    alerts = alerts.filter(a => a.severity === severityFilter);
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-24 md:pb-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <PageHeader 
          titleKey="page.alerts.title" 
          descKey="page.alerts.desc" 
          icon={Bell} 
        />
        <FarmSelector value={farmId} onChange={setFarmId} />
      </div>

      {!farmId && (
        <EmptyState message="Please select a Farm ID to view and manage alerts." />
      )}

      {farmId && error && <ErrorBanner message={error} onRetry={() => fetchAlerts()} />}
      {farmId && loading && !alertSummary && <LoadingSpinner message="Loading alerts..." />}

      {farmId && !loading && alertSummary && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard title="Active Critical" value={alertSummary.critical_count || 0} icon={AlertTriangle} colorClass="bg-danger-50" danger={(alertSummary.critical_count || 0) > 0} />
            <StatCard title="Total Alerts" value={alertSummary.total_alerts || 0} icon={Bell} colorClass="bg-primary-50" />
            <StatCard title="Recent Count" value={alerts.length} icon={RefreshCw} colorClass="bg-teal-50" />
            <StatCard title="Farm ID" value={farmId.split('-')[0]} icon={Users} colorClass="bg-amber-50" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
            <div className="lg:col-span-3 card overflow-hidden p-0">
              <div className="px-5 py-4 border-b border-neutral-100 flex items-center gap-3 flex-wrap">
                <h2 className="text-sm font-semibold text-neutral-700 flex items-center gap-2">
                  <div className="w-2 h-2 bg-teal-400 rounded-full animate-pulse" />
                  Live Alert Feed
                </h2>
                <button
                  onClick={() => fetchAlerts(true)}
                  className="btn-secondary flex items-center gap-1.5 py-1.5 text-xs"
                >
                  <RefreshCw size={12} className={refreshing ? 'animate-spin' : ''} />
                  Refresh
                </button>
                <div className="ml-auto flex gap-1.5 flex-wrap">
                  {['all', 'critical', 'warning', 'info'].map((s) => (
                    <button
                      key={s}
                      onClick={() => setSeverityFilter(s)}
                      className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
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
              <div className="overflow-y-auto max-h-[520px] scrollbar-thin divide-y divide-neutral-50">
                {alerts.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-16 text-neutral-400 gap-3">
                    <Bell size={32} />
                    <p className="text-sm">No {severityFilter !== 'all' ? severityFilter : ''} alerts found.</p>
                  </div>
                ) : (
                  alerts.map((alert) => (
                    <div key={alert.alert_id} className="px-5 py-3.5 hover:bg-neutral-50 transition-colors">
                      <div className="flex items-start gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <AlertBadge severity={alert.severity} />
                            <span className="text-xs font-medium text-neutral-600">{alert.alert_type}</span>
                          </div>
                          <p className="text-sm text-neutral-700 leading-snug">{alert.message}</p>
                          <div className="flex items-center gap-3 mt-1.5">
                            <span className="text-xs text-neutral-400">
                              {new Date(alert.triggered_at || new Date()).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* SMS Composer */}
            <div className="lg:col-span-2 space-y-4">
              <div className="card">
                <h2 className="text-sm font-semibold text-neutral-700 flex items-center gap-2 mb-4">
                  <Bell size={15} className="text-teal-400" />
                  Compose SMS Alert
                </h2>

                {sendSuccess && (
                  <div className="bg-teal-50 border border-teal-200 rounded-lg px-3 py-2.5 flex items-center gap-2 mb-4 text-teal-700 text-sm">
                    <CheckCircle size={15} />
                    SMS sent successfully!
                  </div>
                )}

                <div className="space-y-3">
                  <div>
                    <label className="text-xs font-medium text-neutral-500 mb-1 block">Alert Type</label>
                    <select
                      className="select w-full"
                      value={composerAlertType}
                      onChange={(e) => setComposerAlertType(e.target.value)}
                    >
                      {ALERT_TYPES.map((t) => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <div className="flex justify-between mb-1">
                      <label className="text-xs font-medium text-neutral-500">Message</label>
                      <span className={`text-xs font-semibold tabular-nums ${charCount > 140 ? 'text-danger-500' : charCount > 120 ? 'text-amber-500' : 'text-neutral-400'}`}>
                        {charCount}/160
                      </span>
                    </div>
                    <textarea
                      className="input resize-none h-24 font-mono text-xs"
                      placeholder={`Type SMS alert for farm...`}
                      value={composerMessage}
                      onChange={(e) => setComposerMessage(e.target.value.slice(0, 160))}
                    />
                  </div>
                </div>

                <div className="mt-4">
                  <button
                    onClick={() => setShowSMSPreview(true)}
                    disabled={!composerMessage.trim()}
                    className="btn-primary flex items-center gap-1.5 w-full justify-center disabled:opacity-40"
                  >
                    <Send size={13} />
                    Send Alert to {farmId}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* SMS Preview Modal */}
          {showSMSPreview && (
            <SMSPreview
              message={composerMessage}
              farmName={farmId}
              onConfirm={handleSend}
              onClose={() => setShowSMSPreview(false)}
            />
          )}
        </>
      )}
    </div>
  );
}
