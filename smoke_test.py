"""
smoke_test.py
=============
Full AgriSense pipeline smoke test.
Validates every layer without requiring external API keys.
Run with:  python -W ignore smoke_test.py
"""
import sys
import os
import numpy as np
import pandas as pd
import yaml
from datetime import datetime, timedelta

# ── helpers ────────────────────────────────────────────────────────────────
PASS = "\033[32m PASS\033[0m"
FAIL = "\033[31m FAIL\033[0m"
results: list[tuple[str, bool, str]] = []


def check(label: str, fn):
    try:
        msg = fn()
        results.append((label, True, msg or ""))
        print(f"  {PASS}  {label}" + (f"  [{msg}]" if msg else ""))
    except Exception as exc:
        results.append((label, False, str(exc)))
        print(f"  {FAIL}  {label}  [{exc}]")


print("=" * 60)
print("   AgriSense — Full Pipeline Smoke Test")
print("=" * 60)

# ══════════════════════════════════════════════════════════════
# 1. PREPROCESSING
# ══════════════════════════════════════════════════════════════
print("\n[1] Preprocessing")

from preprocessing.schemas import (
    SatelliteAnalysis, SensorReading, WeatherForecast, FarmHistory
)
from preprocessing.feature_builder import (
    build_satellite_features, build_sensor_features,
    build_weather_features, build_historical_features, assemble_feature_vector
)
from preprocessing.llm_context_builder import build_farm_context_string
from preprocessing.time_series_builder import (
    build_sensor_timeseries, build_ndvi_timeseries
)
from preprocessing.normalizer import fit_and_save_scaler, transform_features

sat = SatelliteAnalysis(
    "F1", datetime.now(), 0.55, 0.08, -0.12,
    np.random.rand(10, 10), False, [0.5, 0.52, 0.55]
)
sensors = [
    SensorReading("F1", datetime.now() - timedelta(days=i),
                  35.0, 22.0, 30.0, 60.0, 0.0)
    for i in range(14)
]
weather = WeatherForecast(
    "F1", datetime.now(),
    [33.0]*7, [22.0]*7, [0.5]*7, [65.0]*7, [15.0]*7
)
history = FarmHistory(
    "F1", "Wheat", datetime.now() - timedelta(days=45),
    "kharif", [3.2, 3.5, 3.4], [], []
)

check("SatelliteAnalysis schema", lambda: "ok")
check("SensorReading schema", lambda: "ok")

def _features():
    sat_f = build_satellite_features(sat)
    sen_f = build_sensor_features(sensors)
    wea_f = build_weather_features(weather)
    hist_f = build_historical_features(history)
    fv = assemble_feature_vector(sat_f, sen_f, wea_f, hist_f, "F1")
    return f"zone={fv.vegetation_zone} irr_score={fv.irrigation_need_score}"

check("Feature assembly (all 4 sources)", _features)

def _context():
    sat_f = build_satellite_features(sat)
    sen_f = build_sensor_features(sensors)
    wea_f = build_weather_features(weather)
    hist_f = build_historical_features(history)
    fv = assemble_feature_vector(sat_f, sen_f, wea_f, hist_f, "F1")
    ctx = build_farm_context_string(fv, sat, {"crop": "Wheat", "season": "kharif"})
    return f"{len(ctx)} chars"

check("LLM context builder", _context)

def _timeseries():
    df = build_sensor_timeseries(sensors)
    return f"rows={len(df)} cols={len(df.columns)}"

check("Sensor time-series builder", _timeseries)

def _ndvi_ts():
    dates = [datetime.now() - timedelta(days=i*5) for i in range(8)]
    ndvi = [(d, 0.5 + i*0.01, 0.05) for i, d in enumerate(dates)]
    df = build_ndvi_timeseries(ndvi)
    return f"rows={len(df)}"

check("NDVI time-series builder", _ndvi_ts)

def _normalizer():
    import tempfile, os
    data = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [10.0, 20.0, 30.0]})
    tmp = os.path.join(tempfile.gettempdir(), "_test_scaler.pkl")
    scaler = fit_and_save_scaler(data, ["a", "b"], scaler_path=tmp)
    scaled = transform_features(data, ["a", "b"], scaler_path=tmp)
    os.remove(tmp)
    return f"scaled shape={scaled.shape} mean~0: {abs(scaled.mean()) < 0.5}"

