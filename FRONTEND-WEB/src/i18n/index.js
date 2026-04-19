import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import en from './locales/en.json';
import hi from './locales/hi.json';
import mr from './locales/mr.json';
import pa from './locales/pa.json';
import gu from './locales/gu.json';
import kn from './locales/kn.json';
import te from './locales/te.json';
import ta from './locales/ta.json';
import bn from './locales/bn.json';

const savedLang = localStorage.getItem('krishi_lang') || 'hi';

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    hi: { translation: hi },
    mr: { translation: mr },
    pa: { translation: pa },
    gu: { translation: gu },
    kn: { translation: kn },
    te: { translation: te },
    ta: { translation: ta },
    bn: { translation: bn },
  },
  lng: savedLang,
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
});

export default i18n;
