import { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Bell, X } from 'lucide-react';
import { useAlerts } from '../hooks/useAlerts';
import AlertBadge from './AlertBadge';

function timeAgo(ts) {
  const diff = Math.floor((Date.now() - new Date(ts)) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

/**
 * Bell icon notification centre — slide-down panel with last 10 alerts.
 */
export default function NotificationCenter() {
  const [open, setOpen] = useState(false);
  const [readIds, setReadIds] = useState(() => {
    try { return new Set(JSON.parse(localStorage.getItem('read_notifs') || '[]')); }
    catch { return new Set(); }
  });
  const panelRef = useRef(null);
  const { data: alerts } = useAlerts();

  const recent = (alerts || []).slice(0, 10);
  const unread = recent.filter((a) => !readIds.has(a.id)).length;

  const markAllRead = () => {
    const ids = recent.map((a) => a.id);
    const next = new Set([...readIds, ...ids]);
    setReadIds(next);
    localStorage.setItem('read_notifs', JSON.stringify([...next]));
  };

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const borderColor = { critical: 'border-danger-400', warning: 'border-amber-400', info: 'border-blue-400' };

  return (
    <div className="relative" ref={panelRef}>
      {/* Bell button */}
      <button
        id="notif-bell-btn"
        onClick={() => setOpen((v) => !v)}
        className="relative w-8 h-8 flex items-center justify-center rounded-lg text-neutral-500 hover:text-neutral-700 hover:bg-neutral-100 transition-colors"
        aria-label="Notifications"
      >
        <Bell size={17} />
        {unread > 0 && (
          <span
            className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-danger-500 text-white text-[9px] font-bold rounded-full flex items-center justify-center"
            style={{ animation: 'pulse-ring 2s infinite' }}
          >
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {/* Panel */}
      {open && (
        <div
          className="absolute right-0 top-10 w-80 bg-white border border-neutral-200 rounded-xl shadow-xl z-50 overflow-hidden"
          style={{ animation: 'slideInUp 250ms ease-out both' }}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-100">
            <h3 className="text-sm font-semibold text-neutral-800">Notifications</h3>
            <div className="flex items-center gap-2">
              {unread > 0 && (
                <button onClick={markAllRead} className="text-xs text-teal-600 hover:underline font-medium">
                  Mark all read
                </button>
              )}
              <button onClick={() => setOpen(false)} className="text-neutral-400 hover:text-neutral-600"><X size={14} /></button>
            </div>
          </div>

          {/* List */}
          <div className="max-h-80 overflow-y-auto scrollbar-thin divide-y divide-neutral-50">
            {recent.length === 0 ? (
              <div className="flex flex-col items-center py-10 text-neutral-400 gap-2">
                <Bell size={24} />
                <p className="text-xs">No notifications yet</p>
              </div>
            ) : (
              recent.map((a) => (
                <div
                  key={a.id}
                  className={`flex gap-3 px-4 py-3 border-l-4 ${borderColor[a.severity] || 'border-blue-400'} ${!readIds.has(a.id) ? 'bg-primary-50/30' : ''}`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <AlertBadge severity={a.severity} />
                      <span className="text-xs text-neutral-400 truncate">{a.farm_name}</span>
                    </div>
                    <p className="text-xs text-neutral-700 leading-snug line-clamp-2">{a.message}</p>
                    <p className="text-xs text-neutral-400 mt-1">{timeAgo(a.timestamp)}</p>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Footer */}
          <div className="px-4 py-2.5 border-t border-neutral-100 text-center">
            <Link to="/alerts" onClick={() => setOpen(false)} className="text-xs text-teal-600 font-medium hover:underline">
              View all alerts →
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
