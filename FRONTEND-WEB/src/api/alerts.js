import client from './client';
import alertsData from '../mock/alerts.json';

const USE_MOCK = true;

/**
 * Fetch all alerts, optionally filtered by farm, severity, or type.
 * @param {Object} params - Optional: { farmId, severity, alert_type }
 * @returns {Promise<Array>} List of alert objects
 */
export async function getAlerts(params = {}) {
  if (USE_MOCK) {
    let results = [...alertsData].sort(
      (a, b) => new Date(b.timestamp) - new Date(a.timestamp)
    );
    if (params.farmId) results = results.filter((a) => a.farm_id === params.farmId);
    if (params.severity) results = results.filter((a) => a.severity === params.severity);
    if (params.alert_type) results = results.filter((a) => a.alert_type === params.alert_type);
    return results;
  }
  const { data } = await client.get('/alerts', { params });
  return data;
}

/**
 * Fetch alerts for a specific farm.
 * @param {string} farmId - Farm ID
 * @returns {Promise<Array>} List of alerts for the farm
 */
export async function getFarmAlerts(farmId) {
  if (USE_MOCK) {
    return alertsData
      .filter((a) => a.farm_id === farmId)
      .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
  }
  const { data } = await client.get(`/alerts/farm/${farmId}`);
  return data;
}

/**
 * Send an SMS alert to a farm's farmer contact.
 * @param {Object} payload - { farm_id, alert_type, message }
 * @returns {Promise<Object>} SMS dispatch result
 */
export async function sendSMSAlert(payload) {
  if (USE_MOCK) {
    return {
      success: true,
      message_id: `sms-${Date.now()}`,
      status: 'queued',
      farm_id: payload.farm_id,
      chars: payload.message.length,
    };
  }
  const { data } = await client.post('/alerts/send-sms', payload);
  return data;
}

/**
 * Send an SMS alert to all active farms.
 * @param {Object} payload - { alert_type, message }
 * @returns {Promise<Object>} Batch SMS dispatch result
 */
export async function sendBulkSMSAlert(payload) {
  if (USE_MOCK) {
    return {
      success: true,
      batch_id: `batch-${Date.now()}`,
      total: 5,
      queued: 5,
    };
  }
  const { data } = await client.post('/alerts/send-sms/bulk', payload);
  return data;
}

/**
 * Get SMS delivery statistics for today.
 * @returns {Promise<Object>} { sent, delivered, failed, pending }
 */
export async function getSMSStats() {
  if (USE_MOCK) {
    const sent = alertsData.filter((a) => a.sms_sent).length;
    const delivered = alertsData.filter((a) => a.delivery_status === 'delivered').length;
    const failed = alertsData.filter((a) => a.delivery_status === 'failed').length;
    const pending = alertsData.filter((a) => a.delivery_status === 'pending').length;
    return { sent, delivered, failed, pending };
  }
  const { data } = await client.get('/alerts/sms-stats');
  return data;
}
