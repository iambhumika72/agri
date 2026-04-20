import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Check } from 'lucide-react';
import i18n from '../i18n/index';

const LANGUAGES = [
  { code: 'en', flag: '🇬🇧', native: 'English', english: 'English' },
  { code: 'hi', flag: '🇮🇳', native: 'हिन्दी', english: 'Hindi' },
  { code: 'mr', flag: '🇮🇳', native: 'मराठी', english: 'Marathi' },
  { code: 'ta', flag: '🇮🇳', native: 'தமிழ்', english: 'Tamil' },
  { code: 'sw', flag: '🇰🇪', native: 'Kiswahili', english: 'Swahili' },
  { code: 'fr', flag: '🇫🇷', native: 'Français', english: 'French' },
];

import { useLocation_ } from '../context/LocationContext';

const PREFS_KEY = 'agri_prefs';

export default function OnboardingPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { requestLocation } = useLocation_();
  const [step, setStep] = useState(0);
  const [selectedLang, setSelectedLang] = useState(localStorage.getItem('agri_lang') || 'en');
  const [prefs, setPrefs] = useState({
    temperature: 'Celsius',
    area: 'Hectares',
    rainfall: 'mm',
    sms: true,
    email: true,
    push: false,
    smsFrequency: 'daily',
  });

  const selectLanguage = (code) => {
    setSelectedLang(code);
    i18n.changeLanguage(code);
    localStorage.setItem('agri_lang', code);
  };

  const togglePref = (key) => setPrefs((p) => ({ ...p, [key]: !p[key] }));
  const setPref = (key, val) => setPrefs((p) => ({ ...p, [key]: val }));

  const finish = () => {
    localStorage.setItem(PREFS_KEY, JSON.stringify({ ...prefs, language: selectedLang }));
    requestLocation(); // silently request in background
    navigate('/');
  };

  const stepStyle = { animation: 'slideInRight 300ms ease-out both' };

  return (
    <div className="min-h-screen bg-neutral-50 flex items-center justify-center p-4">
      <div className="w-full max-w-[560px] bg-white rounded-2xl border border-neutral-100 overflow-hidden">
        {/* Progress dots */}
        <div className="flex gap-2 p-5 border-b border-neutral-100">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className={`h-1.5 rounded-full transition-all duration-500 ${
                i === step ? 'w-12 bg-primary-500' : i < step ? 'w-6 bg-primary-300' : 'w-6 bg-neutral-200'
              }`}
            />
          ))}
          <button
            onClick={() => navigate('/')}
            className="ml-auto text-xs text-neutral-400 hover:text-neutral-600"
          >
            {t('common.cancel')}
          </button>
        </div>

        {/* Step 0: Language */}
        {step === 0 && (
          <div className="p-6" style={stepStyle}>
            <h1 className="text-xl font-bold text-neutral-800 mb-1">
              {t('onboarding.chooseLanguage')}
            </h1>
            <p className="text-sm text-neutral-400 mb-5">अपनी भाषा चुनें · Choose your language</p>
            <div className="grid grid-cols-2 gap-3 mb-6">
              {LANGUAGES.map((lang, idx) => (
                <button
                  key={lang.code}
                  id={`lang-${lang.code}`}
                  onClick={() => selectLanguage(lang.code)}
                  style={{ animation: 'slideInUp 300ms ease-out both', animationDelay: `${idx * 60}ms` }}
                  className={`relative flex items-center gap-3 p-3.5 rounded-xl border-2 text-left transition-colors ${
                    selectedLang === lang.code
                      ? 'border-primary-500 bg-primary-50'
                      : 'border-neutral-200 hover:border-neutral-300'
                  }`}
                >
                  <span className="text-2xl">{lang.flag}</span>
                  <div>
                    <p className="font-semibold text-sm text-neutral-800">{lang.native}</p>
                    <p className="text-xs text-neutral-400">{lang.english}</p>
                  </div>
                  {selectedLang === lang.code && (
                    <div className="absolute top-2 right-2 w-5 h-5 bg-primary-500 rounded-full flex items-center justify-center">
                      <Check size={11} className="text-white" />
                    </div>
                  )}
                </button>
              ))}
            </div>
            <button onClick={() => setStep(1)} className="btn-primary w-full py-2.5">
              {t('common.next')}
            </button>
          </div>
        )}

        {/* Step 1: Unit preferences */}
        {step === 1 && (
          <div className="p-6" style={stepStyle}>
            <h1 className="text-xl font-bold text-neutral-800 mb-1">{t('onboarding.unitPreferences')}</h1>
            <p className="text-sm text-neutral-400 mb-6">Configure units for your region</p>
            <div className="space-y-5">
              {[
                { key: 'temperature', label: t('onboarding.temperature'), options: ['Celsius', 'Fahrenheit'] },
                { key: 'area', label: t('onboarding.area'), options: ['Hectares', 'Acres'] },
                { key: 'rainfall', label: t('onboarding.rainfall'), options: ['mm', 'inches'] },
              ].map(({ key, label, options }) => (
                <div key={key}>
                  <p className="text-xs font-medium text-neutral-500 mb-2 uppercase tracking-wider">{label}</p>
                  <div className="flex gap-2">
                    {options.map((opt) => (
                      <button
                        key={opt}
                        onClick={() => setPref(key, opt)}
                        className={`flex-1 py-2 rounded-lg border text-sm font-medium transition-colors ${
                          prefs[key] === opt
                            ? 'bg-primary-500 text-white border-primary-500'
                            : 'bg-white text-neutral-600 border-neutral-200 hover:border-neutral-300'
                        }`}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <div className="flex gap-3 mt-8">
              <button onClick={() => setStep(0)} className="btn-secondary flex-1 py-2.5">{t('common.back')}</button>
              <button onClick={() => setStep(2)} className="btn-primary flex-1 py-2.5">{t('onboarding.saveAndContinue')}</button>
            </div>
          </div>
        )}

        {/* Step 2: Notifications */}
        {step === 2 && (
          <div className="p-6" style={stepStyle}>
            <h1 className="text-xl font-bold text-neutral-800 mb-1">{t('onboarding.notifications')}</h1>
            <p className="text-sm text-neutral-400 mb-6">Choose how you want to receive updates</p>
            <div className="space-y-4">
              {[
                { key: 'sms', label: t('onboarding.smsAlerts') },
                { key: 'email', label: t('onboarding.emailDigest') },
                { key: 'push', label: t('onboarding.pushNotifications') },
              ].map(({ key, label }) => (
                <div key={key} className="flex items-center justify-between py-2">
                  <span className="text-sm font-medium text-neutral-700">{label}</span>
                  <button
                    onClick={() => togglePref(key)}
                    className={`w-11 h-6 rounded-full transition-colors relative ${prefs[key] ? 'bg-primary-500' : 'bg-neutral-200'}`}
                  >
                    <div className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${prefs[key] ? 'translate-x-5' : 'translate-x-0.5'}`} />
                  </button>
                </div>
              ))}
              <div className="border-t border-neutral-100 pt-4">
                <p className="text-xs font-medium text-neutral-500 mb-3 uppercase tracking-wider">{t('onboarding.smsFrequency')}</p>
                <div className="flex gap-2">
                  {['daily', 'alert'].map((freq) => (
                    <button
                      key={freq}
                      onClick={() => setPref('smsFrequency', freq)}
                      className={`flex-1 py-2 rounded-lg border text-sm font-medium transition-colors ${
                        prefs.smsFrequency === freq
                          ? 'bg-primary-500 text-white border-primary-500'
                          : 'bg-white text-neutral-600 border-neutral-200 hover:border-neutral-300'
                      }`}
                    >
                      {freq === 'daily' ? t('onboarding.daily') : t('onboarding.onAlertOnly')}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div className="flex gap-3 mt-8">
              <button onClick={() => setStep(1)} className="btn-secondary flex-1 py-2.5">{t('common.back')}</button>
              <button onClick={finish} className="btn-primary flex-1 py-2.5">{t('onboarding.enterDashboard')}</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
