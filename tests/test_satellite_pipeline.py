"""
tests/test_satellite_pipeline.py
==================================
pytest suite for the AgriSense satellite imagery pipeline.

Covers:
  - spectral_indices.py  (pure-numpy; no real GeoTIFF/API calls)
  - change_detection.py  (pure-numpy + shapely)
  - satellite_vision_node.py  (Gemini API mocked)

Run:
    pytest tests/test_satellite_pipeline.py -v --tb=short
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds
from shapely.geometry import box

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_synthetic_geotiff(
    path: Path,
    H: int = 64,
    W: int = 64,
    cloud_frac: float = 0.10,
    healthy: bool = True,
) -> Path:
    """
    Write a 4-band float32 GeoTIFF (B02, B03, B04, B08) with an optional
    cloud-masked region (values set to 0).
    """
    rng = np.random.default_rng(seed=42)

    if healthy:
        blue  = rng.uniform(0.02, 0.08, (H, W)).astype(np.float32)
        green = rng.uniform(0.04, 0.12, (H, W)).astype(np.float32)
        red   = rng.uniform(0.03, 0.10, (H, W)).astype(np.float32)
        nir   = rng.uniform(0.40, 0.70, (H, W)).astype(np.float32)
    else:
        # Stressed vegetation — low NIR, high Red
        blue  = rng.uniform(0.02, 0.05, (H, W)).astype(np.float32)
        green = rng.uniform(0.04, 0.08, (H, W)).astype(np.float32)
        red   = rng.uniform(0.15, 0.30, (H, W)).astype(np.float32)
        nir   = rng.uniform(0.10, 0.25, (H, W)).astype(np.float32)

    # Cloud patch
    n_cloud = int(H * W * cloud_frac)
    flat_idx = rng.choice(H * W, size=n_cloud, replace=False)
    for arr in (blue, green, red, nir):
        flat = arr.flatten()
        flat[flat_idx] = 0.0
        arr[:] = flat.reshape(H, W)

    transform = from_bounds(75.85, 30.90, 75.95, 30.98, W, H)
    with rasterio.open(
        path, "w",
        driver="GTiff", height=H, width=W, count=4,
        dtype="float32", crs="EPSG:4326", transform=transform,
    ) as dst:
        dst.write(blue, 1)
        dst.write(green, 2)
        dst.write(red, 3)
        dst.write(nir, 4)
    return path


# ─────────────────────────────────────────────────────────────────────────────
# spectral_indices tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSpectralIndexMath:
    """Unit tests for the pure index computation functions."""

    def test_ndvi_healthy_vegetation(self):
        from ingestion.spectral_indices import compute_ndvi
        nir = np.array([[0.6, 0.5]], dtype=np.float32)
        red = np.array([[0.1, 0.1]], dtype=np.float32)
        ndvi = compute_ndvi(nir, red)
        assert ndvi.shape == (1, 2)
        assert (ndvi > 0.6).all(), f"Expected healthy NDVI > 0.6, got {ndvi}"

    def test_ndvi_zero_denominator(self):
        from ingestion.spectral_indices import compute_ndvi
        nir = np.zeros((2, 2), dtype=np.float32)
        red = np.zeros((2, 2), dtype=np.float32)
        ndvi = compute_ndvi(nir, red)
        assert (ndvi == 0.0).all(), "Zero-denominator should produce 0.0 (fill)"

    def test_ndwi_water_pixel(self):
        from ingestion.spectral_indices import compute_ndwi
        green = np.array([[0.2]], dtype=np.float32)
        nir   = np.array([[0.05]], dtype=np.float32)
        ndwi  = compute_ndwi(green, nir)
        assert ndwi[0, 0] > 0.0, "Water pixel should yield positive NDWI"

    def test_savi_range(self):
        from ingestion.spectral_indices import compute_savi
        rng = np.random.default_rng(0)
        nir = rng.uniform(0, 1, (50, 50)).astype(np.float32)
        red = rng.uniform(0, 1, (50, 50)).astype(np.float32)
        savi = compute_savi(nir, red)
        # SAVI is bounded by ±1.5 (L=0.5 → multiplier = 1.5)
        assert savi.max() <= 1.51
        assert savi.min() >= -1.51

    def test_evi_shape_preserved(self):
        from ingestion.spectral_indices import compute_evi
        nir  = np.ones((8, 8), dtype=np.float32) * 0.6
        red  = np.ones((8, 8), dtype=np.float32) * 0.1
        blue = np.ones((8, 8), dtype=np.float32) * 0.04
        evi  = compute_evi(nir, red, blue)
        assert evi.shape == (8, 8)


class TestComputeIndices:
    """Integration tests for compute_indices() using synthetic GeoTIFFs."""

    def test_healthy_farm_no_stress_alert(self, tmp_path):
        from ingestion.spectral_indices import compute_indices
        tif = _make_synthetic_geotiff(tmp_path / "healthy.tif", healthy=True)
        result = compute_indices(
            tif,
            farm_id="farm_a",
            acquisition_date="2024-10-01",
            composite_output_dir=tmp_path / "composites",
        )
        assert result.ndvi_mean > 0.30, (
            f"Healthy farm NDVI mean should exceed 0.30, got {result.ndvi_mean}"
        )
        assert result.stress_alert is False

    def test_stressed_farm_triggers_alert(self, tmp_path):
        from ingestion.spectral_indices import compute_indices
        tif = _make_synthetic_geotiff(tmp_path / "stressed.tif", healthy=False)
        result = compute_indices(
            tif,
            farm_id="farm_b",
            acquisition_date="2024-10-01",
            composite_output_dir=tmp_path / "composites",
        )
        assert result.stress_alert is True, (
            f"Stressed farm NDVI={result.ndvi_mean:.3f} should trigger alert"
        )

    def test_pixel_coverage_respects_cloud_mask(self, tmp_path):
        from ingestion.spectral_indices import compute_indices
        tif = _make_synthetic_geotiff(
            tmp_path / "cloudy.tif", cloud_frac=0.25
        )
        result = compute_indices(
            tif,
            farm_id="farm_c",
            acquisition_date="2024-10-02",
            composite_output_dir=tmp_path / "composites",
        )
        # ~25% cloud → coverage should be ~75%, allow ±5%
        assert 65.0 <= result.pixel_coverage_pct <= 90.0, (
            f"pixel_coverage_pct={result.pixel_coverage_pct:.1f}% out of expected range"
        )

    def test_composite_png_written(self, tmp_path):
        from ingestion.spectral_indices import compute_indices
        tif = _make_synthetic_geotiff(tmp_path / "farm.tif")
        composite_dir = tmp_path / "composites"
        result = compute_indices(
            tif,
            farm_id="farm_d",
            acquisition_date="2024-11-01",
            composite_output_dir=composite_dir,
        )
        png = Path(result.composite_png_path)
        assert png.exists(), f"Composite PNG not written: {png}"
        assert png.suffix == ".png"

    def test_missing_geotiff_raises(self):
        from ingestion.spectral_indices import compute_indices
        with pytest.raises(FileNotFoundError):
            compute_indices("/nonexistent/path/farm.tif")

    def test_result_field_types(self, tmp_path):
        from ingestion.spectral_indices import IndexResult, compute_indices
        tif = _make_synthetic_geotiff(tmp_path / "farm_e.tif")
        result = compute_indices(
            tif,
            farm_id="farm_e",
            acquisition_date="2024-10-03",
            composite_output_dir=tmp_path / "composites",
        )
        assert isinstance(result, IndexResult)
        assert isinstance(result.ndvi_array, np.ndarray)
        assert isinstance(result.ndvi_mean, float)
        assert isinstance(result.stress_alert, bool)
        assert isinstance(result.pixel_coverage_pct, float)


# ─────────────────────────────────────────────────────────────────────────────
# change_detection tests
# ─────────────────────────────────────────────────────────────────────────────

class TestChangeDetection:
    """Tests for detect_change() using synthetic NDVI arrays."""

    @pytest.fixture()
    def farm_polygon(self):
        return box(0, 0, 100, 100)

    def test_no_change_yields_low_severity(self, tmp_path, farm_polygon):
        from ingestion.change_detection import detect_change
        ndvi = np.full((100, 100), 0.6, dtype=np.float32)
        result = detect_change(
            ndvi_current=ndvi,
            ndvi_prior=ndvi.copy(),
            farm_polygon=farm_polygon,
            crs_str="EPSG:4326",
            output_dir=tmp_path,
            farm_id="no_change",
            detection_date="2024-10-15",
        )
        assert result.severity == "low"
        assert result.alert_zone_pct < 1.0

    def test_stressed_patch_detected(self, tmp_path, farm_polygon):
        from ingestion.change_detection import detect_change
        ndvi_prior   = np.full((100, 100), 0.65, dtype=np.float32)
        ndvi_current = ndvi_prior.copy()
        # Introduce heavy stress in top-left 40×40 block
        ndvi_current[:40, :40] -= 0.25
        result = detect_change(
            ndvi_current=ndvi_current,
            ndvi_prior=ndvi_prior,
            farm_polygon=farm_polygon,
            crs_str="EPSG:4326",
            output_dir=tmp_path,
            farm_id="stressed_patch",
            detection_date="2024-10-16",
        )
        # 40×40 = 1600 / 10000 = 16% → moderate
        assert result.alert_zone_pct > 10.0
        assert result.severity in ("moderate", "high")

    def test_high_severity_threshold(self, tmp_path, farm_polygon):
        from ingestion.change_detection import detect_change
        ndvi_prior   = np.full((100, 100), 0.70, dtype=np.float32)
        ndvi_current = ndvi_prior - 0.30   # everywhere > 0.15 decline
        result = detect_change(
            ndvi_current=ndvi_current.astype(np.float32),
            ndvi_prior=ndvi_prior,
            farm_polygon=farm_polygon,
            crs_str="EPSG:4326",
            output_dir=tmp_path,
            farm_id="high_stress",
            detection_date="2024-10-17",
        )
        assert result.severity == "high"
        assert result.alert_zone_pct > 30.0

    def test_alert_geojson_is_valid(self, tmp_path, farm_polygon):
        from ingestion.change_detection import detect_change
        ndvi_prior   = np.full((100, 100), 0.65, dtype=np.float32)
        ndvi_current = ndvi_prior.copy()
        ndvi_current[:50, :50] -= 0.30
        result = detect_change(
            ndvi_current=ndvi_current,
            ndvi_prior=ndvi_prior,
            farm_polygon=farm_polygon,
            crs_str="EPSG:4326",
            output_dir=tmp_path,
            farm_id="geojson_test",
            detection_date="2024-10-18",
        )
        gj = result.alert_geojson
        assert gj["type"] == "FeatureCollection"
        assert len(gj["features"]) > 0
        for feat in gj["features"]:
            assert feat["type"] == "Feature"
            assert feat["geometry"]["type"] in (
                "Polygon", "MultiPolygon", "Point", "LineString"
            )

    def test_geojson_file_written(self, tmp_path, farm_polygon):
        from ingestion.change_detection import detect_change
        ndvi_prior   = np.full((100, 100), 0.60, dtype=np.float32)
        ndvi_current = ndvi_prior - 0.20
        result = detect_change(
            ndvi_current=ndvi_current.astype(np.float32),
            ndvi_prior=ndvi_prior,
            farm_polygon=farm_polygon,
            crs_str="EPSG:32643",
            output_dir=tmp_path,
            farm_id="write_test",
            detection_date="2024-10-19",
        )
        geojson_path = Path(result.geojson_path)
        assert geojson_path.exists()
        with open(geojson_path) as fh:
            loaded = json.load(fh)
        assert loaded["type"] == "FeatureCollection"

    def test_shape_mismatch_raises(self, tmp_path, farm_polygon):
        from ingestion.change_detection import detect_change
        with pytest.raises(ValueError, match="shape mismatch"):
            detect_change(
                ndvi_current=np.zeros((10, 10), dtype=np.float32),
                ndvi_prior=np.zeros((20, 20), dtype=np.float32),
                farm_polygon=farm_polygon,
                crs_str="EPSG:4326",
                output_dir=tmp_path,
            )

    def test_delta_array_values_correct(self, tmp_path, farm_polygon):
        from ingestion.change_detection import detect_change
        prior   = np.full((50, 50), 0.7, dtype=np.float32)
        current = np.full((50, 50), 0.4, dtype=np.float32)
        result = detect_change(
            ndvi_current=current,
            ndvi_prior=prior,
            farm_polygon=farm_polygon,
            crs_str="EPSG:4326",
            output_dir=tmp_path,
            farm_id="delta_test",
        )
        expected_delta = 0.3
        assert np.allclose(
            result.delta_array[result.delta_array != 0],
            expected_delta,
            atol=1e-5,
        ), f"Expected delta ≈ {expected_delta}"


# ─────────────────────────────────────────────────────────────────────────────
# satellite_vision_node tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSatelliteVisionNode:
    """
    Tests for the LangGraph node.
    Gemini API and base64 encoding are mocked to avoid real API calls.
    """

    VALID_GEMINI_JSON = json.dumps(
        {
            "health_score": 78,
            "stressed_zone_pct": 12.5,
            "likely_cause": "water_stress",
            "growth_stage": "vegetative",
            "confidence": 0.87,
            "agronomist_note": "Field shows moderate water stress in north quadrant; irrigate within 48h.",
        }
    )

    def _make_png(self, tmp_path: Path) -> str:
        """Write a minimal 2×2 PNG and return its path string."""
        from PIL import Image
        img = Image.fromarray(np.zeros((2, 2, 3), dtype=np.uint8), "RGB")
        png = tmp_path / "composite.png"
        img.save(str(png))
        return str(png)

    def _base_state(self, image_path: str) -> dict:
        return {
            "satellite": {
                "image_path": image_path,
                "ndvi_mean": 0.42,
                "ndvi_std": 0.08,
                "stress_alert": False,
                "farm_id": "farm_test_01",
            },
            "errors": [],
        }

    @patch("google.generativeai.GenerativeModel.generate_content")
    @patch("google.generativeai.configure")
    def test_successful_analysis(self, mock_configure, mock_generate, tmp_path):
        from nodes.satellite_vision_node import satellite_vision_node

        mock_response = MagicMock()
        mock_response.text = self.VALID_GEMINI_JSON
        mock_generate.return_value = mock_response

        import os
        os.environ.setdefault("GEMINI_API_KEY", "test-key")

        png_path = self._make_png(tmp_path)
        state = self._base_state(png_path)
        result = satellite_vision_node(state)

        va = result["vision_analysis"]
        assert va["health_score"] == 78
        assert va["likely_cause"] == "water_stress"
        assert va["growth_stage"] == "vegetative"
        assert va["confidence"] == pytest.approx(0.87, abs=0.001)
        assert result["errors"] == []

    @patch("google.generativeai.GenerativeModel.generate_content")
    @patch("google.generativeai.configure")
    def test_missing_image_path_returns_fallback(self, mock_configure, mock_generate, tmp_path):
        from nodes.satellite_vision_node import satellite_vision_node

        import os
        os.environ.setdefault("GEMINI_API_KEY", "test-key")

        state = {
            "satellite": {
                "image_path": "",
                "ndvi_mean": 0.25,
                "ndvi_std": 0.05,
                "stress_alert": True,
                "farm_id": "farm_no_path",
            },
            "errors": [],
        }
        result = satellite_vision_node(state)
        assert len(result["errors"]) > 0
        assert result["vision_analysis"]["source"] == "fallback"
        # Gemini should never have been called
        mock_generate.assert_not_called()

    @patch("google.generativeai.GenerativeModel.generate_content")
    @patch("google.generativeai.configure")
    def test_invalid_json_response_uses_fallback(self, mock_configure, mock_generate, tmp_path):
        from nodes.satellite_vision_node import satellite_vision_node

        mock_response = MagicMock()
        mock_response.text = "This is definitely not JSON ¯\\_(ツ)_/¯"
        mock_generate.return_value = mock_response

        import os
        os.environ.setdefault("GEMINI_API_KEY", "test-key")

        png_path = self._make_png(tmp_path)
        state = self._base_state(png_path)
        result = satellite_vision_node(state)

        assert result["vision_analysis"]["source"] == "fallback"
        # Node must NOT raise; error is captured in state
        assert len(result["errors"]) == 0   # parse error ≠ node error

    @patch("google.generativeai.GenerativeModel.generate_content")
    @patch("google.generativeai.configure")
    def test_gemini_api_exception_non_fatal(self, mock_configure, mock_generate, tmp_path):
        from nodes.satellite_vision_node import satellite_vision_node

        mock_generate.side_effect = RuntimeError("quota exceeded")

        import os
        os.environ.setdefault("GEMINI_API_KEY", "test-key")

        png_path = self._make_png(tmp_path)
        state = self._base_state(png_path)
        result = satellite_vision_node(state)

        assert len(result["errors"]) > 0
        assert "quota exceeded" in result["errors"][0]
        assert result["vision_analysis"]["source"] == "fallback"

    @patch("google.generativeai.GenerativeModel.generate_content")
    @patch("google.generativeai.configure")
    def test_health_score_clamped(self, mock_configure, mock_generate, tmp_path):
        from nodes.satellite_vision_node import satellite_vision_node

        bad_json = json.dumps(
            {
                "health_score": 999,           # out of range
                "stressed_zone_pct": -5.0,    # out of range
                "likely_cause": "healthy",
                "growth_stage": "vegetative",
                "confidence": 2.5,             # out of range
                "agronomist_note": "Test note.",
            }
        )
        mock_response = MagicMock()
        mock_response.text = bad_json
        mock_generate.return_value = mock_response

        import os
        os.environ.setdefault("GEMINI_API_KEY", "test-key")

        png_path = self._make_png(tmp_path)
        state = self._base_state(png_path)
        result = satellite_vision_node(state)

        va = result["vision_analysis"]
        assert 0 <= va["health_score"] <= 100
        assert 0.0 <= va["stressed_zone_pct"] <= 100.0
        assert 0.0 <= va["confidence"] <= 1.0

    @patch("google.generativeai.GenerativeModel.generate_content")
    @patch("google.generativeai.configure")
    def test_unknown_cause_defaults_to_healthy(self, mock_configure, mock_generate, tmp_path):
        from nodes.satellite_vision_node import satellite_vision_node

        bad_cause_json = json.dumps(
            {
                "health_score": 60,
                "stressed_zone_pct": 5.0,
                "likely_cause": "alien_invasion",   # not a valid cause
                "growth_stage": "vegetative",
                "confidence": 0.55,
                "agronomist_note": "Unknown cause.",
            }
        )
        mock_response = MagicMock()
        mock_response.text = bad_cause_json
        mock_generate.return_value = mock_response

        import os
        os.environ.setdefault("GEMINI_API_KEY", "test-key")

        png_path = self._make_png(tmp_path)
        state = self._base_state(png_path)
        result = satellite_vision_node(state)

        assert result["vision_analysis"]["likely_cause"] == "healthy"

    @patch("google.generativeai.GenerativeModel.generate_content")
    @patch("google.generativeai.configure")
    def test_state_passthrough_preserved(self, mock_configure, mock_generate, tmp_path):
        """Extra state keys must survive the node unchanged."""
        from nodes.satellite_vision_node import satellite_vision_node

        mock_response = MagicMock()
        mock_response.text = self.VALID_GEMINI_JSON
        mock_generate.return_value = mock_response

        import os
        os.environ.setdefault("GEMINI_API_KEY", "test-key")

        png_path = self._make_png(tmp_path)
        state = {
            **self._base_state(png_path),
            "weather": {"temp_c": 32.5},
            "farm_metadata": {"crop": "wheat"},
        }
        result = satellite_vision_node(state)

        assert result["weather"] == {"temp_c": 32.5}
        assert result["farm_metadata"] == {"crop": "wheat"}
