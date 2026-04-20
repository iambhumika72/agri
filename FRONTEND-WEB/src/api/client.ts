// src/api/client.ts
import type {
  PlantPestResult,
  YieldRecord,
  PestRecord,
  SoilRecord,
  FarmSummary,
  HealthStatus,
  RecommendationResponse,
  AlertSummary,
  VisionAnalysis,
} from '../types/api';
import { API_BASE } from '../config';

/**
 * Core API fetch wrapper that prefixes with `/api`
 * and strictly checks for 2xx responses.
 */
export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const token = localStorage.getItem('krishi_token');
  
  const headers = new Headers(options?.headers || {});
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }
  
  // Only set Content-Type if it's not FormData
  if (!(options?.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let errorMessage = `HTTP Error ${response.status}`;
      try {
        const errorData = await response.json();
        errorMessage = errorData.detail || errorData.message || errorMessage;
      } catch (e) {
        // Not JSON
        const textData = await response.text();
        errorMessage = textData || errorMessage;
      }
      throw new Error(errorMessage);
    }

    return response.json();
  } catch (err: any) {
    if (err.name === 'TypeError' && err.message === 'Failed to fetch') {
      throw new Error('Network error — check your connection');
    }
    throw err;
  }
}

// ---------------------------------------------------------------------------
// Vision API
// ---------------------------------------------------------------------------
export const visionAPI = {
  getAnalysisResult: async (farmId: string): Promise<VisionAnalysis> => {
    // MOCKED: endpoint does not exist yet.
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          farm_id: farmId,
          image_path: 'mock/path.png',
          health_score: 85,
          crop_health_status: 'good',
          pest_detected: false,
          pest_type: 'none',
          pest_confidence: 0.0,
          affected_area_pct: 0.0,
          growth_stage_visual: 'vegetative',
          stress_pattern: 'none',
          urgency_level: 'none',
          visual_evidence: 'Leaves appear healthy and vibrant green.',
          recommended_action: 'Continue standard monitoring.',
          analysis_timestamp: new Date().toISOString(),
          gemini_latency_ms: 1200,
          token_count: 50,
        });
      }, 1000);
    });
  },

  getHealth: async (): Promise<any> => {
    // MOCKED: endpoint does not exist yet.
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          gemini_status: 'online',
          faiss_status: 'online',
          total_analyses: 1042,
          last_analysis: new Date().toISOString()
        });
      }, 500);
    });
  }
};

