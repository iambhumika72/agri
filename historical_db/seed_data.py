"""
historical_db/seed_data.py — Realistic mock data for Indian farming context.

Design notes:
- All UUIDs are generated deterministically via uuid5(NAMESPACE_DNS, seed_string)
  so re-running the seed is idempotent — the same IDs are produced each time.
- Soil parameters are sourced from ICAR typical ranges for each state's dominant
  soil type: Punjab (alluvial), Maharashtra (black/vertisol), UP (alluvial),
  Karnataka (red laterite), Rajasthan (arid sandy).
- Irrigation volumes use standard Indian BIS guidelines per crop per season.
- Pest names and severity patterns reflect NCIPM (National Centre for Integrated
  Pest Management) data for major Kharif/Rabi crops.
"""

from __future__ import annotations

import logging
import os
import random
import uuid
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Deterministic UUID helper (idempotent re-runs)
# ---------------------------------------------------------------------------
_NS = uuid.NAMESPACE_DNS


def _uid(seed: str) -> str:
    return str(uuid.uuid5(_NS, seed))


# ---------------------------------------------------------------------------
# Master data
# ---------------------------------------------------------------------------
FARMS: list[dict[str, Any]] = [
    {
        "farm_id": _uid("farm_punjab_amarinder"),
        "farmer_name": "Amarinder Singh",
        "district": "Ludhiana",
        "state": "Punjab",
        "latitude": 30.9010,
        "longitude": 75.8573,
        "area_hectares": 4.5,
    },
    {
        "farm_id": _uid("farm_maharashtra_sunita"),
        "farmer_name": "Sunita Patil",
        "district": "Nagpur",
        "state": "Maharashtra",
        "latitude": 21.1458,
        "longitude": 79.0882,
        "area_hectares": 3.2,
    },
    {
        "farm_id": _uid("farm_up_ramesh"),
        "farmer_name": "Ramesh Yadav",
        "district": "Agra",
        "state": "Uttar Pradesh",
        "latitude": 27.1767,
        "longitude": 78.0081,
        "area_hectares": 5.0,
    },
    {
        "farm_id": _uid("farm_karnataka_kavitha"),
        "farmer_name": "Kavitha Reddy",
        "district": "Mysuru",
        "state": "Karnataka",
        "latitude": 12.2958,
        "longitude": 76.6394,
        "area_hectares": 2.8,
    },
    {
        "farm_id": _uid("farm_rajasthan_mohan"),
        "farmer_name": "Mohan Lal Sharma",
        "district": "Jodhpur",
        "state": "Rajasthan",
        "latitude": 26.2389,
        "longitude": 73.0243,
        "area_hectares": 6.0,
    },
]

CROPS: list[dict[str, Any]] = [
    {
        "crop_id": _uid("crop_wheat_hd2967"),
        "crop_name": "Wheat",
        "crop_variety": "HD-2967",
        "season_type": "Rabi",
    },
    {
        "crop_id": _uid("crop_rice_pusa44"),
        "crop_name": "Rice",
        "crop_variety": "Pusa-44",
        "season_type": "Kharif",
    },
    {
        "crop_id": _uid("crop_cotton_bt"),
        "crop_name": "Cotton",
        "crop_variety": "Bt-Hybrid",
        "season_type": "Kharif",
    },
]

# Recommended irrigation water per season in litres / hectare
CROP_IRRIGATION_BASELINE_LITERS: dict[str, float] = {
    "Wheat":  450_000,   # ~450 mm
    "Rice":   1_200_000, # ~1200 mm
    "Cotton": 700_000,   # ~700 mm
}

# Yield ranges (kg/ha)
YIELD_RANGES: dict[str, tuple[int, int]] = {
    "Wheat":  (3500, 5000),
    "Rice":   (2000, 4000),
    "Cotton": (1500, 2500),
}

# Pest catalogue per crop
CROP_PESTS: dict[str, list[str]] = {
    "Wheat":  ["aphids", "stem borer", "armyworm"],
    "Rice":   ["stem borer", "armyworm", "whitefly"],
    "Cotton": ["bollworm", "whitefly", "aphids"],
}

