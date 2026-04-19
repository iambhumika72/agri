"""
tests/test_vision_model.py
==========================
Pytest suite for AgriSense vision pipeline and pest retrieval.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from models.pest_retriever import PestRetriever
from models.schemas import VisionAnalysis, PestCase
from models.vision_model import VisionModel
from nodes.vision_node import vision_node
from preprocessing.schemas import FeatureVector, ChangeResult
from state import AgriState

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_env():
    os.environ["GEMINI_API_KEY"] = "fake_key_for_testing"
    yield
    if "GEMINI_API_KEY" in os.environ:
        del os.environ["GEMINI_API_KEY"]

@pytest.fixture
def mock_feature_vector():
    return FeatureVector(
        farm_id="TEST_FARM",
        feature_timestamp=datetime.utcnow(),
        feature_version="1.0",
        ndvi_stress_flag=0,
        ndvi_trend=0.0,
        ndvi_anomaly_score=0.0,
        vegetation_zone="High",
        ndwi_water_stress=0,
        spatial_heterogeneity=0.1,
        soil_moisture_7d_avg=25.0,
        soil_moisture_trend=0.0,
        soil_moisture_deficit=0.0,
        temperature_stress_days=0,
        heat_accumulation_gdd=1200.0,
        rainfall_7d_total=10.0,
        drought_index=0.0,
        humidity_avg_7d=60.0,
        rain_probability_7d=0.2,
        heat_risk_7d=0,
        irrigation_need_score=0.1,
        optimal_irrigation_days=[1],
        evapotranspiration_est=4.5,
        frost_risk_7d=0,
        days_since_planting=60,
        crop_growth_stage="flowering",
        yield_trend=0.0,
        avg_historical_yield=3000.0,
        yield_volatility=0.0,
        pest_risk_score=0.2,
        days_since_last_irrigation=5,
        irrigation_frequency=0.4,
        season_encoded=1
    )

@pytest.fixture
def mock_change_result():
    return ChangeResult(
        severity="moderate",
        alert_zone_pct=15.0,
        delta_array=np.zeros((300, 300)),
        alert_mask=np.zeros((300, 300), dtype=bool),
        geojson_path=""
    )

@pytest.fixture
def dummy_image(tmp_path):
    img_path = tmp_path / "test_image.png"
    img = Image.new("RGB", (300, 300), color="red")
    img.save(img_path)
    return str(img_path)

# ---------------------------------------------------------------------------
# VisionModel Tests
# ---------------------------------------------------------------------------

class TestVisionModel:
    
    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_encode_image(self, mock_model, mock_cfg, dummy_image):
        vm = VisionModel()
        b64 = vm.encode_image(dummy_image)
        assert isinstance(b64, str)
        assert len(b64) > 0
        
        with pytest.raises(FileNotFoundError):
            vm.encode_image("non_existent.png")

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_prepare_multimodal_payload(self, mock_model, mock_cfg, dummy_image, mock_feature_vector, mock_change_result):
        vm = VisionModel()
        payload = vm.prepare_multimodal_payload(dummy_image, mock_feature_vector, {"mean": 0.5, "std": 0.1}, mock_change_result)
        
        assert "image_base64" in payload
        assert "context" in payload
        assert "prompt" in payload
        assert "TEST_FARM" in payload["context"]
        assert "flowering" in payload["context"]

    @patch("google.generativeai.GenerativeModel.generate_content")
    @patch("google.generativeai.configure")
    def test_analyze_success(self, mock_cfg, mock_gen, dummy_image, mock_feature_vector, mock_change_result):
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "health_score": 85,
            "crop_health_status": "good",
            "pest_detected": True,
            "pest_type": "aphids",
            "pest_confidence": 0.9,
            "affected_area_pct": 12.5,
            "growth_stage_visual": "flowering",
            "stress_pattern": "patchy",
            "urgency_level": "within_week",
            "visual_evidence": "Yellowing clusters on leaf undersides.",
            "recommended_action": "Apply neem oil spray."
        })
        mock_gen.return_value = mock_response
        
        vm = VisionModel()
        analysis = vm.analyze(dummy_image, mock_feature_vector, {"mean": 0.5, "std": 0.1}, mock_change_result)
        
        assert isinstance(analysis, VisionAnalysis)
        assert analysis.health_score == 85
        assert analysis.pest_detected is True
        assert analysis.pest_type == "aphids"

    @patch("google.generativeai.GenerativeModel.generate_content")
    @patch("google.generativeai.configure")
    def test_analyze_retry_logic(self, mock_cfg, mock_gen, dummy_image, mock_feature_vector, mock_change_result):
        # First call returns junk, second returns valid JSON
        bad_response = MagicMock()
        bad_response.text = "NOT JSON"
        
        good_response = MagicMock()
        good_response.text = json.dumps({"health_score": 70, "pest_detected": False})
        
        mock_gen.side_effect = [bad_response, good_response]
        
        vm = VisionModel()
        analysis = vm.analyze(dummy_image, mock_feature_vector, {"mean": 0.5, "std": 0.1}, mock_change_result)
        
        assert analysis.health_score == 70
        assert mock_gen.call_count == 2

    @patch("google.generativeai.GenerativeModel.generate_content")
    @patch("google.generativeai.configure")
    def test_analyze_fallback(self, mock_cfg, mock_gen, dummy_image, mock_feature_vector, mock_change_result):
        # Both calls fail
        bad_response = MagicMock()
        bad_response.text = "STILL NOT JSON"
        mock_gen.return_value = bad_response
        
        vm = VisionModel()
        analysis = vm.analyze(dummy_image, mock_feature_vector, {"mean": 0.5, "std": 0.1}, mock_change_result)
        
        assert analysis.health_score == 0
        assert analysis.pest_detected is False

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_detect_with_patch_analysis(self, mock_model, mock_cfg, dummy_image, mock_feature_vector):
        vm = VisionModel()
        # Mock analyze to avoid API calls
        vm.analyze = MagicMock(return_value=MagicMock())
        
        ndvi_array = np.random.rand(300, 300)
        # Create mask with one high-alert patch in center (1,1)
        alert_mask = np.zeros((300, 300))
        alert_mask[100:200, 100:200] = 1.0 
        
        patches = vm.detect_with_patch_analysis(ndvi_array, alert_mask, dummy_image, mock_feature_vector)
        
        assert len(patches) == 1
        assert patches[0].patch_row == 1
        assert patches[0].patch_col == 1
        assert "patch_1_1" in patches[0].patch_image_path

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_compute_field_health_map(self, mock_model, mock_cfg):
        vm = VisionModel()
        ndvi_array = np.array([0.7, 0.5, 0.3, 0.1]).reshape(2, 2)
        analysis = MagicMock(spec=VisionAnalysis)
        analysis.farm_id = "TEST"
        analysis.pest_detected = False
        
        health_map = vm.compute_field_health_map(ndvi_array, analysis)
        
        assert health_map.shape == (2, 2)
        assert health_map[0, 0] == 3 # 0.7 > 0.6
        assert health_map[1, 1] == 0 # 0.1 < 0.2

# ---------------------------------------------------------------------------
# PestRetriever Tests
# ---------------------------------------------------------------------------

class TestPestRetriever:
    
    def test_build_and_load_index(self, tmp_path):
        db_path = "configs/pest_knowledge.json"
        index_path = str(tmp_path / "test.index")
        
        retriever = PestRetriever(pest_db_path=db_path, index_path=index_path)
        assert os.path.exists(index_path)
        assert retriever.index.ntotal > 0

    def test_retrieve_similar_cases(self):
        retriever = PestRetriever()
        cases = retriever.retrieve_similar_cases("aphids", "wheat", "vegetative", k=2)
        
        assert len(cases) == 2
        assert isinstance(cases[0], PestCase)
        assert any(c.pest_name == "aphids" for c in cases)

    def test_get_treatment_urgency(self):
        retriever = PestRetriever()
        case = PestCase(
            pest_name="armyworm", symptoms="skel", affected_crops=[],
            organic_treatment="org", chemical_treatment="chem",
            severity_level="critical", treatment_window_days=3, source="db"
        )
        
        plan = retriever.get_treatment_urgency(case, 60.0, "immediate")
        
        assert plan.act_within_hours == 24
        assert plan.priority_score > 5.0 # 4 * 1.6 * 2.0 = 12.8
        assert plan.organic_first is False

# ---------------------------------------------------------------------------
# Node Integration Test
# ---------------------------------------------------------------------------

@patch("models.vision_model.VisionModel.analyze")
@patch("google.generativeai.configure")
def test_vision_node_integration(mock_cfg, mock_analyze, dummy_image, mock_feature_vector, mock_change_result):
    mock_analyze.return_value = VisionAnalysis(
        farm_id="F1", image_path=dummy_image, health_score=80,
        crop_health_status="good", pest_detected=True, pest_type="aphids",
        pest_confidence=0.9, affected_area_pct=10.0, growth_stage_visual="flowering",
        stress_pattern="patchy", urgency_level="within_week", visual_evidence="ev",
        recommended_action="act"
    )
    
    state = AgriState(farm_id="F1")
    state.satellite = {
        "false_color_png_path": dummy_image,
        "ndvi_array": np.random.rand(100, 100),
        "ndvi_mean": 0.45
    }
    state.feature_vector = mock_feature_vector
    state.change_result = ChangeResult(
        severity="moderate",
        alert_zone_pct=10.0,
        delta_array=np.zeros((100, 100)),
        alert_mask=np.zeros((100, 100), dtype=bool),
        geojson_path=""
    )
    
    new_state = vision_node(state)
    
    assert new_state.vision_analysis is not None
    assert new_state.vision_analysis.pest_type == "aphids"
    assert len(new_state.pest_cases) > 0
    assert new_state.treatment_plan is not None
    assert new_state.treatment_plan.priority_score > 0

if __name__ == "__main__":
    pytest.main([__file__])
