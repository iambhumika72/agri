import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Bell, RefreshCw, Send, Users, CheckCircle, AlertTriangle, Search, CloudRain, ThermometerSun, Leaf } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import { useAlerts, useSMSStats } from '../hooks/useAlerts';
import { useFarms } from '../hooks/useFarms';
import AlertBadge from '../components/AlertBadge';
import SMSPreview from '../components/SMSPreview';
import StatCard from '../components/StatCard';
import { sendSMSAlert, sendBulkSMSAlert } from '../api/alerts';
import { useQueryClient } from '@tanstack/react-query';

const ALERT_TYPES = ['Drought', 'Irrigation', 'Pest', 'Disease', 'Weather', 'Heat Stress', 'Nutrient', 'Harvest'];

export default function AlertsPage() {
  const queryClient = useQueryClient();
  const [severityFilter, setSeverityFilter] = useState('all');
  const [composerFarmId, setComposerFarmId] = useState('farm-001');
  const [composerAlertType, setComposerAlertType] = useState('Irrigation');
  const [composerMessage, setComposerMessage] = useState('');
  const [showSMSPreview, setShowSMSPreview] = useState(false);
  const [bulkMode, setBulkMode] = useState(false);
  const [sendSuccess, setSendSuccess] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const filters = severityFilter !== 'all' ? { severity: severityFilter } : {};
  const { data: alerts, isLoading } = useAlerts(filters);
  const { data: stats } = useSMSStats();
  const { data: farms } = useFarms();

  const selectedFarm = farms?.find((f) => f.id === composerFarmId);
  const charCount = composerMessage.length;

  const handleRefresh = async () => {
    setRefreshing(true);
    await queryClient.invalidateQueries({ queryKey: ['alerts'] });
    setTimeout(() => setRefreshing(false), 600);
  };

  const handleSend = async (msg) => {
    if (bulkMode) {
      await sendBulkSMSAlert({ alert_type: composerAlertType, message: msg });
    } else {
      await sendSMSAlert({ farm_id: composerFarmId, alert_type: composerAlertType, message: msg });
    }
    setSendSuccess(true);
    setShowSMSPreview(false);
    setComposerMessage('');
    setTimeout(() => setSendSuccess(false), 3000);
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-24 md:pb-8">
      <PageHeader 
        titleKey="page.alerts.title" 
        descKey="page.alerts.desc" 
        icon={Bell} 
      />

      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between px-6 md:px-0" style={{ animation: 'fadeIn 300ms ease-out both' }}>
        <p className="text-sm text-neutral-400 mt-0.5">Monitor alerts and send SMS notifications to farmers</p>
      </div>

      {/* SMS Delivery Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="Sent Today" value={stats?.sent || 0} icon={Send} colorClass="bg-primary-50" />
        <StatCard title="Delivered" value={stats?.delivered || 0} icon={CheckCircle} colorClass="bg-teal-50" />
        <StatCard title="Failed" value={stats?.failed || 0} icon={AlertTriangle} colorClass="bg-danger-50" danger={(stats?.failed || 0) > 0} />
        <StatCard title="Pending" value={stats?.pending || 0} icon={Bell} colorClass="bg-amber-50" />
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
        {/* Alert Feed */}
        <div className="lg:col-span-3 card overflow-hidden p-0">
          <div className="px-5 py-4 border-b border-neutral-100 flex items-center gap-3 flex-wrap">
            <h2 className="text-sm font-semibold text-neutral-700 flex items-center gap-2">
              <div className="w-2 h-2 bg-teal-400 rounded-full animate-pulse" />
              Live Alert Feed
            </h2>
            <button
              id="refresh-alerts-btn"
              onClick={handleRefresh}
              className="btn-secondary flex items-center gap-1.5 py-1.5 text-xs"
            >
              <RefreshCw size={12} className={refreshing ? 'animate-spin' : ''} />
              Refresh
            </button>
            <div className="ml-auto flex gap-1.5 flex-wrap">
              {['all', 'critical', 'warning', 'info'].map((s) => (
                <button
                  key={s}
                  id={`alert-filter-${s}`}
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
            {isLoading ? (
              <div className="flex items-center justify-center h-32 text-neutral-400 text-sm gap-2">
                <div className="w-4 h-4 border-2 border-primary-300 border-t-primary-500 rounded-full animate-spin" />
                Loading alerts…
              </div>
            ) : !alerts || alerts.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-neutral-400 gap-3">
                <Bell size={32} />
                <p className="text-sm">No {severityFilter !== 'all' ? severityFilter : ''} alerts found.</p>
              </div>
            ) : (
              alerts.map((alert) => (
                <div key={alert.id} className="px-5 py-3.5 hover:bg-neutral-50 transition-colors">
                  <div className="flex items-start gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <AlertBadge severity={alert.severity} />
                        <span className="text-xs font-medium text-neutral-600">{alert.alert_type}</span>
                        <span className="text-xs text-neutral-300">·</span>
                        <span className="text-xs text-neutral-400 truncate">{alert.farm_name}</span>
                      </div>
                      <p className="text-sm text-neutral-700 leading-snug">{alert.message}</p>
                      <div className="flex items-center gap-3 mt-1.5">
                        <span className="text-xs text-neutral-400">
                          {new Date(alert.timestamp).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                        </span>
                        <span className={`text-xs ${
                          alert.delivery_status === 'delivered' ? 'text-teal-600' :
                          alert.delivery_status === 'failed' ? 'text-danger-500' :
                          'text-amber-500'
                        }`}>
                          SMS: {alert.delivery_status}
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
              {/* Farm selector */}
              <div>
                <label className="text-xs font-medium text-neutral-500 mb-1 block" htmlFor="composer-farm">
                  Farm
                </label>
                <select
                  id="composer-farm"
                  className="select w-full"
                  value={composerFarmId}
                  onChange={(e) => setComposerFarmId(e.target.value)}
                >
                  {(farms || []).map((f) => (
                    <option key={f.id} value={f.id}>{f.name}</option>
                  ))}
                </select>
                {selectedFarm && (
                  <p className="text-xs text-neutral-400 mt-1">{selectedFarm.farmer_name} · {selectedFarm.farmer_phone}</p>
                )}
              </div>

              {/* Alert type */}
              <div>
                <label className="text-xs font-medium text-neutral-500 mb-1 block" htmlFor="composer-type">
                  Alert Type
                </label>
                <select
                  id="composer-type"
                  className="select w-full"
                  value={composerAlertType}
                  onChange={(e) => setComposerAlertType(e.target.value)}
                >
                  {ALERT_TYPES.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>

              {/* Message */}
              <div>
                <div className="flex justify-between mb-1">
                  <label className="text-xs font-medium text-neutral-500" htmlFor="composer-message">
                    Message
                  </label>
                  <span className={`text-xs font-semibold tabular-nums ${charCount > 140 ? 'text-danger-500' : charCount > 120 ? 'text-amber-500' : 'text-neutral-400'}`}>
                    {charCount}/160
                  </span>
                </div>
                <textarea
                  id="composer-message"
                  className="input resize-none h-24 font-mono text-xs"
                  placeholder={`Type SMS alert for ${selectedFarm?.farmer_name || 'farmer'}…`}
                  value={composerMessage}
                  onChange={(e) => setComposerMessage(e.target.value.slice(0, 160))}
                />
              </div>
            </div>

            {/* Buttons */}
            <div className="flex gap-2 mt-4">
              <button
                id="send-to-farmer-btn"
                onClick={() => { setBulkMode(false); setShowSMSPreview(true); }}
                disabled={!composerMessage.trim()}
                className="btn-primary flex items-center gap-1.5 flex-1 justify-center disabled:opacity-40"
              >
                <Send size={13} />
                Send to Farmer
              </button>
              <button
                id="send-to-all-btn"
                onClick={() => { setBulkMode(true); setShowSMSPreview(true); }}
                disabled={!composerMessage.trim()}
                className="btn-secondary flex items-center gap-1.5 flex-1 justify-center disabled:opacity-40"
              >
                <Users size={13} />
                All Farms
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* SMS Preview Modal */}
      {showSMSPreview && (
        <SMSPreview
          message={composerMessage}
          farmName={bulkMode ? 'All Farms' : selectedFarm?.name}
          onConfirm={handleSend}
          onClose={() => setShowSMSPreview(false)}
        />
      )}
    </div>
  );
}
