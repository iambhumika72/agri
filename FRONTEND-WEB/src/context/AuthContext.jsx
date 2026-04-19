import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import { useNavigate } from 'react-router-dom';
import client from '../api/client';

const AuthContext = createContext(null);

const TOKEN_KEY = 'agri_token';
const USER_KEY = 'agri_user';

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState(() => {
    try {
      const raw = localStorage.getItem(USER_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  // Keep axios default header in sync
  useEffect(() => {
    if (token) {
      client.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    } else {
      delete client.defaults.headers.common['Authorization'];
    }
  }, [token]);

  /**
   * Log in with email + password.
   * Calls POST /api/auth/login → { token, user }
   * On success saves to localStorage and redirects to /.
   */
  const login = useCallback(async (email, password) => {
    setIsLoading(true);
    try {
      // Mock: accept any credentials in dev
      const USE_MOCK = true;
      let data;
      if (USE_MOCK) {
        await new Promise((r) => setTimeout(r, 800));
        if (email && password.length >= 4) {
          data = {
            token: 'mock-jwt-token-' + Date.now(),
            user: {
              id: 'usr-001',
              name: email.split('@')[0].replace(/[^a-zA-Z]/g, ' ').trim() || 'Arjun Wali',
              email,
              role: 'Extension Worker',
              worker_id: 'EW-214',
            },
          };
        } else {
          throw new Error('Invalid credentials. Please try again.');
        }
      } else {
        const res = await client.post('/auth/login', { email, password });
        data = res.data;
      }
      localStorage.setItem(TOKEN_KEY, data.token);
      localStorage.setItem(USER_KEY, JSON.stringify(data.user));
      setToken(data.token);
      setUser(data.user);
      navigate('/');
    } finally {
      setIsLoading(false);
    }
  }, [navigate]);

  /**
   * Register a new account.
   * Calls POST /api/auth/signup → { token, user }
   */
  const signup = useCallback(async (payload) => {
    setIsLoading(true);
    try {
      const USE_MOCK = true;
      let data;
      if (USE_MOCK) {
        await new Promise((r) => setTimeout(r, 1000));
        data = {
          token: 'mock-jwt-token-' + Date.now(),
          user: {
            id: 'usr-new-' + Date.now(),
            name: payload.name,
            email: payload.email,
            role: payload.role || 'Extension Worker',
            worker_id: 'EW-' + Math.floor(Math.random() * 900 + 100),
          },
        };
      } else {
        const res = await client.post('/auth/signup', payload);
        data = res.data;
      }
      localStorage.setItem(TOKEN_KEY, data.token);
      localStorage.setItem(USER_KEY, JSON.stringify(data.user));
      setToken(data.token);
      setUser(data.user);
      navigate('/onboarding');
    } finally {
      setIsLoading(false);
    }
  }, [navigate]);

  /** Clear auth state and redirect to /login */
  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setToken(null);
    setUser(null);
    navigate('/login');
  }, [navigate]);

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

AuthProvider.propTypes = {
  children: PropTypes.node.isRequired,
};

/** Hook to consume auth context */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
