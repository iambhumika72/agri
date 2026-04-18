"""
weather_client.py
-----------------
Async HTTP client for the Open-Meteo weather forecast API.
Primary data source for the KrishiAI Sustainable Agriculture platform.

Provider : Open-Meteo  (https://open-meteo.com/) — free, no API key required
Author   : KrishiAI Backend Team
"""

import logging
import os
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants / configuration via environment variables
# ---------------------------------------------------------------------------
OPEN_METEO_BASE_URL: str = os.getenv(
    "OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1/forecast"
)
HTTP_TIMEOUT_SECONDS: float = float(os.getenv("HTTP_TIMEOUT_SECONDS", "10"))
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
BACKOFF_MIN: float = float(os.getenv("BACKOFF_MIN_SECONDS", "1"))
BACKOFF_MAX: float = float(os.getenv("BACKOFF_MAX_SECONDS", "16"))

# Daily variables requested from Open-Meteo
DAILY_VARIABLES: list[str] = [
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "windspeed_10m_max",
    "et0_fao_evapotranspiration",
    "weathercode",
]

# Hourly variables requested from Open-Meteo
HOURLY_VARIABLES: list[str] = [
    "soil_moisture_0_to_1cm",
]


# ---------------------------------------------------------------------------
# Retry-decorated fetch helper
# ---------------------------------------------------------------------------
def _build_retry_decorator():
    """Build the tenacity retry decorator with structured back-off."""
    return retry(
        retry=retry_if_exception_type(
            (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError)
        ),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=BACKOFF_MIN, max=BACKOFF_MAX),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


class WeatherAPIError(Exception):
    """Raised when the Open-Meteo API returns an unrecoverable error."""


class WeatherClient:
    """
    Async client for the Open-Meteo /v1/forecast endpoint.

    Usage::

        async with WeatherClient() as client:
            raw = await client.fetch_forecast(lat=19.0760, lon=72.8777, farm_id="FARM_001")

    The client handles:
    - Connection / read timeouts (10 s default)
    - Automatic retries with exponential back-off (3 attempts)
    - HTTP 4xx / 5xx error propagation as ``WeatherAPIError``
    """

    def __init__(
        self,
        base_url: str = OPEN_METEO_BASE_URL,
        timeout: float = HTTP_TIMEOUT_SECONDS,
    ) -> None:
        """
        Initialise the client.

        Args:
            base_url: Open-Meteo forecast endpoint.
            timeout:  Per-request timeout in seconds.
        """
        self._base_url = base_url
        self._timeout = httpx.Timeout(timeout)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "WeatherClient":
        """Open the underlying HTTPX session."""
        self._client = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, *_: Any) -> None:
        """Close the underlying HTTPX session."""
        if self._client:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch_forecast(
        self,
        latitude: float,
        longitude: float,
        farm_id: str,
    ) -> dict[str, Any]:
        """
        Fetch a 7-day weather forecast from Open-Meteo.

        Args:
            latitude:  Farm latitude in decimal degrees.
            longitude: Farm longitude in decimal degrees.
            farm_id:   Opaque identifier for the farm (injected into response).

        Returns:
            Raw JSON response from Open-Meteo augmented with ``farm_id``.

        Raises:
            WeatherAPIError: On HTTP 4xx/5xx after all retries exhausted.
            httpx.TimeoutException: If the server does not respond in time
                (after all retries exhausted).
        """
        if self._client is None:
            raise RuntimeError(
                "WeatherClient must be used as an async context manager."
            )

        params = self._build_params(latitude, longitude)
        logger.info(
            "Fetching weather forecast",
            extra={"farm_id": farm_id, "latitude": latitude, "longitude": longitude},
        )

        raw = await self._fetch_with_retry(params)
        raw["farm_id"] = farm_id  # annotate for downstream consumers
        return raw

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_params(self, latitude: float, longitude: float) -> dict[str, Any]:
        """Build the Open-Meteo query-string parameters."""
        return {
            "latitude": latitude,
            "longitude": longitude,
            "daily": ",".join(DAILY_VARIABLES),
            "hourly": ",".join(HOURLY_VARIABLES),
            "forecast_days": 7,
            "timezone": "auto",
        }

    @_build_retry_decorator()
    async def _fetch_with_retry(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the HTTP GET request, raising on non-2xx status.

        This method is wrapped by the tenacity retry decorator so that
        transient failures are automatically retried with exponential back-off.
        """
        assert self._client is not None  # guaranteed by fetch_forecast guard
        response = await self._client.get(self._base_url, params=params)

        if response.status_code >= 400:
            logger.error(
                "Open-Meteo returned HTTP error",
                extra={"status_code": response.status_code, "body": response.text[:512]},
            )
            raise WeatherAPIError(
                f"Open-Meteo API error {response.status_code}: {response.text[:256]}"
            )

        response.raise_for_status()
        data: dict[str, Any] = response.json()
        logger.debug("Weather forecast fetched successfully", extra={"keys": list(data.keys())})
        return data
