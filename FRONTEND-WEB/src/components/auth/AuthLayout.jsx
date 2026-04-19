import PropTypes from 'prop-types';
import { Leaf } from 'lucide-react';

const FEATURES = [
  { emoji: '🛰️', label: 'Satellite crop monitoring' },
  { emoji: '🌤️', label: '7-day weather forecast' },
  { emoji: '🐛', label: 'AI pest detection' },
];

/**
 * Full-screen split layout for auth pages.
 * Left 40% = dark green branding panel.
 * Right 60% = white form area.
 */
export default function AuthLayout({ children }) {
  return (
    <div className="min-h-screen flex">
      {/* Left branding panel */}
      <div
        className="hidden md:flex flex-col justify-between w-[40%] p-10 flex-shrink-0"
        style={{ background: '#1a2e1a' }}
      >
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-primary-500 rounded-xl flex items-center justify-center">
            <Leaf size={20} className="text-white" />
          </div>
          <div>
            <p className="text-white font-bold text-xl leading-none">AgriAI</p>
            <p className="text-green-400 text-xs font-medium">KrishiAI Platform</p>
          </div>
        </div>

        {/* Hero text */}
        <div className="space-y-6">
          <h2 className="text-white text-3xl font-bold leading-tight">
            Empowering farmers with intelligent insights
          </h2>
          <p className="text-green-300 text-sm leading-relaxed">
            Real-time AI-driven analysis for small-scale farms across India and Africa.
          </p>
          {/* Feature pills with staggered slide-in */}
          <div className="space-y-3">
            {FEATURES.map((f, i) => (
              <div
                key={f.label}
                className="flex items-center gap-3 bg-white bg-opacity-10 rounded-xl px-4 py-3"
                style={{
                  animation: `slideInLeft 400ms ease-out both`,
                  animationDelay: `${i * 200}ms`,
                }}
              >
                <span className="text-xl">{f.emoji}</span>
                <span className="text-white text-sm font-medium">{f.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <p className="text-green-600 text-xs">© 2025 KrishiAI · Sustainable Agriculture Platform</p>
      </div>

      {/* Right form panel */}
      <div className="flex-1 flex items-center justify-center p-6 bg-white overflow-y-auto">
        <div className="w-full max-w-md" style={{ animation: 'fadeIn 300ms ease-out both' }}>
          {/* Mobile logo */}
          <div className="flex items-center gap-2 mb-8 md:hidden">
            <div className="w-8 h-8 bg-primary-500 rounded-lg flex items-center justify-center">
              <Leaf size={15} className="text-white" />
            </div>
            <span className="font-bold text-neutral-800">AgriAI</span>
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}

AuthLayout.propTypes = {
  children: PropTypes.node.isRequired,
};
