import { useState } from 'react';
import PropTypes from 'prop-types';
import {
  ChevronDown,
  ChevronUp,
  MessageSquare,
  Eye,
  TrendingUp,
  Droplets,
  Bug,
  Thermometer,
  Cpu,
  Zap,
} from 'lucide-react';
import ConfidenceTimeline from './ConfidenceTimeline';

const MODULE_CONFIG = {
  Vision: { label: 'Vision AI', color: 'bg-purple-100 text-purple-700', icon: Eye },
  Forecaster: { label: 'Forecaster', color: 'bg-blue-100 text-blue-700', icon: TrendingUp },
  LLM: { label: 'LLM', color: 'bg-teal-50 text-teal-700', icon: Cpu },
};

const PRIORITY_CONFIG = {
  critical: 'badge-critical animate-pulse-ring',
  high: 'bg-orange-100 text-orange-700 text-xs font-medium px-2 py-0.5 rounded-full',
  medium: 'badge-warning',
  low: 'badge-info',
};

const CATEGORY_ICONS = {
  Irrigation: Droplets,
  Pest: Bug,
  Yield: TrendingUp,
  Weather: Thermometer,
};

/**
 * AI recommendation card with expand/collapse and SMS send.
 */
export default function InsightCard({ insight, onSendSMS }) {
  const [expanded, setExpanded] = useState(false);

  const module = MODULE_CONFIG[insight.module] || MODULE_CONFIG.LLM;
  const ModuleIcon = module.icon;
  const CategoryIcon = CATEGORY_ICONS[insight.category] || Zap;

  return (
    <div className="card border border-neutral-100 hover:border-neutral-200 transition-colors">
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 bg-primary-50 rounded-lg flex items-center justify-center flex-shrink-0">
          <CategoryIcon size={16} className="text-primary-500" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${module.color}`}>
              {module.label}
            </span>
            <span className={PRIORITY_CONFIG[insight.priority] || PRIORITY_CONFIG.medium}>
              {insight.priority.charAt(0).toUpperCase() + insight.priority.slice(1)}
            </span>
            {insight.farm_name && (
              <span className="text-xs text-neutral-400 truncate">{insight.farm_name}</span>
            )}
          </div>
          <h3 className="text-sm font-semibold text-neutral-800 leading-snug">{insight.title}</h3>
        </div>
        <button
          onClick={() => setExpanded((v) => !v)}
          className="text-neutral-400 hover:text-neutral-600 flex-shrink-0 mt-0.5"
          aria-label={expanded ? 'Collapse' : 'Expand'}
          id={`insight-toggle-${insight.id}`}
        >
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>

      {/* Body */}
      {expanded && (
        <div className="mt-3 space-y-3">
          <p className="text-sm text-neutral-600 leading-relaxed">{insight.description}</p>
          <div className="bg-primary-50 border border-primary-100 rounded-lg p-3">
            <p className="text-xs font-semibold text-primary-700 mb-1">Recommended Action</p>
            <p className="text-sm text-primary-800">{insight.recommended_action}</p>
          </div>
          <ConfidenceTimeline confidence={insight.confidence} />
          <div className="flex items-center justify-between pt-1">
            <span className="text-xs text-neutral-400">{new Date(insight.timestamp).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</span>
            {onSendSMS && (
              <button
                id={`send-sms-${insight.id}`}
                onClick={() => onSendSMS(insight)}
                className="btn-teal flex items-center gap-1.5 text-xs py-1.5"
              >
                <MessageSquare size={13} />
                Send SMS
              </button>
            )}
          </div>
        </div>
      )}

      {/* Collapsed summary */}
      {!expanded && (
        <p className="text-xs text-neutral-400 mt-2 line-clamp-1">{insight.description}</p>
      )}
    </div>
  );
}

InsightCard.propTypes = {
  insight: PropTypes.shape({
    id: PropTypes.string.isRequired,
    farm_name: PropTypes.string,
    module: PropTypes.string.isRequired,
    category: PropTypes.string.isRequired,
    priority: PropTypes.string.isRequired,
    title: PropTypes.string.isRequired,
    description: PropTypes.string.isRequired,
    recommended_action: PropTypes.string.isRequired,
    confidence: PropTypes.number.isRequired,
    timestamp: PropTypes.string.isRequired,
  }).isRequired,
  onSendSMS: PropTypes.func,
};
