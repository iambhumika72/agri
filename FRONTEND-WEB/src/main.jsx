import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import './i18n/index';
import './index.css';
import App from './App';
import { LocationProvider } from './context/LocationContext';
import LocationBanner from './components/LocationBanner';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      refetchOnWindowFocus: false,
      staleTime: 5 * 60 * 1000,
    },
  },
});

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <LocationProvider>
          <App />
          <LocationBanner />
        </LocationProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>
);