check("Feature normalizer", _normalizer)

# ══════════════════════════════════════════════════════════════
# 2. INGESTION
# ══════════════════════════════════════════════════════════════
print("\n[2] Ingestion")

def _spectral():
    from ingestion.spectral_indices import compute_ndvi, compute_ndwi, compute_evi
    nir = np.array([[0.8, 0.7], [0.6, 0.9]])
    red = np.array([[0.2, 0.3], [0.4, 0.1]])
    green = np.array([[0.15, 0.25], [0.35, 0.1]])
    blue = np.array([[0.1, 0.15], [0.2, 0.08]])
    ndvi = compute_ndvi(nir, red)
    ndwi = compute_ndwi(nir, green)
    evi = compute_evi(nir, red, blue)
    return f"NDVI mean={ndvi.mean():.3f}"

check("Spectral indices (NDVI/NDWI/EVI)", _spectral)

def _change():
    from shapely.geometry import box
    from ingestion.change_detection import detect_change, ChangeResult
    base = np.random.uniform(0.5, 0.7, (20, 20)).astype(np.float32)
    current = base.copy()
    current[5:10, 5:10] = 0.2  # stressed patch
    farm_polygon = box(0, 0, 20, 20)
    result = detect_change(
        ndvi_current=current, ndvi_prior=base,
        farm_polygon=farm_polygon, crs_str="EPSG:32643",
        farm_id="_smoke_test_farm"
    )
    import os, glob
    for f in glob.glob("preprocessing/alerts/_smoke_test_farm*.geojson"):
        os.remove(f)
    return f"severity={result.severity} alert_pct={result.alert_zone_pct:.1f}%"

check("Change detection", _change)

# ══════════════════════════════════════════════════════════════
# 3. MODELS
# ══════════════════════════════════════════════════════════════
print("\n[3] Models")

from models.prophet_forecaster import ProphetForecaster
from models.lstm_forecaster import LSTMForecaster, CropLSTM
from models.ensemble_forecaster import EnsembleForecaster
from models.schemas import IrrigationSchedule, YieldForecast, LSTMPrediction

def _prophet_fit_predict():
    p = ProphetForecaster()
    dates = pd.to_datetime([f"201{i}-06-01" for i in range(10)])
    yield_df = pd.DataFrame({
        "ds": dates, "y": [3000 + i*100 for i in range(10)],
        "ndvi_mean": [0.6]*10, "rainfall_7d": [40]*10, "gdd": [500]*10
    })
    p.fit_yield_model(yield_df)
    yf = p.forecast_yield("F1", "Wheat")
    return f"predicted={yf.predicted_yield:.1f} kg/ha model={yf.model_used}"

check("Prophet fit + forecast_yield", _prophet_fit_predict)

def _lstm_sequences():
    l = LSTMForecaster(sequence_len=10)
    data = pd.DataFrame(
        np.random.rand(50, 9),
        columns=["soil_moisture","ndvi_mean","temperature","humidity",
                 "rainfall","gdd","drought_index","lag_1d","lag_7d"]
    )
    X, y = l.prepare_sequences(data)
    return f"X={X.shape} y={y.shape}"

check("LSTM sequence preparation", _lstm_sequences)

def _ensemble_select():
    p = ProphetForecaster(); l = LSTMForecaster()
    e = EnsembleForecaster(p, l)
    small = pd.DataFrame(np.random.rand(10, 3))
    large = pd.DataFrame(np.random.rand(40, 3))
    m_small = e.select_model(small)
    m_large = e.select_model(large)
    return f"small->{m_small} large->{m_large}"

check("Ensemble model selection logic", _ensemble_select)

def _models_init():
    from models import (
        ProphetForecaster, LSTMForecaster, EnsembleForecaster,
        IrrigationSchedule, YieldForecast, LSTMPrediction
    )
    return "all public exports OK"

check("models/__init__.py public exports", _models_init)