# Soil baselines per state (mean ± small jitter added during generation)
SOIL_BASELINES: dict[str, dict[str, float]] = {
    "Punjab": {
        "ph_level": 7.8,
        "nitrogen_ppm": 220.0,
        "phosphorus_ppm": 18.0,
        "potassium_ppm": 195.0,
        "organic_matter_pct": 0.55,
        "moisture_pct": 22.0,
    },
    "Maharashtra": {
        "ph_level": 7.2,
        "nitrogen_ppm": 185.0,
        "phosphorus_ppm": 12.0,
        "potassium_ppm": 280.0,
        "organic_matter_pct": 0.48,
        "moisture_pct": 18.0,
    },
    "Uttar Pradesh": {
        "ph_level": 7.5,
        "nitrogen_ppm": 200.0,
        "phosphorus_ppm": 15.0,
        "potassium_ppm": 210.0,
        "organic_matter_pct": 0.50,
        "moisture_pct": 20.0,
    },
    "Karnataka": {
        "ph_level": 6.4,
        "nitrogen_ppm": 165.0,
        "phosphorus_ppm": 22.0,
        "potassium_ppm": 145.0,
        "organic_matter_pct": 0.72,
        "moisture_pct": 25.0,
    },
    "Rajasthan": {
        "ph_level": 8.1,
        "nitrogen_ppm": 130.0,
        "phosphorus_ppm": 8.0,
        "potassium_ppm": 160.0,
        "organic_matter_pct": 0.28,
        "moisture_pct": 10.0,
    },
}


# ---------------------------------------------------------------------------
# Data generation helpers
# ---------------------------------------------------------------------------
def _jitter(value: float, pct: float = 0.10) -> float:
    """Add ±pct relative jitter (deterministic-ish via seeded random)."""
    delta = value * pct
    return round(value + random.uniform(-delta, delta), 3)


def _generate_yield_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    # Two seasons: Kharif 2023, Rabi 2023-24
    season_configs = [
        {
            "season": "Kharif",
            "year": 2023,
            "crops": ["Rice", "Cotton"],
            "harvest_month": 11,
        },
        {
            "season": "Rabi",
            "year": 2023,
            "crops": ["Wheat"],
            "harvest_month": 4,
            "harvest_year_offset": 1,  # harvested in 2024
        },
    ]
    crop_map = {c["crop_name"]: c for c in CROPS}

    for farm in FARMS:
        for sc in season_configs:
            for crop_name in sc["crops"]:
                crop = crop_map[crop_name]
                lo, hi = YIELD_RANGES[crop_name]
                harvest_year = sc["year"] + sc.get("harvest_year_offset", 0)
                harvest_date = date(harvest_year, sc["harvest_month"], 15)
                records.append(
                    {
                        "record_id": _uid(
                            f"yield_{farm['farm_id']}_{crop['crop_id']}_{sc['year']}"
                        ),
                        "farm_id": farm["farm_id"],
                        "crop_id": crop["crop_id"],
                        "season": sc["season"],
                        "year": sc["year"],
                        "yield_kg_per_hectare": round(random.uniform(lo, hi), 2),
                        "harvest_date": harvest_date.isoformat(),
                        "notes": f"Seed data — {sc['season']} {sc['year']}",
                    }
                )
    return records


def _generate_pest_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    crop_map = {c["crop_name"]: c for c in CROPS}
    kharif_crops = ["Rice", "Cotton"]
    rabi_crops = ["Wheat"]

    for farm in FARMS:
        for crop_name, crops_list, season_start in [
            (kc, kharif_crops, date(2023, 7, 1)) for kc in kharif_crops
        ] + [
            (rc, rabi_crops, date(2023, 11, 15)) for rc in rabi_crops
        ]:
            if crop_name not in crops_list:
                continue
            crop = crop_map[crop_name]
            pests = CROP_PESTS[crop_name]
            # 1-3 pest events per crop per season
            n_events = random.randint(1, 3)
            for i in range(n_events):
                offset_days = random.randint(5, 90)
                detected = season_start + timedelta(days=offset_days)
                severity = random.randint(1, 5)
                resolved_offset = random.randint(7, 21) if severity >= 2 else None
                resolved = (
                    (detected + timedelta(days=resolved_offset))
                    if resolved_offset
                    else None
                )
                treatments = {
                    "aphids": "Imidacloprid 17.8 SL @ 150ml/acre",
                    "stem borer": "Chlorpyrifos 20 EC @ 1L/acre",
                    "armyworm": "Emamectin benzoate 5 SG @ 80g/acre",
                    "bollworm": "Spinosad 45 SC @ 75ml/acre",
                    "whitefly": "Thiamethoxam 25 WG @ 80g/acre",
                }
                pest_name = random.choice(pests)
                records.append(
                    {
                        "pest_id": _uid(
                            f"pest_{farm['farm_id']}_{crop['crop_id']}_{detected}_{i}"
                        ),
                        "farm_id": farm["farm_id"],
                        "crop_id": crop["crop_id"],
                        "pest_name": pest_name,
                        "severity": severity,
                        "affected_area_pct": round(random.uniform(5.0, 60.0), 1),
                        "detected_date": detected.isoformat(),
                        "resolved_date": resolved.isoformat() if resolved else None,
                        "treatment_applied": treatments.get(pest_name),
                    }
                )
    return records


