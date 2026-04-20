import { useState, useRef, useEffect } from 'react';
import { NavLink, useLocation, Outlet } from 'react-router-dom';
import {
  LayoutDashboard, Tractor, CloudSun, Lightbulb, Bell,
  Menu, X, Leaf, Globe, LogOut, Check, Bug, Activity
} from 'lucide-react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import i18n from '../i18n/index';
import { useAuth } from '../context/AuthContext';
import NotificationCenter from './NotificationCenter';
import QuickActionFAB from './QuickActionFAB';
import TopProgressBar from './TopProgressBar';
import LocationChip from './LocationChip';

const LANGUAGES = [
  { code: 'en', flag: '🇬🇧', label: 'English', state: 'All India' },
  { code: 'hi', flag: '🇮🇳', label: 'हिन्दी', state: 'UP · MP · Bihar' },
  { code: 'mr', flag: '🇮🇳', label: 'मराठी', state: 'Maharashtra' },
  { code: 'pa', flag: '🇮🇳', label: 'ਪੰਜਾਬੀ', state: 'Punjab · Haryana' },
  { code: 'gu', flag: '🇮🇳', label: 'ગુજરાતી', state: 'Gujarat' },
  { code: 'kn', flag: '🇮🇳', label: 'ಕನ್ನಡ', state: 'Karnataka' },
  { code: 'te', flag: '🇮🇳', label: 'తెలుగు', state: 'Andhra · Telangana' },
  { code: 'ta', flag: '🇮🇳', label: 'தமிழ்', state: 'Tamil Nadu' },
  { code: 'bn', flag: '🇮🇳', label: 'বাংলা', state: 'West Bengal' },
  { code: 'en', flag: '🇬🇧', label: 'English', state: 'Global' },
];