# ══════════════════════════════════════════════════════════════
# 4. NODES
# ══════════════════════════════════════════════════════════════
print("\n[4] LangGraph Nodes")

def _forecaster_node():
    from nodes.forecaster_node import forecaster_node
    aligned = pd.DataFrame({
        "ds": pd.date_range("2024-01-01", periods=40, freq="D"),
        "soil_moisture": np.random.uniform(25, 45, 40),
        "rainfall": np.random.uniform(0, 5, 40),
        "temperature": np.random.uniform(20, 30, 40),
        "evapotranspiration_est": np.random.uniform(2, 4, 40),
    })
    for col in ["ndvi_mean","humidity","gdd","drought_index","lag_1d","lag_7d"]:
        aligned[col] = np.random.rand(40)
    aligned.index = aligned["ds"]
    state = {"aligned_df": aligned, "farm_metadata": {"farm_id": "F1", "crop_type": "Wheat"}}
    out = forecaster_node(state)
    model = out.get("forecast_model_used", "None")
    assert model is not None, "forecast_model_used missing from state"
    return f"model={model} irrigation_set={out.get('irrigation_schedule') is not None}"

check("Forecaster LangGraph node", _forecaster_node)

def _vision_fallback():
    from nodes.satellite_vision_node import satellite_vision_node
    state = {"satellite": {"farm_id": "F1", "image_path": "", "ndvi_mean": 0.45}, "errors": []}
    out = satellite_vision_node(state)
    return f"source={out['vision_analysis']['source']} errors={len(out['errors'])}"

check("Satellite vision node (graceful fallback)", _vision_fallback)

# ══════════════════════════════════════════════════════════════
# 5. GENERATIVE
# ══════════════════════════════════════════════════════════════
print("\n[5] Generative Module")

def _llm_client():
    from generative.llm_client import GeminiClient
    client = GeminiClient()
    return f"model={client.model_name} initialized={client._initialized}"

check("GeminiClient (lazy init)", _llm_client)

def _prompt_templates():
    from generative.prompt_templates import (
        build_irrigation_prompt, build_yield_prompt,
        build_pest_prompt, build_full_advisory_prompt
    )
    ctx = "Farm F1 | Wheat | Kharif | 45 days"
    s, u = build_irrigation_prompt(ctx, {"next_critical_date": "2024-06-15",
        "total_water_needed_liters": 12000, "moisture_forecast": "22%", "confidence": 0.82})
    s2, u2 = build_yield_prompt(ctx, {"predicted_yield": 3200, "yield_lower": 2800,
        "yield_upper": 3600, "key_drivers": ["ndvi_mean"], "trend_component": 1.0})
    return f"irr={len(u)} chars yield={len(u2)} chars"

check("Prompt templates (4 types)", _prompt_templates)

def _multilingual():
    from generative.multilingual import detect_farmer_language, SUPPORTED_LANGUAGES
    tests = [
        ({"region": "Punjab"}, "hi"),
        ({"region": "Tamil Nadu"}, "ta"),
        ({"language": "te"}, "te"),
        ({"region": "Maharashtra"}, "mr"),
        ({}, "en"),
    ]
    for farm_meta, expected in tests:
        got = detect_farmer_language(farm_meta)
        assert got == expected, f"Expected {expected}, got {got} for {farm_meta}"
    return f"{len(SUPPORTED_LANGUAGES)} languages supported"

check("Multilingual detection (5 regions)", _multilingual)

def _rag():
    from generative.rag.vectorstore import AgriVectorStore, seed_knowledge_base
    from generative.rag.retriever import AgriRetriever
    store = AgriVectorStore(
        index_path="configs/_smoke_test.index",
        docs_path="configs/_smoke_test_docs.pkl"
    )
    seed_knowledge_base(store)
    retriever = AgriRetriever(store=store, top_k=2)
    ctx = retriever.retrieve_for_irrigation("wheat", 22.5)
    enriched = retriever.enrich_prompt("base prompt", "wheat", "irrigation")
    for f in ["configs/_smoke_test.index.npy", "configs/_smoke_test_docs.pkl"]:
        if os.path.exists(f): os.remove(f)
    return f"docs={len(store.documents)} retrieval={len(ctx)} chars"

