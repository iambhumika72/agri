import client from './client';
import farmsData from '../mock/farms.json';

const USE_MOCK = false;

/**
 * Fetch all farms for the authenticated extension worker.
 * @returns {Promise<Array>} List of farm objects
 */
export async function getFarms() {
  if (USE_MOCK) return farmsData;
  const { data } = await client.get('/history/farms');
  return data;
}

/**
 * Fetch a single farm by ID.
 * @param {string} farmId - The farm's unique identifier
 * @returns {Promise<Object>} Farm object
 */
export async function getFarm(farmId) {
  if (USE_MOCK) {
    const farm = farmsData.find((f) => f.id === farmId);
    if (!farm) throw new Error(`Farm ${farmId} not found`);
    return farm;
  }
  const { data } = await client.get(`/farms/${farmId}`);
  return data;
}

/**
 * Create a new farm record.
 * @param {Object} payload - Farm data to create
 * @returns {Promise<Object>} Created farm object
 */
export async function createFarm(payload) {
  if (USE_MOCK) return { ...payload, id: `farm-${Date.now()}` };
  const { data } = await client.post('/farms', payload);
  return data;
}

/**
 * Update an existing farm.
 * @param {string} farmId - Farm ID to update
 * @param {Object} payload - Updated fields
 * @returns {Promise<Object>} Updated farm object
 */
export async function updateFarm(farmId, payload) {
  if (USE_MOCK) return { ...payload, id: farmId };
  const { data } = await client.patch(`/farms/${farmId}`, payload);
  return data;
}

/**
 * Delete a farm record.
 * @param {string} farmId - Farm ID to delete
 * @returns {Promise<void>}
 */
export async function deleteFarm(farmId) {
  if (USE_MOCK) return;
  await client.delete(`/farms/${farmId}`);
}
