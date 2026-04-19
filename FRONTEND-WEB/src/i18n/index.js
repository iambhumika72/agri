import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import en from './locales/en.json';
import hi from './locales/hi.json';
import sw from './locales/sw.json';
import mr from './locales/mr.json';
import ta from './locales/ta.json';
import fr from './locales/fr.json';

const savedLang = localStorage.getItem('agri_lang') || 'en';

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    hi: { translation: hi },
    sw: { translation: sw },
    mr: { translation: mr },
    ta: { translation: ta },
    fr: { translation: fr },
  },
  lng: savedLang,
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
});

export default i18n;
