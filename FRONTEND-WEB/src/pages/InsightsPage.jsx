import { useState, useEffect } from 'react';
import { Lightbulb, CheckCircle, XCircle, AlertCircle, ChevronLeft, ChevronRight } from 'lucide-react';
import InsightCard from '../components/InsightCard';
import SMSPreview from '../components/SMSPreview';
import PageHeader from '../components/PageHeader';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorBanner from '../components/ErrorBanner';
import { insightsAPI } from '../api/client';

const CATEGORIES = ['All', 'Irrigation', 'Pest', 'Yield', 'Weather'];
const PAGE_SIZE = 10;

function ModelStatusDot({ status }) {
  if (status === 'healthy') return <span className="w-2 h-2 rounded-full bg-teal-400 inline-block animate-pulse" />;
  if (status === 'degraded') return <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />;
  return <span className="w-2 h-2 rounded-full bg-danger-500 inline-block" />;
}

function ModelStatusBar({ modelStatus }) {
  const models = [
    { key: 'vision', label: 'Vision Model', model: modelStatus?.vision },
    { key: 'forecaster', label: 'Time-Series Forecaster', model: modelStatus?.forecaster },
    { key: 'llm', label: 'Generative LLM', model: modelStatus?.llm },
  ];

  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-3">
        <Lightbulb size={15} className="text-teal-400" />
        <h2 className="text-sm font-semibold text-neutral-700">AI Model Status</h2>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {models.map(({ key, label, model }) => (
          <div key={key} className="bg-neutral-50 rounded-lg px-4 py-3 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-neutral-700">{label}</p>
              {model && (
                <p className="text-xs text-neutral-400 mt-0.5">
                  {model.model} · Last run:{' '}
                  {new Date(model.last_run).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                </p>
              )}
            </div>
            {model ? (
              <div className="flex items-center gap-1.5 flex-shrink-0">
                <ModelStatusDot status={model.status} />
                <span className="text-xs font-medium text-teal-600 capitalize">{model.status}</span>
              </div>
            ) : (
              <span className="w-2 h-2 rounded-full bg-neutral-300 inline-block" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function InsightsPage() {
  const [category, setCategory] = useState('All');
  const [page, setPage] = useState(1);
  const [smsFarm, setSMSFarm] = useState(null);

  const [insights, setInsights] = useState([]);
  const [modelStatus, setModelStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchInsights = async () => {
    setLoading(true);
    setError(null);
    try {
      const filters = category !== 'All' ? { category } : {};
      const [insightsData, statusData] = await Promise.all([
        insightsAPI.getInsights(filters),
        insightsAPI.getModelStatus()
      ]);
      setInsights(insightsData || []);
      setModelStatus(statusData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInsights();
  }, [category]);

  const paginated = insights.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const totalPages = Math.max(1, Math.ceil(insights.length / PAGE_SIZE));

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-24 md:pb-8">
      <PageHeader 
        titleKey="page.insights.title" 
        descKey="page.insights.desc" 
        icon={Lightbulb} 
      />

      <ModelStatusBar modelStatus={modelStatus} />

      {/* Filter bar */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs font-medium text-neutral-500 mr-1">Filter:</span>
        {CATEGORIES.map((cat) => (
          <button
            key={cat}
            onClick={() => { setCategory(cat); setPage(1); }}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
              category === cat
                ? 'bg-primary-500 text-white border-primary-500'
                : 'bg-white text-neutral-500 border-neutral-200 hover:border-neutral-300'
            }`}
          >
            {cat}
          </button>
        ))}
        {insights.length > 0 && (
          <span className="ml-auto text-xs text-neutral-400">
            {insights.length} result{insights.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {error && <ErrorBanner message={error} onRetry={fetchInsights} />}

      {loading && <LoadingSpinner message="Loading insights..." />}

      {/* Insights Grid */}
      {!loading && paginated.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {paginated.map((insight) => (
            <InsightCard
              key={insight.id}
              insight={insight}
              onSendSMS={() => setSMSFarm(insight)}
            />
          ))}
        </div>
      )}

      {!loading && !error && paginated.length === 0 && (
        <div className="card flex flex-col items-center justify-center py-16 text-neutral-400 gap-3">
          <Lightbulb size={32} />
          <p className="text-sm">No insights found for the selected filter.</p>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="btn-secondary flex items-center gap-1 py-1.5 disabled:opacity-40"
          >
            <ChevronLeft size={14} /> Previous
          </button>
          <span className="text-sm text-neutral-500">
            Page {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="btn-secondary flex items-center gap-1 py-1.5 disabled:opacity-40"
          >
            Next <ChevronRight size={14} />
          </button>
        </div>
      )}

      {/* SMS Modal */}
      {smsFarm && (
        <SMSPreview
          message={smsFarm.sms_template}
          farmName={smsFarm.farm_name}
          onConfirm={async (msg) => {
            alert('SMS sent (mock)');
            setSMSFarm(null);
          }}
          onClose={() => setSMSFarm(null)}
        />
      )}
    </div>
  );
}