def _generate_soil_health() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    # 3 readings per farm: pre-Kharif, mid-Kharif, post-Rabi
    sample_dates = [
        date(2023, 5, 10),
        date(2023, 9, 20),
        date(2024, 3, 5),
    ]
    for farm in FARMS:
        baseline = SOIL_BASELINES[farm["state"]]
        for idx, sample_date in enumerate(sample_dates):
            records.append(
                {
                    "soil_id": _uid(f"soil_{farm['farm_id']}_{sample_date}"),
                    "farm_id": farm["farm_id"],
                    "recorded_date": sample_date.isoformat(),
                    "ph_level": round(_jitter(baseline["ph_level"], 0.05), 2),
                    "nitrogen_ppm": round(_jitter(baseline["nitrogen_ppm"], 0.12), 1),
                    "phosphorus_ppm": round(_jitter(baseline["phosphorus_ppm"], 0.15), 1),
                    "potassium_ppm": round(_jitter(baseline["potassium_ppm"], 0.10), 1),
                    "organic_matter_pct": round(
                        _jitter(baseline["organic_matter_pct"], 0.10), 3
                    ),
                    "moisture_pct": round(_jitter(baseline["moisture_pct"], 0.15), 1),
                }
            )
    return records


def _generate_irrigation_logs() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    # Weekly irrigation events across Kharif (Jun–Nov 2023) and Rabi (Nov 2023–Apr 2024)
    kharif_start = date(2023, 6, 1)
    rabi_start = date(2023, 11, 1)
    kharif_weeks = 22  # 22 weeks
    rabi_weeks = 22

    # Map farm state to common method
    state_method = {
        "Punjab": "flood",
        "Maharashtra": "drip",
        "Uttar Pradesh": "flood",
        "Karnataka": "sprinkler",
        "Rajasthan": "drip",
    }

    for farm in FARMS:
        method = state_method[farm["state"]]
        for crop_name, start, n_weeks in [
            ("Rice",   kharif_start, kharif_weeks),
            ("Wheat",  rabi_start,   rabi_weeks),
        ]:
            baseline_liters = CROP_IRRIGATION_BASELINE_LITERS[crop_name]
            weekly_target = baseline_liters / n_weeks
            for week in range(n_weeks):
                log_date = start + timedelta(weeks=week)
                water = round(_jitter(weekly_target, 0.15), 0)
                duration = int(water / 300)  # rough: 300 L/min
                records.append(
                    {
                        "log_id": _uid(
                            f"irr_{farm['farm_id']}_{crop_name}_{log_date}"
                        ),
                        "farm_id": farm["farm_id"],
                        "log_date": log_date.isoformat(),
                        "water_used_liters": water,
                        "method": method,
                        "duration_minutes": duration,
                    }
                )
    return records


# ---------------------------------------------------------------------------
# Main seeding routine
# ---------------------------------------------------------------------------
def seed_database(connector: Any) -> None:
    """
    Insert all seed data via HistoricalDBConnector.insert_record().

    The connector must already have its session open (or will use its
    internal _get_session context manager per record).
    """
    random.seed(42)  # reproducible

    logger.info("Seeding farms…")
    for farm in FARMS:
        try:
            connector.insert_record("farms", farm)
        except Exception as e:
            logger.warning("Farm insert skipped (may already exist): %s", e)

    logger.info("Seeding crops…")
    for crop in CROPS:
        try:
            connector.insert_record("crops", crop)
        except Exception as e:
            logger.warning("Crop insert skipped (may already exist): %s", e)

    logger.info("Seeding yield_records…")
    for rec in _generate_yield_records():
        try:
            connector.insert_record("yield_records", rec)
        except Exception as e:
            logger.warning("Yield record insert skipped: %s", e)

    logger.info("Seeding pest_records…")
    for rec in _generate_pest_records():
        try:
            connector.insert_record("pest_records", rec)
        except Exception as e:
            logger.warning("Pest record insert skipped: %s", e)

    logger.info("Seeding irrigation_logs…")
    for rec in _generate_irrigation_logs():
        try:
            connector.insert_record("irrigation_logs", rec)
        except Exception as e:
            logger.warning("Irrigation log insert skipped: %s", e)

    logger.info("Seeding soil_health…")
    for rec in _generate_soil_health():
        try:
            connector.insert_record("soil_health", rec)
        except Exception as e:
            logger.warning("Soil health insert skipped: %s", e)

    logger.info("Seeding complete.")


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    # Import here to avoid circular issues when running standalone
    from historical_db.db_connector import HistoricalDBConnector

    with HistoricalDBConnector() as conn:
        conn.create_all_tables()
        seed_database(conn)