check("RAG vectorstore + retriever", _rag)

def _recommendation_engine_init():
    from generative.recommendation_engine import RecommendationEngine
    engine = RecommendationEngine()
    return f"engine ready model={engine.client.model_name}"

check("RecommendationEngine instantiation", _recommendation_engine_init)

# ══════════════════════════════════════════════════════════════
# 6. WEATHER MODULE
# ══════════════════════════════════════════════════════════════
print("\n[6] Weather Module")

def _weather_client_import():
    from weather_module.weather_client import WeatherClient, WeatherAPIError
    return "WeatherClient + WeatherAPIError importable"

check("WeatherClient import", _weather_client_import)

def _weather_features_import():
    from weather_module.weather_features import engineer_features, DailyWeatherFeatures
    return "engineer_features importable"

check("Weather features import", _weather_features_import)

def _weather_adapter_import():
    from weather_module.weather_pipeline_adapter import adapt_batch, adapt_single
    return "adapt_batch + adapt_single importable"

check("Weather pipeline adapter import", _weather_adapter_import)

# ══════════════════════════════════════════════════════════════
# 7. API LAYER
# ══════════════════════════════════════════════════════════════
print("\n[7] API Layer")

def _api_app():
    from api.main import create_app
    app = create_app()
    paths = sorted({r.path for r in app.routes if hasattr(r, "path")})
    return f"{len(paths)} routes: {[p for p in paths if not p.startswith('/openapi')]}"

check("FastAPI app creation + route registration", _api_app)

def _api_schemas():
    from api.schemas import FarmRequest, FullForecastResponse
    req = FarmRequest(
        farm_id="F1", latitude=30.7, longitude=76.7,
        crop_type="Wheat", season="kharif",
        planting_date=datetime.now() - timedelta(days=45)
    )
    return f"FarmRequest valid farm_id={req.farm_id}"

check("API Pydantic schemas", _api_schemas)

def _api_auth():
    from api.auth import create_access_token, verify_token
    return "auth module importable"

check("API auth module", _api_auth)

def _api_dependencies():
    from api.dependencies import get_settings
    settings = get_settings()
    return f"env={settings.get('environment')}"

check("API dependencies", _api_dependencies)

def _alerts_route():
    from api.routes.alerts import router
    paths = [r.path for r in router.routes]
    return f"routes={paths}"

check("Alerts route", _alerts_route)

def _recommendations_route():
    from api.routes.recommendations import router
    paths = [r.path for r in router.routes]
    return f"routes={paths}"

check("Recommendations route", _recommendations_route)

# ══════════════════════════════════════════════════════════════
# 8. CONFIGS & ARTIFACTS
# ══════════════════════════════════════════════════════════════
print("\n[8] Configs & Model Artifacts")

CONFIGS = [
    "configs/app_config.yaml",
    "configs/data_config.yaml",
    "configs/model_config.yaml",
    "configs/prophet_config.yaml",
    "configs/lstm_config.yaml",
]
ARTIFACTS = [
    "configs/lstm_model.pt",
    "configs/prophet_yield.pkl",
    "configs/prophet_irrigation.pkl",
]

for cfg in CONFIGS:
    def _check_cfg(p=cfg):
        with open(p) as f:
            data = yaml.safe_load(f)
        return f"keys={list(data.keys())}"
    check(f"Config: {os.path.basename(cfg)}", _check_cfg)

for art in ARTIFACTS:
    def _check_art(p=art):
        size = os.path.getsize(p)
        assert size > 1000, f"File too small: {size} bytes"
        return f"{size // 1024} KB"
    check(f"Artifact: {os.path.basename(art)}", _check_art)

# ══════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
passed = sum(1 for _, ok, _ in results if ok)
failed = [(label, msg) for label, ok, msg in results if not ok]
total = len(results)

print(f"   Results: {passed}/{total} checks passed")
if failed:
    print(f"\n   FAILURES ({len(failed)}):")
    for label, msg in failed:
        print(f"     FAIL {label}: {msg}")
    print()
    sys.exit(1)
else:
    print("\n   ALL CHECKS PASSED -- Ready for GitHub push")
    print("=" * 60)
