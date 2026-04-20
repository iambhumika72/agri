import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import { useNavigate } from 'react-router-dom';
const AuthContext = createContext(null);
const TOKEN_KEY = 'krishi_token';
const USER_KEY = 'krishi_user';

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem(USER_KEY)); } catch { return null; }
  });
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    // client.ts now dynamically reads the token from localStorage per request.
  }, [token]);

  const login = useCallback(async (name, phone) => {
    setIsLoading(true);
    try {
      await new Promise(r => setTimeout(r, 900));
      const lang = localStorage.getItem('krishi_lang');
      const data = {
        token: 'krishi-jwt-' + Date.now(),
        user: { id: 'usr-1', name, phone: `+91${phone}`, language: lang || 'en' }
      };
      localStorage.setItem(TOKEN_KEY, data.token);
      localStorage.setItem(USER_KEY, JSON.stringify(data.user));
      setToken(data.token); setUser(data.user);
      
      if (!lang) navigate('/language');
      else navigate('/');
      
      return data;
    } finally { setIsLoading(false); }
  }, [navigate]);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY);
    setToken(null); setUser(null); navigate('/login');
  }, [navigate]);

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

AuthProvider.propTypes = { children: PropTypes.node.isRequired };
export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
};