function LanguageSwitcher() {
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState(localStorage.getItem('krishi_lang') || 'hi');
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const changeLanguage = (code) => {
    i18n.changeLanguage(code);
    localStorage.setItem('krishi_lang', code);
    setCurrent(code);
    setOpen(false);
  };

  const currentLang = LANGUAGES.find((l) => l.code === current) || LANGUAGES[0];

  return (
    <div className="relative" ref={ref}>
      <button
        id="lang-switcher-btn"
        onClick={() => setOpen((v) => !v)}
        className="w-8 h-8 flex items-center justify-center rounded-lg text-neutral-500 hover:text-neutral-700 hover:bg-neutral-100 transition-colors"
        aria-label="Change language"
        title={`Language: ${currentLang.label}`}
      >
        <Globe size={16} />
      </button>
      {open && (
        <div
          className="absolute right-0 top-10 w-44 bg-white border border-neutral-200 rounded-xl shadow-xl z-50 overflow-hidden"
          style={{ animation: 'slideInUp 200ms ease-out both' }}
        >
          {LANGUAGES.map((lang) => (
            <button
              key={lang.code}
              onClick={() => changeLanguage(lang.code)}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                current === lang.code ? 'bg-primary-50 text-primary-700 font-medium' : 'text-neutral-700 hover:bg-neutral-50'
              }`}
            >
              <div className="w-8 h-8 rounded-full bg-[#1a2e1a] flex items-center justify-center text-xs font-bold text-white flex-shrink-0">
                {lang.code === 'en' ? 'En' : lang.label.charAt(0)}
              </div>
              <div className="text-left">
                 <p className="leading-tight">{lang.code === 'en' ? 'English' : `${lang.label} · ${lang.code.toUpperCase()}`}</p>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function SidebarContent({ onClose }) {
  const location = useLocation();
  const { t } = useTranslation();
  const { user, logout } = useAuth();

  const NAV_ITEMS = [
    { to: '/', icon: LayoutDashboard, label: t('nav.dashboard') },
    { to: '/farms', icon: Tractor, label: t('nav.farms') },
    { to: '/weather', icon: CloudSun, label: t('nav.weather') },
    { to: '/insights', icon: Lightbulb, label: t('nav.insights') },
    { to: '/alerts', icon: Bell, label: t('nav.alerts') },
    { to: '/yield', icon: Leaf, label: t('page.yield.title') || 'Yield History' },
    { to: '/soil', icon: Activity, label: t('page.soil.title') || 'Soil Health' },
    { to: '/pest-detect', icon: Bug, label: t('page.pest_detect.title') || 'Pest Detection' },
    { to: '/health', icon: Check, label: t('page.system_health.title') || 'System Health' },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 py-5 border-b border-neutral-800">
        <div className="w-8 h-8 bg-primary-500 rounded-lg flex items-center justify-center flex-shrink-0">
          <Leaf size={16} className="text-white" />
        </div>
        <div className="min-w-0">
          <p className="text-white font-semibold text-sm leading-tight">KrishiAI</p>
          <p className="text-neutral-400 text-xs">v2.0 (India)</p>
        </div>
        {onClose && (
          <button onClick={onClose} className="ml-auto text-neutral-400 hover:text-white md:hidden" aria-label="Close sidebar">
            <X size={18} />
          </button>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto scrollbar-thin">
        <p className="text-neutral-500 text-xs font-medium uppercase tracking-wider px-2 mb-2">Navigation</p>
        {NAV_ITEMS.map(({ to, icon: Icon, label }, idx) => {
          const isActive = to === '/' ? location.pathname === '/' : location.pathname.startsWith(to);
          return (
            <NavLink
              key={to}
              to={to}
              onClick={onClose}
              style={{ animation: 'slideInLeft 300ms ease-out both', animationDelay: `${idx * 60}ms` }}
              className={isActive ? 'sidebar-link-active' : 'sidebar-link'}
            >
              <Icon size={17} />
              <span>{label}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-4 border-t border-neutral-800 space-y-3">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 bg-teal-500 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
            {user?.name?.[0]?.toUpperCase() || 'A'}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-white text-xs font-medium truncate">{user?.name || 'Arjun Wali'}</p>
            <p className="text-neutral-400 text-xs truncate">{user?.role || 'Extension Worker'}</p>
          </div>
        </div>
        <button
          onClick={logout}
          className="flex items-center gap-2 text-neutral-400 hover:text-white text-xs w-full px-1 transition-colors"
          id="logout-btn"
        >
          <LogOut size={13} />
          <span>{t('common.logout')}</span>
        </button>
      </div>
    </div>
  );
}

SidebarContent.propTypes = { onClose: PropTypes.func };

export default function Layout({ children }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { t } = useTranslation();
  const { user } = useAuth();

  const NAV_ITEMS_MOBILE = [
    { to: '/', icon: LayoutDashboard, label: t('nav.dashboard') },
    { to: '/farms', icon: Tractor, label: t('nav.farms') },
    { to: '/soil', icon: Activity, label: t('page.soil') || 'Soil' },
    { to: '/pest-detect', icon: Bug, label: t('page.pest_detection') || 'Pest' },
    { to: '/alerts', icon: Bell, label: t('nav.alerts') },
  ];

  return (
    <div className="flex h-screen bg-neutral-50 overflow-hidden">
      {/* Global top progress bar */}
      <TopProgressBar />

      {/* Desktop Sidebar */}
      <aside className="hidden md:flex flex-col w-60 bg-neutral-950 flex-shrink-0">
        <SidebarContent />
      </aside>

      {/* Mobile Overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-40 md:hidden" onClick={() => setMobileOpen(false)} />
      )}

      {/* Mobile Drawer */}
      <aside className={`fixed top-0 left-0 h-full w-60 bg-neutral-950 z-50 transform transition-transform duration-200 md:hidden ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <SidebarContent onClose={() => setMobileOpen(false)} />
      </aside>

      {/* Main Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Topbar */}
        <header className="h-14 bg-white border-b border-neutral-100 flex items-center px-4 gap-3 flex-shrink-0">
          <button className="md:hidden text-neutral-500 hover:text-neutral-800" onClick={() => setMobileOpen(true)} aria-label="Open menu" id="mobile-menu-btn">
            <Menu size={20} />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-teal-400 rounded-full animate-pulse" />
            <span className="text-xs text-neutral-500 font-medium">
              Live · {new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
            </span>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <span className="hidden sm:block text-xs text-neutral-400 font-medium">
              Agricultural Intelligence Platform
            </span>
            {/* Language switcher */}
            <LanguageSwitcher />
            <LocationChip />
            {/* Notifications */}
            <NotificationCenter />
            {/* User avatar */}
            <div className="w-7 h-7 bg-primary-500 rounded-full flex items-center justify-center text-white text-xs font-bold">
              {user?.name?.[0]?.toUpperCase() || 'A'}
            </div>
          </div>
        </header>

        {/* Scrollable Content */}
        <main className="flex-1 overflow-y-auto scrollbar-thin p-4 md:p-6 pb-24 md:pb-6">
          {children || <Outlet />}
        </main>
      </div>

      {/* Mobile Bottom Tab Bar */}
      <nav className="fixed bottom-0 left-0 right-0 bg-white border-t border-neutral-100 flex md:hidden z-30">
        {NAV_ITEMS_MOBILE.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex-1 flex flex-col items-center py-2 text-xs gap-0.5 ${isActive ? 'text-primary-600 font-medium' : 'text-neutral-400'}`
            }
          >
            <Icon size={18} />
            <span className="text-xs">{label.split(' ')[0]}</span>
          </NavLink>
        ))}
      </nav>

      {/* Global Floating Action Button */}
      <QuickActionFAB />
    </div>
  );
}

Layout.propTypes = { children: PropTypes.node.isRequired };
