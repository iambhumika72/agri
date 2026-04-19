import { useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Loader2, CheckCircle } from 'lucide-react';
import AuthLayout from '../components/auth/AuthLayout';
import client from '../api/client';

const STEPS = ['Email', 'Verify OTP', 'New Password'];

function ProgressBar({ step }) {
  return (
    <div className="mb-8">
      <div className="flex items-center justify-between mb-2">
        {STEPS.map((s, i) => (
          <div key={s} className="flex items-center gap-1">
            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
              i < step ? 'bg-primary-500 text-white' : i === step ? 'bg-primary-100 text-primary-700 border-2 border-primary-500' : 'bg-neutral-100 text-neutral-400'
            }`}>
              {i < step ? '✓' : i + 1}
            </div>
            <span className={`text-xs hidden sm:block ${i === step ? 'text-primary-600 font-medium' : 'text-neutral-400'}`}>{s}</span>
          </div>
        ))}
      </div>
      <div className="h-1.5 bg-neutral-100 rounded-full overflow-hidden">
        <div
          className="h-1.5 bg-primary-500 rounded-full transition-all duration-500 ease-out"
          style={{ width: `${((step) / (STEPS.length - 1)) * 100}%` }}
        />
      </div>
    </div>
  );
}

export default function ForgotPasswordPage() {
  const [step, setStep] = useState(0);
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState(['', '', '', '', '', '']);
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);
  const otpRefs = useRef([]);

  const handleOtpChange = (idx, val) => {
    if (!/^\d?$/.test(val)) return;
    const next = [...otp];
    next[idx] = val;
    setOtp(next);
    if (val && idx < 5) otpRefs.current[idx + 1]?.focus();
  };

  const handleStepOne = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      await new Promise((r) => setTimeout(r, 700)); // Mock
      setStep(1);
    } catch {
      setError('Failed to send reset email.');
    } finally {
      setLoading(false);
    }
  };

  const handleStepTwo = async (e) => {
    e.preventDefault();
    if (otp.join('').length < 6) { setError('Enter all 6 digits.'); return; }
    setLoading(true); setError('');
    try {
      await new Promise((r) => setTimeout(r, 500));
      setStep(2);
    } catch {
      setError('Invalid OTP. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleStepThree = async (e) => {
    e.preventDefault();
    if (newPw !== confirmPw) { setError('Passwords do not match.'); return; }
    if (newPw.length < 6) { setError('Password must be at least 6 characters.'); return; }
    setLoading(true); setError('');
    try {
      await new Promise((r) => setTimeout(r, 700));
      setDone(true);
    } catch {
      setError('Failed to reset password.');
    } finally {
      setLoading(false);
    }
  };

  if (done) {
    return (
      <AuthLayout>
        <div className="flex flex-col items-center text-center py-8 gap-4">
          <div className="w-16 h-16 bg-teal-50 rounded-full flex items-center justify-center">
            <CheckCircle size={32} className="text-teal-500" />
          </div>
          <h2 className="text-xl font-bold text-neutral-800">Password reset!</h2>
          <p className="text-sm text-neutral-400">Your password has been updated. You can now log in.</p>
          <Link to="/login" className="btn-primary mt-2">Back to login</Link>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <Link to="/login" className="inline-flex items-center gap-1.5 text-sm text-neutral-400 hover:text-neutral-700 mb-6">
        <ArrowLeft size={14} /> Back to login
      </Link>

      <ProgressBar step={step} />

      {error && (
        <div className="mb-4 bg-danger-50 border border-danger-200 text-danger-600 text-sm rounded-lg px-4 py-3">{error}</div>
      )}

      {/* Step 0: Email */}
      {step === 0 && (
        <form onSubmit={handleStepOne} className="space-y-4" style={{ animation: 'slideInRight 300ms ease-out both' }}>
          <div>
            <h1 className="text-xl font-bold text-neutral-800 mb-1">Forgot password?</h1>
            <p className="text-sm text-neutral-400 mb-5">We&apos;ll send a 6-digit OTP to your email.</p>
            <label className="text-xs font-medium text-neutral-500 block mb-1">Email address</label>
            <input className="input" type="email" required placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <button type="submit" disabled={loading} className="btn-primary w-full flex items-center justify-center gap-2 py-2.5 disabled:opacity-60">
            {loading ? <><Loader2 size={15} className="animate-spin" /> Sending…</> : 'Send reset code'}
          </button>
        </form>
      )}

      {/* Step 1: OTP */}
      {step === 1 && (
        <form onSubmit={handleStepTwo} className="space-y-6" style={{ animation: 'slideInRight 300ms ease-out both' }}>
          <div>
            <h1 className="text-xl font-bold text-neutral-800 mb-1">Check your email</h1>
            <p className="text-sm text-neutral-400">Enter the 6-digit code sent to <strong>{email}</strong></p>
          </div>
          <div className="flex gap-2 justify-center">
            {otp.map((digit, idx) => (
              <input
                key={idx}
                ref={(el) => (otpRefs.current[idx] = el)}
                id={`otp-${idx}`}
                type="text"
                inputMode="numeric"
                maxLength={1}
                className="w-11 h-12 text-center text-lg font-bold border border-neutral-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500"
                value={digit}
                onChange={(e) => handleOtpChange(idx, e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Backspace' && !digit && idx > 0) otpRefs.current[idx - 1]?.focus();
                }}
              />
            ))}
          </div>
          <button type="submit" disabled={loading} className="btn-primary w-full flex items-center justify-center gap-2 py-2.5 disabled:opacity-60">
            {loading ? <><Loader2 size={15} className="animate-spin" /> Verifying…</> : 'Verify OTP'}
          </button>
        </form>
      )}

      {/* Step 2: New password */}
      {step === 2 && (
        <form onSubmit={handleStepThree} className="space-y-4" style={{ animation: 'slideInRight 300ms ease-out both' }}>
          <div>
            <h1 className="text-xl font-bold text-neutral-800 mb-1">Set new password</h1>
            <p className="text-sm text-neutral-400 mb-2">Choose a strong password for your account.</p>
          </div>
          <div>
            <label className="text-xs font-medium text-neutral-500 block mb-1">New password</label>
            <input className="input" type="password" required placeholder="Min. 6 characters" value={newPw} onChange={(e) => setNewPw(e.target.value)} />
          </div>
          <div>
            <label className="text-xs font-medium text-neutral-500 block mb-1">Confirm password</label>
            <input className="input" type="password" required placeholder="Repeat password" value={confirmPw} onChange={(e) => setConfirmPw(e.target.value)} />
          </div>
          <button type="submit" disabled={loading} className="btn-primary w-full flex items-center justify-center gap-2 py-2.5 disabled:opacity-60">
            {loading ? <><Loader2 size={15} className="animate-spin" /> Saving…</> : 'Reset password'}
          </button>
        </form>
      )}
    </AuthLayout>
  );
}
