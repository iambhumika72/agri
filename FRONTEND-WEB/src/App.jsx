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
import YieldHistoryPage from './pages/YieldHistoryPage';
import SoilHealthPage from './pages/SoilHealthPage';
import PestHistoryPage from './pages/PestHistoryPage';
import SystemHealthPage from './pages/SystemHealthPage';
import PestDetectionPage from './pages/PestDetectionPage';
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
      <Routes>
        {/* Public auth routes */}
        <Route path="/language" element={<LanguageSelectPage />} />
        <Route path="/login" element={<LoginPage />} />

        {/* Protected app routes inside Layout */}
        <Route
          element={
            <ProtectedRoute>
              <Layout>
                <div style={{ animation: 'fadeIn 200ms ease-out both' }} />
              </Layout>
            </ProtectedRoute>
          }
        >
          {/* We use the ProtectedRoute + Layout as a wrapper for these routes */}
        </Route>
        
        {/* This is the better way in RRv6: Nested Routes */}
        <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/farms" element={<FarmsListPage />} />
          <Route path="/farms/:farmId" element={<FarmDetail />} />
          <Route path="/weather" element={<WeatherPage />} />
          <Route path="/insights" element={<InsightsPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/yield" element={<YieldHistoryPage />} />
          <Route path="/soil" element={<SoilHealthPage />} />
          <Route path="/pest-history" element={<PestHistoryPage />} />
          <Route path="/health" element={<SystemHealthPage />} />
          <Route path="/pest-detect" element={<PestDetectionPage />} />
          <Route path="/onboarding" element={<OnboardingPage />} />
          <Route
            path="*"
            element={
              <div className="flex flex-col items-center justify-center h-64 gap-3 text-neutral-400">
                <p className="text-5xl font-bold text-neutral-200">404</p>
                <p className="text-sm">Page not found</p>
              </div>
            }
          />
        </Route>
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
