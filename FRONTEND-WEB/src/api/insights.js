import client from './client';
import insightsData from '../mock/insights.json';

const USE_MOCK = true;

/**
 * Fetch all AI recommendations, optionally filtered.
 * @param {Object} params - Optional query params { farmId, category, priority }
 * @returns {Promise<Array>} List of insight objects
 */
export async function getInsights(params = {}) {
  if (USE_MOCK) {
    let results = [...insightsData];
    if (params.farmId) results = results.filter((i) => i.farm_id === params.farmId);
    if (params.category) results = results.filter((i) => i.category === params.category);
    if (params.priority) results = results.filter((i) => i.priority === params.priority);
    return results;
  }
  const { data } = await client.get('/insights', { params });
  return data;
}

/**
 * Fetch insights for a specific farm.
 * @param {string} farmId - Farm ID
 * @returns {Promise<Array>} List of insight objects for the farm
 */
export async function getFarmInsights(farmId) {
  if (USE_MOCK) return insightsData.filter((i) => i.farm_id === farmId);
  const { data } = await client.get(`/insights/farm/${farmId}`);
  return data;
}

/**
 * Get AI model status (last run times and health).
 * @returns {Promise<Object>} Model status object
 */
export async function getModelStatus() {
  if (USE_MOCK) {
    return {
      vision: { status: 'healthy', last_run: '2025-10-06T08:30:00Z', model: 'ViT-L/16' },
      forecaster: { status: 'healthy', last_run: '2025-10-06T06:00:00Z', model: 'LSTM-v2' },
      llm: { status: 'healthy', last_run: '2025-10-06T09:00:00Z', model: 'Gemini-1.5-Pro' },
    };
  }
  const { data } = await client.get('/insights/model-status');
  return data;
}

/**
 * Trigger SMS send for an insight.
 * @param {string} insightId - Insight ID
 * @param {string} farmId - Target farm ID
 * @returns {Promise<Object>} SMS dispatch result
 */
export async function sendInsightSMS(insightId, farmId) {
  if (USE_MOCK) {
    return { success: true, message_id: `sms-${Date.now()}`, status: 'queued' };
  }
  const { data } = await client.post(`/insights/${insightId}/send-sms`, { farm_id: farmId });
  return data;
}
