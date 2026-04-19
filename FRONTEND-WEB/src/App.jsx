import { Routes, Route, useLocation } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/auth/ProtectedRoute';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import FarmsListPage from './pages/FarmsListPage';
import FarmDetail from './pages/FarmDetail';
import WeatherPage from './pages/WeatherPage';
import InsightsPage from './pages/InsightsPage';
import AlertsPage from './pages/AlertsPage';
import LoginPage from './pages/LoginPage';
import LanguageSelectPage from './pages/LanguageSelectPage';
import OnboardingPage from './pages/OnboardingPage';

/** Wraps route outlet with a fadeIn animation keyed to pathname */
import { useEffect } from 'react';

/** Wraps route outlet with a fadeIn animation keyed to pathname */
function AnimatedRoutes() {
  const location = useLocation();

  // Redirect to language select if no language preference 
  useEffect(() => {
    if (!localStorage.getItem('krishi_lang') && location.pathname !== '/language') {
      window.location.href = '/language';
    }
  }, [location.pathname]);

  return (
    <div key={location.pathname} style={{ animation: 'fadeIn 200ms ease-out both' }}>
      <Routes location={location}>
        {/* Public auth routes */}
        <Route path="/language" element={<LanguageSelectPage />} />
        <Route path="/login" element={<LoginPage />} />

        {/* Onboarding (needs auth) */}
        <Route
          path="/onboarding"
          element={
            <ProtectedRoute>
              <OnboardingPage />
            </ProtectedRoute>
          }
        />

        {/* Protected app routes inside Layout */}
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <Layout>
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/farms" element={<FarmsListPage />} />
                  <Route path="/farms/:farmId" element={<FarmDetail />} />
                  <Route path="/weather" element={<WeatherPage />} />
                  <Route path="/insights" element={<InsightsPage />} />
                  <Route path="/alerts" element={<AlertsPage />} />
                  <Route
                    path="*"
                    element={
                      <div className="flex flex-col items-center justify-center h-64 gap-3 text-neutral-400">
                        <p className="text-5xl font-bold text-neutral-200">404</p>
                        <p className="text-sm">Page not found</p>
                      </div>
                    }
                  />
                </Routes>
              </Layout>
            </ProtectedRoute>
          }
        />
      </Routes>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AnimatedRoutes />
    </AuthProvider>
  );
}