// ---------------------------------------------------------------------------
// Pest API
// ---------------------------------------------------------------------------
export const pestAPI = {
  detectPest: (formData: FormData): Promise<PlantPestResult> =>
    apiFetch<PlantPestResult>('/farmer-input/pest/detect', {
      method: 'POST',
      body: formData,
    }),

  detectPestBase64: (payload: { image_base64: string, farm_id?: string, crop_name?: string }): Promise<PlantPestResult> =>
    apiFetch<PlantPestResult>('/farmer-input/pest/detect/base64', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getHistory: (farmId: string): Promise<PlantPestResult[]> =>
    apiFetch<PlantPestResult[]>(`/farmer-input/pest/history/${farmId}`),
};

// ---------------------------------------------------------------------------
// History API
// ---------------------------------------------------------------------------
export const historyAPI = {
  getYieldHistory: (farmId: string, cropId: string, years = 5): Promise<YieldRecord[]> =>
    apiFetch<YieldRecord[]>(`/history/yield/${farmId}?crop_id=${cropId}&years=${years}`),

  getPestHistory: (farmId: string, startDate: string, endDate: string): Promise<PestRecord[]> =>
    apiFetch<PestRecord[]>(`/history/pests/${farmId}?start_date=${startDate}&end_date=${endDate}`),

  getSoilHealth: (farmId: string, lastN = 10): Promise<SoilRecord[]> =>
    apiFetch<SoilRecord[]>(`/history/soil/${farmId}?last_n=${lastN}`),

  getFarmSummary: (farmId: string): Promise<FarmSummary> =>
    apiFetch<FarmSummary>(`/history/summary/${farmId}`),

  ingestRecord: (payload: any): Promise<{ status: string, table: string }> =>
    apiFetch<{ status: string, table: string }>('/history/ingest', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};

// ---------------------------------------------------------------------------
// Farmer Input API
// ---------------------------------------------------------------------------
export const farmerAPI = {
  submitMobile: (payload: any): Promise<{ record_id: string, status: string }> =>
    apiFetch<{ record_id: string, status: string }>('/farmer-input/mobile', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getHistory: (farmerId: string, limit = 10, offset = 0): Promise<{ records: any[], total_returned: number }> =>
    apiFetch<{ records: any[], total_returned: number }>(`/farmer-input/history/${farmerId}?limit=${limit}&offset=${offset}`),
};

// ---------------------------------------------------------------------------
// Alerts API
// ---------------------------------------------------------------------------
export const alertsAPI = {
  getAlerts: (farmId: string): Promise<AlertSummary> =>
    apiFetch<AlertSummary>(`/alerts/${farmId}`),
    
  triggerAlert: (payload: any): Promise<any> =>
    apiFetch<any>('/alerts/trigger', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};

// ---------------------------------------------------------------------------
// Forecast API
// ---------------------------------------------------------------------------
export const forecastAPI = {
  getForecast: (payload: any): Promise<any> =>
    apiFetch<any>('/forecast/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};

// ---------------------------------------------------------------------------
// Recommendations API
// ---------------------------------------------------------------------------
export const recommendationsAPI = {
  getRecommendation: (payload: { farm_id: string, crop_type: string, season: string }): Promise<RecommendationResponse> =>
    apiFetch<RecommendationResponse>('/recommendations/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};

// ---------------------------------------------------------------------------
// Health API
// ---------------------------------------------------------------------------
export const systemHealthAPI = {
  getSystemHealth: (): Promise<HealthStatus> =>
    apiFetch<HealthStatus>('/health/'),
};

// ---------------------------------------------------------------------------
// Weather API (Mocked)
// ---------------------------------------------------------------------------
export const weatherAPI = {
  getWeather: async (farmId: string): Promise<any> => {
    return new Promise((resolve) => setTimeout(() => resolve({ daily: [] }), 500));
  },
  getHourlySoilMoisture: async (farmId: string): Promise<any[]> => {
    return new Promise((resolve) => setTimeout(() => resolve([]), 500));
  }
};

// ---------------------------------------------------------------------------
// Insights API (Mocked)
// ---------------------------------------------------------------------------
export const insightsAPI = {
  getInsights: async (filters: any): Promise<any[]> => {
    return new Promise((resolve) => setTimeout(() => resolve([]), 500));
  },
  getModelStatus: async (): Promise<any> => {
    return new Promise((resolve) => setTimeout(() => resolve({
      vision: { status: 'healthy', model: 'gemini-1.5-pro', last_run: new Date().toISOString() },
      forecaster: { status: 'healthy', model: 'lstm-v2', last_run: new Date().toISOString() },
      llm: { status: 'healthy', model: 'gemini-1.5-flash', last_run: new Date().toISOString() }
    }), 500));
  }
};

// ---------------------------------------------------------------------------
// Legacy Default Export (Axios-like compatibility)
// ---------------------------------------------------------------------------
const legacyClient = {
  get: <T>(path: string) => apiFetch<T>(path, { method: 'GET' }).then(data => ({ data })),
  post: <T>(path: string, body: any) => apiFetch<T>(path, { 
    method: 'POST', 
    body: typeof body === 'string' ? body : JSON.stringify(body) 
  }).then(data => ({ data })),
  patch: <T>(path: string, body: any) => apiFetch<T>(path, { 
    method: 'PATCH', 
    body: typeof body === 'string' ? body : JSON.stringify(body) 
  }).then(data => ({ data })),
  delete: <T>(path: string) => apiFetch<T>(path, { method: 'DELETE' }).then(data => ({ data })),
};

export default legacyClient;
