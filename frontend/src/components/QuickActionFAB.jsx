import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, X, Eye, MessageSquare, Lightbulb, Droplets } from 'lucide-react';

const ACTIONS = [
  { id: 'log', icon: Eye, label: 'Log observation', color: 'bg-teal-500', path: null },
  { id: 'sms', icon: MessageSquare, label: 'Send SMS', color: 'bg-primary-500', path: '/alerts' },
  { id: 'insight', icon: Lightbulb, label: 'AI Insight', color: 'bg-amber-500', path: '/insights' },
  { id: 'irrigate', icon: Droplets, label: 'Irrigate', color: 'bg-blue-500', path: '/farms' },
];

/**
 * Floating action button — expands into 4 action bubbles.
 * Collapses on outside click or Escape.
 */
export default function QuickActionFAB() {
  const [open, setOpen] = useState(false);
  const fabRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    const handleKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    const handleClick = (e) => { if (fabRef.current && !fabRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener('keydown', handleKey);
    document.addEventListener('mousedown', handleClick);
    return () => { document.removeEventListener('keydown', handleKey); document.removeEventListener('mousedown', handleClick); };
  }, []);

  const handleAction = (action) => {
    setOpen(false);
    if (action.path) navigate(action.path);
  };

  return (
    <div
      ref={fabRef}
      className="fixed bottom-20 right-5 md:bottom-6 md:right-6 z-40 flex flex-col items-end gap-3"
    >
      {/* Action bubbles */}
      {open && ACTIONS.map((action, idx) => (
        <div
          key={action.id}
          className="flex items-center gap-2.5"
          style={{
            animation: 'slideInRight 200ms ease-out both',
            animationDelay: `${idx * 50}ms`,
          }}
        >
          <span className="text-xs font-medium text-neutral-700 bg-white px-2.5 py-1 rounded-full shadow-sm border border-neutral-100 whitespace-nowrap">
            {action.label}
          </span>
          <button
            id={`fab-${action.id}`}
            onClick={() => handleAction(action)}
            className={`w-10 h-10 rounded-full ${action.color} text-white flex items-center justify-center shadow-md hover:scale-105 transition-transform`}
          >
            <action.icon size={17} />
          </button>
        </div>
      ))}

      {/* Main FAB */}
      <button
        id="quick-action-fab"
        onClick={() => setOpen((v) => !v)}
        className={`w-12 h-12 rounded-full bg-primary-500 hover:bg-primary-600 text-white flex items-center justify-center shadow-lg transition-all duration-200 ${open ? 'rotate-45' : ''}`}
        aria-label={open ? 'Close quick actions' : 'Quick actions'}
      >
        {open ? <X size={20} /> : <Plus size={22} />}
      </button>
    </div>
  );
}
