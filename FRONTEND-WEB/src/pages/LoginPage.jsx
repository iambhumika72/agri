import { useState } from 'react';
import { User, Phone, Shield } from 'lucide-react';
import AuthLayout from '../components/auth/AuthLayout';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from 'react-i18next';

export default function LoginPage() {
  const { t } = useTranslation();
  const { login, isLoading } = useAuth();
  
  const [phone, setPhone] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!name || name.length < 2) return setError(t('auth.validation_name'));
    if (phone.length !== 10) return setError(t('auth.validation_phone'));
    try {
      await login(name, phone);
    } catch (err) { setError(err.message || t('common.error')); }
  };

  return (
    <AuthLayout>
      <div style={{ animation: 'fadeIn 300ms ease-out' }}>
        <div className="flex items-center gap-2 mb-8 md:hidden">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#3B6D11" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 22v-8m0 0a4 4 0 014-4V6a6 6 0 00-6 6v2m2-2a4 4 0 00-4-4V6a6 6 0 016 6v2" />
          </svg>
          <span className="font-bold text-neutral-800 text-xl tracking-tight">KrishiAI</span>
        </div>

        <h1 className="text-[26px] font-bold text-neutral-800 mb-1">{t('auth.what_name', 'अपना परिचय दें')}</h1>
        <p className="text-sm text-neutral-500 mb-8">{t('auth.name_hint', 'अपना नाम और मोबाइल नंबर डालें')}</p>

        {error && (
          <div className="mb-6 bg-danger-50 border border-danger-200 text-danger-600 text-sm rounded-lg px-4 py-3">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Name Field */}
          <div>
            <label className="text-sm font-medium text-neutral-600 block mb-1.5">{t('auth.name_label')}</label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                <User size={20} className="text-neutral-400" />
              </div>
              <input
                type="text" autoFocus
                className="w-full pl-11 pr-4 py-3 text-[18px] border border-neutral-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent h-[52px]"
                placeholder={t('auth.name_placeholder')}
                value={name} onChange={(e) => setName(e.target.value)}
              />
            </div>
          </div>

          {/* Phone Field */}
          <div>
            <label className="text-sm font-medium text-neutral-600 block mb-1.5">{t('auth.phone_label')}</label>
            <div className="flex border border-neutral-300 rounded-xl overflow-hidden focus-within:ring-2 ring-primary-500 h-[52px]">
              <div className="bg-neutral-50 px-4 flex items-center border-r border-neutral-200 min-w-max">
                <Phone size={18} className="text-neutral-400 mr-2" />
                <span className="text-neutral-700 font-bold text-[18px]">+91</span>
              </div>
              <input
                type="tel" maxLength="10"
                className="w-full px-4 text-[20px] tracking-[0.15em] outline-none"
                placeholder={t('auth.phone_placeholder')}
                value={phone} onChange={(e) => setPhone(e.target.value.replace(/\D/g, ''))}
              />
            </div>
          </div>

          <button disabled={isLoading} type="submit" className="btn-primary w-full h-[52px] text-[18px] mt-2 mb-4">
            {isLoading ? t('common.loading') : t('auth.login_btn')}
          </button>
          
          <div className="flex items-center justify-center gap-1.5 text-neutral-400 mt-6">
            <Shield size={14} />
            <p className="text-[12px] font-medium">{t('auth.privacy_note')}</p>
          </div>
        </form>
      </div>
    </AuthLayout>
  );
}
