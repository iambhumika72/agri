"""
KrishiAI Weather Module
-----------------------
Provides Open-Meteo weather data fetching, feature engineering,
pipeline adaptation, SMS alert formatting, and scheduling.
"""

from .weather_client import WeatherClient, WeatherAPIError
from .weather_features import DailyWeatherFeatures, engineer_features
from .weather_pipeline_adapter import (
    FarmLocation,
    PipelineRecord,
    adapt_batch,
    pipeline_records_as_dicts,
    tag_crop_season,
)
from .weather_sms_formatter import format_sms, format_sms_batch
from .weather_scheduler import build_scheduler, WeatherPipelineJob

__all__ = [
    "WeatherClient",
    "WeatherAPIError",
    "DailyWeatherFeatures",
    "engineer_features",
    "FarmLocation",
    "PipelineRecord",
    "adapt_batch",
    "pipeline_records_as_dicts",
    "tag_crop_season",
    "format_sms",
    "format_sms_batch",
    "build_scheduler",
    "WeatherPipelineJob",
]
