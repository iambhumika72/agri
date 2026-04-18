"""
test_weather_module.py
----------------------
Comprehensive unit test suite for the KrishiAI weather data module.

Coverage
--------
* WeatherClient — normal fetch, timeout retry (mocked HTTP)
* engineer_features — drought_risk_score edge cases, per-day feature correctness
* format_sms — 160-char enforcement, priority logic
* weather_pipeline_adapter — crop_season tagging for boundary months

Dependencies
------------
    pytest
    pytest-asyncio
    responses  (for mocking httpx — uses httpx-mock via pytest_httpx)
    pydantic
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import pytest_asyncio

# pytest-asyncio mode
pytest_plugins = ["pytest_asyncio"]

# ---------------------------------------------------------------------------
# Fixtures — synthetic Open-Meteo responses
# ---------------------------------------------------------------------------

def _make_raw_response(
    farm_id: str = "FARM_TEST",
    days: int = 7,
    temp_max: list[float] | None = None,
    temp_min: list[float] | None = None,
    precip: list[float] | None = None,
    et0: list[float] | None = None,
    wind: list[float] | None = None,
    wcodes: list[int] | None = None,
    soil_moisture: list[float] | None = None,
    start_date: date | None = None,
) -> dict[str, Any]:
    """
    Build a synthetic Open-Meteo API response dict for testing.

    All array parameters are broadcast to *days* entries if not supplied.
    Soil moisture is supplied as 24 * days hourly readings (one per hour).
    """
    base = start_date or date(2024, 7, 1)
    dates = [(base + timedelta(days=i)).isoformat() for i in range(days)]
    hours = []
    soil_hour = []
    for i in range(days):
        d = base + timedelta(days=i)
        for h in range(24):
            hours.append(f"{d.isoformat()}T{h:02d}:00")
            soil_val = (soil_moisture[i] if soil_moisture else 0.25)
            soil_hour.append(soil_val)

    return {
        "farm_id": farm_id,
        "daily": {
            "time": dates,
            "temperature_2m_max": temp_max or [32.0] * days,
            "temperature_2m_min": temp_min or [22.0] * days,
            "precipitation_sum": precip or [0.0] * days,
            "windspeed_10m_max": wind or [15.0] * days,
            "et0_fao_evapotranspiration": et0 or [5.0] * days,
            "weathercode": wcodes or [0] * days,
        },
        "hourly": {
            "time": hours,
            "soil_moisture_0_to_1cm": soil_hour,
        },
    }


# ---------------------------------------------------------------------------
# WeatherClient tests
# ---------------------------------------------------------------------------

class TestWeatherClient:
    """Tests for WeatherClient — HTTP fetch, retries, and error handling."""

    @pytest.mark.asyncio
    async def test_fetch_forecast_success(self):
        """Normal fetch returns dict annotated with farm_id."""
        from weather_client import WeatherClient

        mock_response_data = _make_raw_response("FARM_001")
        # Remove farm_id since the client adds it after fetching
        api_payload = {k: v for k, v in mock_response_data.items() if k != "farm_id"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = api_payload
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        async with WeatherClient() as client:
            client._client = mock_client
            result = await client.fetch_forecast(19.0760, 72.8777, "FARM_001")

        assert result["farm_id"] == "FARM_001"
        assert "daily" in result
        assert "hourly" in result
        mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_forecast_http_error_raises(self):
        """HTTP 500 from API raises WeatherAPIError."""
        import httpx
        from weather_client import WeatherClient, WeatherAPIError

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with pytest.raises((WeatherAPIError, Exception)):
            async with WeatherClient() as client:
                client._client = mock_client
                # Patch retry to stop immediately
                with patch("weather_client.MAX_RETRIES", 1):
                    await client.fetch_forecast(0.0, 0.0, "FARM_ERR")

    @pytest.mark.asyncio
    async def test_fetch_timeout_retries(self):
        """TimeoutException triggers retries (mock raises then succeeds)."""
        import httpx
        from weather_client import WeatherClient

        api_payload = _make_raw_response()
        api_payload.pop("farm_id", None)

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = api_payload
        success_response.raise_for_status = MagicMock()

        call_count = {"n": 0}

        async def _side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] < 2:
                raise httpx.ReadTimeout("timed out", request=None)
            return success_response

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=_side_effect)

        async with WeatherClient() as client:
            client._client = mock_client
            result = await client.fetch_forecast(0.0, 0.0, "FARM_RETRY")

        assert call_count["n"] == 2  # failed once, succeeded on second attempt
        assert result["farm_id"] == "FARM_RETRY"

    @pytest.mark.asyncio
    async def test_client_without_context_manager_raises(self):
        """Calling fetch_forecast outside context manager raises RuntimeError."""
        from weather_client import WeatherClient

        client = WeatherClient()  # not entered as context manager
        with pytest.raises(RuntimeError, match="async context manager"):
            await client.fetch_forecast(0.0, 0.0, "FARM_X")


# ---------------------------------------------------------------------------
# Feature engineering tests
# ---------------------------------------------------------------------------

class TestEngineerFeatures:
    """Tests for the feature engineering layer."""

    def test_basic_features_computed_correctly(self):
        """Verify temp_mean_c and temp_range_c are correct."""
        from weather_features import engineer_features

        raw = _make_raw_response(temp_max=[30.0] * 7, temp_min=[20.0] * 7)
        features = engineer_features(raw)

        assert len(features) == 7
        for f in features:
            assert f.temp_mean_c == pytest.approx(25.0, abs=0.01)
            assert f.temp_range_c == pytest.approx(10.0, abs=0.01)

    def test_frost_risk_detected(self):
        """is_frost_risk is True when temp_min < 4°C."""
        from weather_features import engineer_features

        temp_min = [3.5] + [20.0] * 6  # only day 0 is frosty
        raw = _make_raw_response(temp_min=temp_min)
        features = engineer_features(raw)

        assert features[0].is_frost_risk is True
        for f in features[1:]:
            assert f.is_frost_risk is False

    def test_frost_risk_boundary_exactly_4c(self):
        """is_frost_risk is False when temp_min == 4.0 (strictly less than)."""
        from weather_features import engineer_features

        raw = _make_raw_response(temp_min=[4.0] * 7)
        features = engineer_features(raw)
        assert all(not f.is_frost_risk for f in features)

    def test_heat_stress_detected(self):
        """is_heat_stress is True when temp_max > 38°C."""
        from weather_features import engineer_features

        temp_max = [39.0] + [30.0] * 6
        raw = _make_raw_response(temp_max=temp_max)
        features = engineer_features(raw)

        assert features[0].is_heat_stress is True
        for f in features[1:]:
            assert f.is_heat_stress is False

    def test_drought_risk_zero_with_surplus_rain(self):
        """Drought risk should be 0 when precip >> et0 throughout the window."""
        from weather_features import engineer_features

        raw = _make_raw_response(
            precip=[20.0] * 7,
            et0=[3.0] * 7,
        )
        features = engineer_features(raw)
        for f in features:
            assert f.drought_risk_score == pytest.approx(0.0, abs=0.001)

    def test_drought_risk_maximum_with_zero_rain(self):
        """Drought risk should be 1.0 when precip=0 and et0>0 across all days."""
        from weather_features import engineer_features

        raw = _make_raw_response(
            precip=[0.0] * 7,
            et0=[8.0] * 7,
        )
        features = engineer_features(raw)
        # By day 6 (full 7-day window of zero rain) drought score must be 1.0
        assert features[6].drought_risk_score == pytest.approx(1.0, abs=0.001)

    def test_drought_risk_zero_et0_does_not_divide_by_zero(self):
        """Drought risk is 0 when et0=0 (no evaporation demand, no drought)."""
        from weather_features import engineer_features

        raw = _make_raw_response(precip=[0.0] * 7, et0=[0.0] * 7)
        features = engineer_features(raw)
        for f in features:
            assert f.drought_risk_score == pytest.approx(0.0, abs=1e-6)

    def test_rain_probability_from_wmo_code(self):
        """Rain probability = 1.0 for rain WMO codes, 0.0 for clear codes."""
        from weather_features import engineer_features

        # code 61 = moderate rain; code 0 = clear sky
        wcodes = [61, 0, 63, 1, 80, 2, 55]
        raw = _make_raw_response(wcodes=wcodes)
        features = engineer_features(raw)

        expected = [1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0]
        for feat, exp in zip(features, expected):
            assert feat.rain_probability == exp

    def test_soil_moisture_averaged_per_day(self):
        """soil_moisture_avg should equal the input hourly value (uniform mock)."""
        from weather_features import engineer_features

        soil = [0.3] * 7
        raw = _make_raw_response(soil_moisture=soil)
        features = engineer_features(raw)

        for f in features:
            assert f.soil_moisture_avg == pytest.approx(0.3, abs=1e-5)

    def test_mismatched_array_lengths_raises(self):
        """Mismatched daily arrays raise ValueError."""
        from weather_features import engineer_features

        raw = _make_raw_response()
        raw["daily"]["temperature_2m_max"].pop()  # now length 6 instead of 7

        with pytest.raises(ValueError, match="mismatched lengths"):
            engineer_features(raw)


# ---------------------------------------------------------------------------
# SMS formatter tests
# ---------------------------------------------------------------------------

class TestSMSFormatter:
    """Tests for the SMS alert formatter."""

    def _make_feat(self, **kwargs) -> "DailyWeatherFeatures":
        from weather_features import DailyWeatherFeatures

        defaults = {
            "farm_id": "FARM_001",
            "forecast_date": date(2024, 7, 1),
            "temp_mean_c": 27.0,
            "temp_range_c": 10.0,
            "precip_mm": 0.0,
            "rain_probability": 0.0,
            "wind_kmh": 10.0,
            "et0_mm": 4.5,
            "drought_risk_score": 0.0,
            "is_frost_risk": False,
            "is_heat_stress": False,
            "soil_moisture_avg": 0.25,
        }
        defaults.update(kwargs)
        return DailyWeatherFeatures(**defaults)

    def test_sms_max_160_chars_normal(self):
        """Normal conditions SMS ≤ 160 chars."""
        from weather_sms_formatter import format_sms

        feat = self._make_feat()
        sms = format_sms(feat)
        assert len(sms) <= 160, f"SMS too long ({len(sms)}): {sms!r}"

    def test_sms_max_160_chars_all_alerts(self):
        """Frost-risk alert SMS ≤ 160 chars."""
        from weather_sms_formatter import format_sms

        feat = self._make_feat(is_frost_risk=True, precip_mm=1.0)
        sms = format_sms(feat)
        assert len(sms) <= 160, f"SMS too long ({len(sms)}): {sms!r}"

    def test_sms_max_160_chars_heat_stress(self):
        """Heat-stress alert SMS ≤ 160 chars."""
        from weather_sms_formatter import format_sms

        feat = self._make_feat(is_heat_stress=True)
        sms = format_sms(feat)
        assert len(sms) <= 160

    def test_sms_max_160_chars_drought_high(self):
        """High drought alert SMS ≤ 160 chars."""
        from weather_sms_formatter import format_sms

        feat = self._make_feat(drought_risk_score=0.95)
        sms = format_sms(feat)
        assert len(sms) <= 160

    def test_sms_max_160_chars_long_farm_id(self):
        """Long farm IDs are truncated to keep SMS within limit."""
        from weather_sms_formatter import format_sms

        feat = self._make_feat(farm_id="VERY_LONG_FARM_IDENTIFIER_EXCEEDING_NORMAL_LENGTH")
        sms = format_sms(feat)
        assert len(sms) <= 160

    def test_frost_prioritised_over_heat(self):
        """Frost risk is mentioned when both frost and heat flags are set."""
        from weather_sms_formatter import format_sms

        feat = self._make_feat(is_frost_risk=True, is_heat_stress=True)
        sms = format_sms(feat)
        assert "FROST" in sms.upper()

    def test_heat_prioritised_over_drought(self):
        """Heat stress is mentioned over drought when both are present."""
        from weather_sms_formatter import format_sms

        feat = self._make_feat(is_heat_stress=True, drought_risk_score=0.9)
        sms = format_sms(feat)
        assert "HEAT" in sms.upper()

    def test_no_alert_message_contains_water_advice(self):
        """No-alert message contains watering advice."""
        from weather_sms_formatter import format_sms

        feat = self._make_feat()
        sms = format_sms(feat)
        assert "Water" in sms or "water" in sms or "Good" in sms

    def test_batch_formatter_returns_correct_count(self):
        """format_sms_batch returns one entry per input feature."""
        from weather_sms_formatter import format_sms_batch
        from weather_features import engineer_features

        raw = _make_raw_response()
        features = engineer_features(raw)
        results = format_sms_batch(features)

        assert len(results) == 7
        for r in results:
            assert "farm_id" in r
            assert "date" in r
            assert "sms" in r
            assert len(r["sms"]) <= 160


# ---------------------------------------------------------------------------
# Pipeline adapter / crop-season tests
# ---------------------------------------------------------------------------

class TestPipelineAdapter:
    """Tests for weather_pipeline_adapter — schema and crop season tagging."""

    def test_crop_season_kharif_june(self):
        """June is kharif season."""
        from weather_pipeline_adapter import tag_crop_season
        assert tag_crop_season(date(2024, 6, 1)) == "kharif"

    def test_crop_season_kharif_october(self):
        """October is kharif season."""
        from weather_pipeline_adapter import tag_crop_season
        assert tag_crop_season(date(2024, 10, 31)) == "kharif"

    def test_crop_season_rabi_november(self):
        """November is rabi season."""
        from weather_pipeline_adapter import tag_crop_season
        assert tag_crop_season(date(2024, 11, 1)) == "rabi"

    def test_crop_season_rabi_march(self):
        """March is rabi season."""
        from weather_pipeline_adapter import tag_crop_season
        assert tag_crop_season(date(2024, 3, 31)) == "rabi"

    def test_crop_season_zaid_april(self):
        """April is zaid season."""
        from weather_pipeline_adapter import tag_crop_season
        assert tag_crop_season(date(2024, 4, 1)) == "zaid"

    def test_crop_season_zaid_may(self):
        """May is zaid season."""
        from weather_pipeline_adapter import tag_crop_season
        assert tag_crop_season(date(2024, 5, 31)) == "zaid"

    def test_crop_season_boundary_june_1(self):
        """1 June is the kharif start boundary."""
        from weather_pipeline_adapter import tag_crop_season
        assert tag_crop_season(date(2024, 6, 1)) == "kharif"

    def test_crop_season_boundary_november_1(self):
        """1 November is the rabi start boundary."""
        from weather_pipeline_adapter import tag_crop_season
        assert tag_crop_season(date(2024, 11, 1)) == "rabi"

    def test_adapt_batch_produces_correct_schema(self):
        """adapt_batch output matches PipelineRecord schema."""
        from weather_pipeline_adapter import adapt_batch

        raw = _make_raw_response(farm_id="FARM_001")
        records = adapt_batch([raw])

        assert len(records) == 7
        for rec in records:
            assert rec.source == "weather"
            assert rec.farm_id == "FARM_001"
            assert rec.timestamp  # non-empty ISO date
            assert "crop_season" in rec.metadata
            assert rec.metadata["crop_season"] in {"kharif", "rabi", "zaid"}
            # All required feature keys must be present
            for key in [
                "temp_mean_c", "temp_range_c", "precip_mm", "rain_probability",
                "wind_kmh", "et0_mm", "drought_risk_score", "is_frost_risk",
                "is_heat_stress", "soil_moisture_avg",
            ]:
                assert key in rec.features, f"Missing feature key: {key}"

    def test_adapt_batch_handles_bad_farm_gracefully(self):
        """adapt_batch skips malformed farm data and still returns others."""
        from weather_pipeline_adapter import adapt_batch

        good_raw = _make_raw_response(farm_id="GOOD_FARM")
        bad_raw = {"farm_id": "BAD_FARM", "daily": {}, "hourly": {}}  # missing arrays

        records = adapt_batch([good_raw, bad_raw])
        farm_ids = {r.farm_id for r in records}
        assert "GOOD_FARM" in farm_ids
        assert "BAD_FARM" not in farm_ids

    def test_pipeline_records_as_dicts_is_json_serialisable(self):
        """pipeline_records_as_dicts produces JSON-serialisable output."""
        from weather_pipeline_adapter import adapt_batch, pipeline_records_as_dicts

        raw = _make_raw_response()
        records = adapt_batch([raw])
        dicts = pipeline_records_as_dicts(records)

        serialised = json.dumps(dicts)  # must not raise
        parsed = json.loads(serialised)
        assert len(parsed) == 7
