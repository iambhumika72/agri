import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Eye, EyeOff, Loader2 } from 'lucide-react';
import AuthLayout from '../components/auth/AuthLayout';
import { useAuth } from '../context/AuthContext';

const ROLES = ['Extension Worker', 'Agronomist', 'Farm Manager'];

export default function SignupPage() {
  const { signup, isLoading } = useAuth();
  const [form, setForm] = useState({
    name: '', email: '', phone: '', password: '', confirmPassword: '', role: 'Extension Worker',
  });
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState('');

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (form.password !== form.confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    if (form.password.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }
    try {
      await signup({ name: form.name, email: form.email, phone: form.phone, role: form.role });
    } catch (err) {
      setError(err.message || 'Signup failed. Please try again.');
    }
  };

  return (
    <AuthLayout>
      <h1 className="text-2xl font-bold text-neutral-800 mb-1">Create your account</h1>
      <p className="text-sm text-neutral-400 mb-6">Join AgriAI to manage your farms with AI</p>

      {error && (
        <div className="mb-4 bg-danger-50 border border-danger-200 text-danger-600 text-sm rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Name */}
        <div>
          <label className="text-xs font-medium text-neutral-500 block mb-1" htmlFor="signup-name">Full name</label>
          <input id="signup-name" type="text" required className="input" placeholder="Raju Krishnamurthy" value={form.name} onChange={set('name')} />
        </div>

        {/* Email */}
        <div>
          <label className="text-xs font-medium text-neutral-500 block mb-1" htmlFor="signup-email">Email</label>
          <input id="signup-email" type="email" required className="input" placeholder="you@example.com" value={form.email} onChange={set('email')} />
        </div>

        {/* Phone */}
        <div>
          <label className="text-xs font-medium text-neutral-500 block mb-1" htmlFor="signup-phone">
            Phone <span className="text-neutral-300">(optional)</span>
          </label>
          <input id="signup-phone" type="tel" className="input" placeholder="+91 98765 43210" value={form.phone} onChange={set('phone')} />
        </div>

        {/* Password */}
        <div>
          <label className="text-xs font-medium text-neutral-500 block mb-1" htmlFor="signup-password">Password</label>
          <div className="relative">
            <input
              id="signup-password"
              type={showPw ? 'text' : 'password'}
              required
              className="input pr-10"
              placeholder="Min. 6 characters"
              value={form.password}
              onChange={set('password')}
            />
            <button type="button" tabIndex={-1} onClick={() => setShowPw((v) => !v)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-600">
              {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
            </button>
          </div>
        </div>

        {/* Confirm password */}
        <div>
          <label className="text-xs font-medium text-neutral-500 block mb-1" htmlFor="signup-confirm">Confirm password</label>
          <input
            id="signup-confirm"
            type="password"
            required
            className="input"
            placeholder="Repeat password"
            value={form.confirmPassword}
            onChange={set('confirmPassword')}
          />
        </div>

        {/* Role pill toggles */}
        <div>
          <label className="text-xs font-medium text-neutral-500 block mb-2">Role</label>
          <div className="flex gap-2 flex-wrap">
            {ROLES.map((r) => (
              <button
                key={r}
                type="button"
                id={`role-${r.replace(/\s+/g, '-').toLowerCase()}`}
                onClick={() => setForm((f) => ({ ...f, role: r }))}
                className={`text-xs px-3 py-2 rounded-full border font-medium transition-colors ${
                  form.role === r
                    ? 'bg-primary-500 text-white border-primary-500'
                    : 'bg-white text-neutral-600 border-neutral-200 hover:border-neutral-300'
                }`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>

        <button
          id="signup-submit"
          type="submit"
          disabled={isLoading}
          className="btn-primary w-full flex items-center justify-center gap-2 py-2.5 text-base disabled:opacity-60 mt-2"
        >
          {isLoading ? <><Loader2 size={16} className="animate-spin" />Creating account…</> : 'Create account'}
        </button>
      </form>

      <p className="text-sm text-center text-neutral-400 mt-6">
        Already have an account?{' '}
        <Link to="/login" className="text-primary-600 font-medium hover:underline">Sign in</Link>
      </p>
    </AuthLayout>
  );
}
