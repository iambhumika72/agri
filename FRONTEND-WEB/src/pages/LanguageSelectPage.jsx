import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Leaf, Check, ArrowRight } from 'lucide-react';
import i18n from '../i18n/index';

const LANGUAGES = [
  { code: 'en', native: 'English', english: 'English', state: 'All India' },
  { code: 'hi', native: 'हिन्दी', english: 'Hindi', state: 'UP · MP · Bihar' },
  { code: 'mr', native: 'मराठी', english: 'Marathi', state: 'Maharashtra' },
  { code: 'pa', native: 'ਪੰਜਾਬੀ', english: 'Punjabi', state: 'Punjab · Haryana' },
  { code: 'gu', native: 'ગુજરાતી', english: 'Gujarati', state: 'Gujarat' },
  { code: 'kn', native: 'ಕನ್ನಡ', english: 'Kannada', state: 'Karnataka' },
  { code: 'te', native: 'తెలుగు', english: 'Telugu', state: 'AP · Telangana' },
  { code: 'ta', native: 'தமிழ்', english: 'Tamil', state: 'Tamil Nadu' },
  { code: 'bn', native: 'বাংলা', english: 'Bengali', state: 'West Bengal' },
];

export default function LanguageSelectPage() {
  const navigate = useNavigate();
  const currentLang = localStorage.getItem('krishi_lang') || null;

  const handleSelect = (code) => {
    i18n.changeLanguage(code);
    localStorage.setItem('krishi_lang', code);
    // Force a re-render to reflect new lang key
    navigate('/language', { replace: true });
  };

  const handleContinue = () => navigate('/login');

  return (
    <div className="min-h-screen bg-neutral-50 flex items-center justify-center p-4">
      <div className="w-full max-w-[560px] bg-white rounded-2xl border border-neutral-100 overflow-hidden shadow-sm p-8">
        
        <div className="flex flex-col items-center text-center mb-8">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#3B6D11" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mb-4">
            <path d="M12 22v-8m0 0a4 4 0 014-4V6a6 6 0 00-6 6v2m2-2a4 4 0 00-4-4V6a6 6 0 016 6v2" />
          </svg>
          <h1 className="text-2xl font-bold text-neutral-800 mb-1">{i18n.t('lang.choose_title')}</h1>
          <p className="text-sm text-neutral-500">{i18n.t('lang.choose_subtitle')}</p>
        </div>

        <div className="grid grid-cols-2 gap-3 mb-8">
          {LANGUAGES.map((lang, idx) => {
            const isSelected = currentLang === lang.code;
            return (
              <button
                key={lang.code}
                onClick={() => handleSelect(lang.code)}
                style={{ minHeight: '80px', animation: 'slideInUp 300ms ease-out both', animationDelay: `${idx * 60}ms` }}
                className={`relative flex flex-col justify-center p-4 rounded-xl border-2 text-left transition-colors ${
                  isSelected ? 'border-primary-500 bg-primary-50' : 'border-neutral-200 hover:border-neutral-300'
                }`}
              >
                <p className="font-semibold text-lg text-neutral-800 leading-none mb-1.5">{lang.native}</p>
                <div className="flex items-center gap-1.5 opacity-80">
                  <p className="text-xs font-medium text-neutral-600">{lang.english}</p>
                  <p className="text-[10px] text-neutral-400">— {lang.state}</p>
                </div>
                {isSelected && (
                  <div className="absolute top-3 right-3 w-5 h-5 bg-primary-500 rounded-full flex items-center justify-center">
                    <Check size={12} className="text-white" />
                  </div>
                )}
              </button>
            )
          })}
        </div>

        <button
          onClick={handleContinue}
          disabled={!currentLang}
          style={{ minHeight: '52px' }}
          className="btn-primary w-full flex items-center justify-center gap-2 text-lg disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {currentLang ? i18n.t('lang.continue', { defaultValue: 'आगे बढ़ें · Continue' }) : 'आगे बढ़ें · Continue'}
          <ArrowRight size={20} />
        </button>
      </div>
    </div>
  );
}
