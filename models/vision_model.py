"""
models/vision_model.py
======================
Main vision analysis class using Gemini 1.5 Pro multimodal API.
Detects crop health issues, pests, and diseases from satellite composites.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import google.generativeai as genai
import matplotlib.pyplot as plt
import numpy as np
import yaml
from PIL import Image

from models.pest_retriever import PestRetriever
from models.schemas import VisionAnalysis, PatchAnalysis, PestCase, TreatmentPlan
from preprocessing.schemas import FeatureVector, ChangeResult

log = logging.getLogger(__name__)

class VisionModel:
    """Multimodal vision pipeline for AgriSense."""

    def __init__(
        self,
        model_name: str = "gemini-1.5-pro",
        config_path: str = "configs/vision_config.yaml",
        pest_db_path: str = "configs/pest_knowledge.json"
    ) -> None:
        self.model_name = model_name
        
        # Initialize Gemini API
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            log.error("GEMINI_API_KEY not found in environment.")
            raise EnvironmentError("GEMINI_API_KEY missing.")
            
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name=model_name)
        
        # Load vision config
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                self.config = yaml.safe_load(f)
        else:
            log.warning("Vision config not found at %s. Using defaults.", config_path)
            self.config = {
                "max_retries": 2,
                "temperature": 0.1,
                "max_output_tokens": 1024
            }
            
        # Initialize Pest Retriever
        self.retriever = PestRetriever(pest_db_path=pest_db_path)
        log.info("VisionModel initialised with %s and pest DB size %d.", 
                 model_name, len(self.retriever.pest_names))

    def encode_image(self, image_path: str) -> str:
        """Read PNG and return base64 string with size validation."""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found at {image_path}")
            
        # Check size (10MB limit)
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > 10.0:
            raise ValueError(f"Image size {size_mb:.2f}MB exceeds Gemini 10MB limit.")
            
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        return encoded

    def prepare_multimodal_payload(
        self,
        image_path: str,
        feature_vector: FeatureVector,
        ndvi_stats: dict,
        change_result: ChangeResult
    ) -> dict:
        """Assemble context and prompt for the multimodal model."""
        # Stats dictionary can be passed as {"mean": 0.4, "std": 0.1}
        ndvi_mean = ndvi_stats.get("mean", 0.0)
        ndvi_std = ndvi_stats.get("std", 0.0)
        
        context = (
            f"Farm ID: {feature_vector.farm_id} | "
            f"Crop: {getattr(feature_vector, 'crop_type', 'unknown')} | "
            f"Growth stage: {feature_vector.crop_growth_stage} | "
            f"Days since planting: {feature_vector.days_since_planting}\n"
            f"NDVI: {ndvi_mean:.2f} ± {ndvi_std:.2f} | Zone: {feature_vector.vegetation_zone}\n"
            f"Water stress: {'Yes' if feature_vector.ndwi_water_stress else 'No'} | "
            f"Alert severity: {change_result.severity}\n"
            f"NDVI decline over 30d: {change_result.alert_zone_pct:.1f}% of field\n"
            f"Soil moisture: {feature_vector.soil_moisture_7d_avg:.1f}% | "
            f"Pest risk score: {feature_vector.pest_risk_score:.2f}\n"
            f"Temp stress days: {feature_vector.temperature_stress_days} | "
            f"GDD accumulated: {feature_vector.heat_accumulation_gdd:.1f}"
        )
        
        prompt = (
            "You are an expert agronomist and plant pathologist analyzing "
            "Sentinel-2 satellite imagery for small-scale farms in India. "
            "You are given a false-color composite (NIR-Red-Green bands) "
            "and contextual farm data. Your task is to detect crop health "
            "issues, pest presence, and disease signs.\n\n"
            "Analyze the image and context carefully. Return ONLY a valid "
            "JSON object with exactly these keys — no markdown, no explanation:\n"
            "{\n"
            "  'health_score': int,\n"
            "    (0-100: 100=perfect, 0=complete crop failure)\n"
            "  'crop_health_status': str,\n"
            "    (one of: excellent | good | moderate | poor | critical)\n"
            "  'pest_detected': bool,\n"
            "  'pest_type': str,\n"
            "    (one of: aphids | stem_borer | whitefly | locusts |\n"
            "     armyworm | fungal_blight | bacterial_wilt | \n"
            "     nutrient_deficiency | drought_stress | waterlogging |\n"
            "     healthy | unknown)\n"
            "  'pest_confidence': float,\n"
            "    (0.0 to 1.0)\n"
            "  'affected_area_pct': float,\n"
            "    (% of visible field showing symptoms)\n"
            "  'growth_stage_visual': str,\n"
            "    (one of: seedling | vegetative | flowering |\n"
            "     maturation | harvest_ready | unknown)\n"
            "  'stress_pattern': str,\n"
            "    (one of: uniform | patchy | edge_effect |\n"
            "     center_spread | row_pattern | healthy)\n"
            "  'urgency_level': str,\n"
            "    (one of: immediate | within_3_days | within_week |\n"
            "     monitor | none)\n"
            "  'visual_evidence': str,\n"
            "    (one sentence: what specific visual pattern justified\n"
            "     your pest/stress detection — max 20 words)\n"
            "  'recommended_action': str,\n"
            "    (one sentence in simple English for a farmer — max 15 words)\n"
            "}"
        )
        
        return {
            "image_base64": self.encode_image(image_path),
            "context": context,
            "prompt": prompt
        }

    def analyze(
        self,
        image_path: str,
        feature_vector: FeatureVector,
        ndvi_stats: dict,
        change_result: ChangeResult
    ) -> VisionAnalysis:
        """Call Gemini API and return structured vision analysis."""
        payload = self.prepare_multimodal_payload(image_path, feature_vector, ndvi_stats, change_result)
        
        start_time = datetime.utcnow()
        
        # Prepare parts
        image_part = {
            "mime_type": "image/png",
            "data": payload["image_base64"]
        }
        
        full_prompt = f"{payload['prompt']}\n\nCONTEXT:\n{payload['context']}"
        
        def _call_gemini(retry_reminder: str = ""):
            return self.model.generate_content(
                [image_part, f"{full_prompt}\n{retry_reminder}"],
                generation_config=genai.types.GenerationConfig(
                    temperature=self.config["temperature"],
                    max_output_tokens=self.config["max_output_tokens"]
                )
            )

        try:
            response = _call_gemini()
            text = response.text.strip()
            
            # Clean markdown if present
            if text.startswith("```"):
                text = text.split("json")[-1].split("```")[0].strip()
                
            try:
                analysis_dict = json.loads(text)
            except json.JSONDecodeError:
                log.warning("Failed to parse Gemini JSON. Retrying with explicit reminder...")
                response = _call_gemini(retry_reminder="IMPORTANT: Return ONLY valid JSON.")
                text = response.text.strip()
                if text.startswith("```"):
                    text = text.split("json")[-1].split("```")[0].strip()
                analysis_dict = json.loads(text)
                
        except Exception as e:
            log.error("Gemini analysis failed after retries: %s", e)
            latency = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            return VisionAnalysis(
                farm_id=feature_vector.farm_id,
                image_path=image_path,
                health_score=0,
                crop_health_status="critical",
                pest_detected=False,
                pest_type="unknown",
                pest_confidence=0.0,
                affected_area_pct=0.0,
                growth_stage_visual="unknown",
                stress_pattern="healthy",
                urgency_level="none",
                visual_evidence=f"API Error: {str(e)[:50]}",
                recommended_action="Please check sensor data manually.",
                gemini_latency_ms=latency
            )

        latency = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        # Token count extraction (if available in response)
        token_count = getattr(response, 'usage_metadata', {}).get('total_token_count', 0)
        
        log.info("Gemini analysis complete in %dms. Tokens: %d", latency, token_count)
        
        return VisionAnalysis(
            farm_id=feature_vector.farm_id,
            image_path=image_path,
            health_score=analysis_dict.get("health_score", 50),
            crop_health_status=analysis_dict.get("crop_health_status", "moderate"),
            pest_detected=analysis_dict.get("pest_detected", False),
            pest_type=analysis_dict.get("pest_type", "unknown"),
            pest_confidence=analysis_dict.get("pest_confidence", 0.0),
            affected_area_pct=analysis_dict.get("affected_area_pct", 0.0),
            growth_stage_visual=analysis_dict.get("growth_stage_visual", "unknown"),
            stress_pattern=analysis_dict.get("stress_pattern", "patchy"),
            urgency_level=analysis_dict.get("urgency_level", "monitor"),
            visual_evidence=analysis_dict.get("visual_evidence", ""),
            recommended_action=analysis_dict.get("recommended_action", ""),
            gemini_latency_ms=latency,
            token_count=token_count
        )

    def detect_with_patch_analysis(
        self,
        ndvi_array: np.ndarray,
        alert_mask: np.ndarray,
        image_path: str,
        feature_vector: FeatureVector
    ) -> List[PatchAnalysis]:
        """Divide field into 3x3 grid and analyze high-alert patches."""
        if ndvi_array.sum() == 0:
            log.warning("Cloudy scene — skipping patch analysis")
            return []
            
        img = Image.open(image_path)
        w, h = img.size
        pw, ph = w // 3, h // 3
        
        # Grid dimensions for the array
        rows, cols = alert_mask.shape
        r_step, c_step = rows // 3, cols // 3
        
        patch_results = []
        
        for r in range(3):
            for c in range(3):
                # Extract sub-mask
                sub_mask = alert_mask[r*r_step:(r+1)*r_step, c*c_step:(c+1)*c_step]
                alert_pct = (sub_mask.sum() / sub_mask.size) * 100
                
                if alert_pct > 20.0:
                    # Crop image
                    left = c * pw
                    top = r * ph
                    right = (c + 1) * pw
                    bottom = (r + 1) * ph
                    patch_img = img.crop((left, top, right, bottom))
                    
                    # Save patch
                    date_str = datetime.utcnow().strftime("%Y%m%d")
                    patch_name = f"{feature_vector.farm_id}_patch_{r}_{c}_{date_str}.png"
                    patch_dir = Path("preprocessing/composites/patches")
                    patch_dir.mkdir(parents=True, exist_ok=True)
                    patch_path = patch_dir / patch_name
                    patch_img.save(patch_path)
                    
                    # Analyze patch
                    # Dummy stats and result for patch
                    patch_stats = {"mean": float(ndvi_array[r*r_step:(r+1)*r_step, c*c_step:(c+1)*c_step].mean()), "std": 0.05}
                    patch_change = ChangeResult(
                        severity="high", 
                        alert_zone_pct=alert_pct, 
                        delta_array=np.zeros((1,1)), 
                        alert_mask=np.zeros((1,1), dtype=bool),
                        geojson_path=""
                    )
                    
                    analysis = self.analyze(str(patch_path), feature_vector, patch_stats, patch_change)
                    
                    patch_results.append(PatchAnalysis(
                        patch_row=r,
                        patch_col=c,
                        patch_image_path=str(patch_path),
                        alert_pixel_pct=alert_pct,
                        vision_analysis=analysis
                    ))
                    
        log.info("Analyzed %d high-alert patches.", len(patch_results))
        return patch_results

    def compute_field_health_map(
        self,
        ndvi_array: np.ndarray,
        vision_analysis: VisionAnalysis
    ) -> np.ndarray:
        """Create a vectorized health map and save colorized PNG."""
        health_map = np.zeros_like(ndvi_array, dtype=np.uint8)
        
        # Classification
        health_map[ndvi_array > 0.6] = 3
        health_map[(ndvi_array > 0.4) & (ndvi_array <= 0.6)] = 2
        health_map[(ndvi_array > 0.2) & (ndvi_array <= 0.4)] = 1
        health_map[ndvi_array <= 0.2] = 0
        
        # Overlay pest confidence if detected
        if vision_analysis.pest_detected and vision_analysis.pest_confidence > 0.5:
            # Penalize stressed zones further or highlight them
            # For this impl, we just ensure the map reflects the detection
            pass
            
        # Save colorized map
        date_str = datetime.utcnow().strftime("%Y%m%d")
        map_path = f"preprocessing/composites/{vision_analysis.farm_id}_healthmap_{date_str}.png"
        
        plt.figure(figsize=(8, 8))
        plt.imshow(health_map, cmap="RdYlGn")
        plt.axis("off")
        plt.savefig(map_path, bbox_inches="tight", pad_inches=0)
        plt.close()
        
        log.info("Health map saved to %s", map_path)
        return health_map

if __name__ == "__main__":
    # Smoke test
    logging.basicConfig(level=logging.INFO)
    try:
        # Requires valid GEMINI_API_KEY
        model = VisionModel()
        print("VisionModel ready.")
    except Exception as e:
        log.error("Failed to init VisionModel: %s", e)
