"""
tests/test_pest_detection.py
============================
Pytest suite for the new farmer plant photo pest detection feature.
"""

import os
import base64
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.main import app
from models.schemas import VisionAnalysis, get_confidence_label
from vision.plant_photo_preprocessor import PlantPhotoPreprocessor
from models.vision_model import VisionModel

client = TestClient(app)

@pytest.fixture
def sample_image_bytes():
    # Create a simple 500x500 green square image with some noise to increase file size
    img = np.zeros((500, 500, 3), dtype=np.uint8)
    img[100:400, 100:400] = [0, 255, 0] # Green leaf
    img += np.random.randint(0, 50, (500, 500, 3), dtype=np.uint8)
    _, buffer = cv2.imencode(".png", img)
    return buffer.tobytes()

@pytest.fixture
def mock_gemini_response():
    return {
        "pest_identified": True,
        "pest_name": "aphids",
        "common_name": "Aphids",
        "affected_plant_part": "leaf",
        "symptoms_observed": "Small green insects on the underside of leaves.",
        "confidence": 0.92,
        "confidence_reason": "Clear visibility of insect clusters.",
        "severity": "moderate",
        "severity_explanation": "Clusters localized to few leaves.",
        "spread_risk": "medium",
        "organic_treatment": "Neem oil spray (5ml/L)",
        "chemical_treatment": "Imidacloprid 17.8 SL",
        "act_within_days": 3,
        "preventive_measure": "Monitor weekly",
        "photo_quality_sufficient": True,
        "retake_suggestion": ""
    }

# --- Preprocessor Tests ---

def test_load_and_validate_valid(sample_image_bytes):
    preprocessor = PlantPhotoPreprocessor()
    img = preprocessor.load_and_validate(sample_image_bytes, "test.png")
    assert isinstance(img, np.ndarray)
    assert img.shape == (500, 500, 3)

def test_load_and_validate_low_res():
    preprocessor = PlantPhotoPreprocessor()
    img_low = np.zeros((100, 100, 3), dtype=np.uint8)
    img_low += np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8) # Add noise to ensure >1KB
    _, buffer = cv2.imencode(".png", img_low)
    with pytest.raises(ValueError, match="resolution"):
        preprocessor.load_and_validate(buffer.tobytes(), "small.png")

def test_load_and_validate_invalid_format():
    preprocessor = PlantPhotoPreprocessor()
    with pytest.raises(ValueError, match="format"):
        preprocessor.load_and_validate(b"fake data", "test.gif")

def test_load_and_validate_blank():
    preprocessor = PlantPhotoPreprocessor()
    blank = np.ones((300, 300, 3), dtype=np.uint8) * 255
    _, buffer = cv2.imencode(".png", blank)
    with pytest.raises(ValueError, match="blank"):
        preprocessor.load_and_validate(buffer.tobytes(), "blank.png")

def test_detect_lesion_zones_synthetic():
    preprocessor = PlantPhotoPreprocessor()
    img = np.zeros((300, 300, 3), dtype=np.uint8)
    # Add a brown patch (HSV around H=40 in full 360, which is H=20 in OpenCV)
    # BGR for brown: (0, 100, 150) -> R=150, G=100, B=0
    img[100:150, 100:150] = [0, 100, 150] 
    res = preprocessor.detect_lesion_zones(img)
    assert res["brown_yellow_pct"] > 0
    assert res["total_affected_pct"] > 0

def test_detect_leaf_region_synthetic():
    preprocessor = PlantPhotoPreprocessor()
    img = np.ones((500, 500, 3), dtype=np.uint8) * 255 # White background
    img[100:400, 100:400] = [0, 200, 0] # Green square
    cropped, meta = preprocessor.detect_leaf_region(img)
    assert meta["leaf_detected"] is True
    assert cropped.shape[0] < 500

