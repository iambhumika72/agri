"""
models/crop_suitability_scorer.py
=================================
Scores crops based on environmental suitability and field capability.
"""

from __future__ import annotations

import logging
from typing import Dict

from preprocessing.schemas import FieldCapabilityProfile

log = logging.getLogger(__name__)

# Ideal requirements for common crops in India
# These are simplified heuristics for demonstration
CROP_REQUIREMENTS = {
    "wheat": {
        "temp_opt": 22, 
        "rain_min": 20, 
        "ph_range": (6.0, 7.5),
        "ideal_ndvi": 0.6
    },
    "rice": {
        "temp_opt": 28, 
        "rain_min": 100, 
        "ph_range": (5.0, 6.5),
        "ideal_ndvi": 0.7
    },
    "maize": {
        "temp_opt": 25, 
        "rain_min": 40, 
        "ph_range": (5.5, 7.5),
        "ideal_ndvi": 0.55
    },
    "cotton": {
        "temp_opt": 30, 
        "rain_min": 30, 
        "ph_range": (6.0, 8.0),
        "ideal_ndvi": 0.5
    },
    "mustard": {
        "temp_opt": 20, 
        "rain_min": 15, 
        "ph_range": (6.0, 7.0),
        "ideal_ndvi": 0.5
    },
}


class CropSuitabilityScorer:
    """Calculates suitability of different crops for a specific field profile."""

    def score_crops(self, profile: FieldCapabilityProfile) -> Dict[str, float]:
        """
        Returns suitability scores [0-1] for all supported crops.
        
        Args:
            profile: The FieldCapabilityProfile for the farm.
            
        Returns:
            Dictionary mapping crop names to suitability scores.
        """
        log.info("Calculating crop suitability scores for farm_id=%s", profile.farm_id)
        results = {}

        for crop, req in CROP_REQUIREMENTS.items():
            # 1. Base score from field capability
            # This accounts for NDVI, Climate, Soil OM, and Pests in a general sense
            base_score = profile.overall_capability_score
            
            # 2. pH match (Crop specific)
            ph_min, ph_max = req["ph_range"]
            if ph_min <= profile.ph_level <= ph_max:
                ph_score = 1.0
            else:
                # Penalty based on distance from range
                dist = min(abs(profile.ph_level - ph_min), abs(profile.ph_level - ph_max))
                ph_score = max(1.0 - (dist / 2.0), 0.3)
            
            # 3. Seasonality check (Simplified)
            # In a production system, we'd check if the current season matches crop types
            
            # 4. Stability Bonus
            # Crops like wheat/rice benefit from field stability
            stability_bonus = 0.1 * profile.ndvi_stability
            
            # 5. Composite Score
            # Weighting factors: 60% General Capability, 30% pH, 10% Stability
            final_score = (0.6 * base_score) + (0.3 * ph_score) + stability_bonus
            
            # Clamp to [0, 1]
            final_score = min(max(final_score, 0.0), 1.0)
            results[crop] = float(final_score)
            
            log.debug("Crop: %s | Score: %.2f (Base: %.2f, pH: %.2f)", crop, final_score, base_score, ph_score)
            
        return results
