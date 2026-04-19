import client from './client';
import weatherData from '../mock/weather.json';

const USE_MOCK = true;

/**
 * Fetch 7-day weather forecast for a specific farm.
 * @param {string} farmId - The farm's unique identifier
 * @returns {Promise<Object>} Weather forecast object with daily and hourly arrays
 */
export async function getWeatherForecast(farmId) {
  if (USE_MOCK) {
    const forecast = weatherData[farmId];
    if (!forecast) throw new Error(`No weather data for farm ${farmId}`);
    return forecast;
  }
  const { data } = await client.get(`/weather/${farmId}/forecast`);
  return data;
}

/**
 * Fetch today's hourly soil moisture data for a farm.
 * @param {string} farmId - Farm ID
 * @returns {Promise<Array>} Array of { hour, moisture } objects
 */
export async function getHourlySoilMoisture(farmId) {
  if (USE_MOCK) {
    const forecast = weatherData[farmId];
    return forecast?.hourly_soil_moisture || [];
  }
  const { data } = await client.get(`/weather/${farmId}/soil-moisture/hourly`);
  return data;
}

/**
 * Fetch weather forecasts for all farms (dashboard summary).
 * @returns {Promise<Object>} Map of farmId → forecast
 */
export async function getAllWeatherForecasts() {
  if (USE_MOCK) return weatherData;
  const { data } = await client.get('/weather/all');
  return data;
}