def test_run_full_pipeline_success(sample_image_bytes):
    preprocessor = PlantPhotoPreprocessor()
    path, meta = preprocessor.run_full_pipeline(sample_image_bytes, "test.png", "test_farm")
    assert os.path.exists(path)
    assert meta["leaf_detected"] is True
    assert "lesion_zones" in meta

# --- Vision Model Tests ---

@patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"})
@patch("google.generativeai.GenerativeModel.generate_content")
def test_analyze_farmer_photo_success(mock_gen, mock_gemini_response):
    # Mock response object
    mock_resp = MagicMock()
    mock_resp.text = json.dumps(mock_gemini_response)
    mock_gen.return_value = mock_resp
    
    # Need dummy image on disk
    dummy_path = "test_dummy.png"
    cv2.imwrite(dummy_path, np.zeros((224, 224, 3), dtype=np.uint8))
    
    try:
        model = VisionModel()
        meta = {"lesion_zones": {"total_affected_pct": 5.0}, "dominant_symptom": "spots"}
        res = model.analyze_farmer_photo(dummy_path, meta, {"farm_id": "F1"})
        
        assert isinstance(res, VisionAnalysis)
        assert res.pest_type == "aphids"
        assert res.pest_confidence == 0.92
    finally:
        if os.path.exists(dummy_path): os.remove(dummy_path)

@patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"})
@patch("google.generativeai.GenerativeModel.generate_content")
def test_analyze_farmer_photo_fail(mock_gen):
    mock_gen.side_effect = Exception("Gemini Down")
    
    dummy_path = "test_fail.png"
    cv2.imwrite(dummy_path, np.zeros((224, 224, 3), dtype=np.uint8))
    
    try:
        model = VisionModel()
        res = model.analyze_farmer_photo(dummy_path, {}, {"farm_id": "F1"})
        assert res.health_score == 0
        assert "API Error" in res.visual_evidence
    finally:
        if os.path.exists(dummy_path): os.remove(dummy_path)

# --- Schema / Label Tests ---

def test_get_confidence_label():
    assert get_confidence_label(0.90) == "Very High Confidence"
    assert get_confidence_label(0.25) == "Unable to Identify — Contact Local Agriculture Officer"

# --- API Integration Tests ---

@patch("api.routes.farmer_input.VisionModel")
@patch("api.routes.farmer_input.PlantPhotoPreprocessor")
def test_api_detect_pest_multipart(mock_prep_class, mock_model_class, sample_image_bytes):
    # Setup mocks
    mock_prep = mock_prep_class.return_value
    mock_prep.run_full_pipeline.return_value = ("test.png", {"lesion_zones": {"total_affected_pct": 5.0}, "dominant_symptom": "none"})
    
    mock_model = mock_model_class.return_value
    mock_model.analyze_farmer_photo.return_value = VisionAnalysis(
        farm_id="F1", image_path="test.png", health_score=50, crop_health_status="poor",
        pest_detected=True, pest_type="aphids", pest_confidence=0.9, affected_area_pct=5.0,
        growth_stage_visual="unknown", stress_pattern="patchy", urgency_level="within_3_days",
        visual_evidence="test", recommended_action="test"
    )
    mock_model.retriever.retrieve_similar_cases.return_value = []
    mock_model.retriever.get_treatment_urgency.return_value = MagicMock(priority_score=0.5)

    os.environ["GEMINI_API_KEY"] = "fake_key"
    
    response = client.post(
        "/farmer-input/pest/detect",
        data={"farm_id": "F1"},
        files={"file": ("test.png", sample_image_bytes, "image/png")}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["vision_analysis"]["pest_type"] == "aphids"
    assert "confidence_label" in data

def test_api_detect_pest_invalid_format():
    response = client.post(
        "/farmer-input/pest/detect",
        files={"file": ("test.gif", b"fake gif data", "image/gif")}
    )
    assert response.status_code == 400

def test_api_get_history_not_found():
    response = client.get("/farmer-input/pest/history/NON_EXISTENT")
    assert response.status_code == 404

if __name__ == "__main__":
    pytest.main([__file__])
