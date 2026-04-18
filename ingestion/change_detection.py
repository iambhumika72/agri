"""
ingestion/change_detection.py
==============================
Temporal NDVI change detection for the AgriSense pipeline.

Given two registered NDVI arrays (current + 30-days-prior), this module:
  1. Computes the pixel-wise delta  (prior − current)
  2. Flags alert zones where the decline exceeds 0.15 NDVI units
  3. Vectorises the boolean alert mask into GeoJSON polygons (per-field)
  4. Classifies overall severity as "low" / "moderate" / "high"
  5. Writes alert GeoJSON to preprocessing/alerts/{farm_id}_{date}_alert.geojson

All spatial operations use rasterio + shapely; no GDAL CLI required.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import rasterio.features
from rasterio.crs import CRS
from rasterio.transform import from_bounds, Affine
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)

ALERT_DIR = Path("preprocessing/alerts")
DECLINE_THRESHOLD = 0.15   # NDVI decline magnitude considered significant
SEVERITY_MODERATE_PCT = 10.0   # % of field affected → moderate
SEVERITY_HIGH_PCT     = 30.0   # % of field affected → high


# ---------------------------------------------------------------------------
# Typed result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ChangeResult:
    """Outcome of a single change detection run."""

    delta_array: np.ndarray        # (H, W) float32 — prior − current
    alert_mask: np.ndarray         # (H, W) bool    — True where delta > threshold
    alert_zone_pct: float          # % of field in alert
    alert_geojson: dict            # GeoJSON FeatureCollection of alert polygons
    severity: str                  # "low" | "moderate" | "high"

    farm_id: str = ""
    detection_date: str = ""
    geojson_path: str = ""         # path of written GeoJSON file


# ---------------------------------------------------------------------------
# Severity classifier
# ---------------------------------------------------------------------------

def _classify_severity(alert_zone_pct: float) -> str:
    if alert_zone_pct < SEVERITY_MODERATE_PCT:
        return "low"
    if alert_zone_pct < SEVERITY_HIGH_PCT:
        return "moderate"
    return "high"


# ---------------------------------------------------------------------------
# Vectorisation: boolean raster mask → GeoJSON FeatureCollection
# ---------------------------------------------------------------------------

def _mask_to_geojson(
    alert_mask: np.ndarray,
    transform: Affine,
    crs_str: str,
) -> dict[str, Any]:
    """
    Convert a boolean 2-D ndarray into a GeoJSON FeatureCollection.

    Uses rasterio.features.shapes to extract connected regions from the mask,
    then filters only True (alert) regions.
    """
    mask_uint8 = alert_mask.astype(np.uint8)

    features: list[dict] = []
    for geom_dict, value in rasterio.features.shapes(
        mask_uint8, transform=transform
    ):
        if int(value) == 1:  # keep only alert regions
            geom = shape(geom_dict)
            features.append(
                {
                    "type": "Feature",
                    "geometry": mapping(geom),
                    "properties": {
                        "alert": True,
                        "crs": crs_str,
                        "description": "Significant NDVI decline detected",
                    },
                }
            )

    geojson: dict[str, Any] = {
        "type": "FeatureCollection",
        "features": features,
        "crs": {
            "type": "name",
            "properties": {"name": crs_str},
        },
    }
    log.info("Vectorised %d alert polygon(s) from mask.", len(features))
    return geojson


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_change(
    ndvi_current: np.ndarray,
    ndvi_prior: np.ndarray,
    farm_polygon,              # shapely geometry (Polygon / MultiPolygon)
    crs_str: str,
    output_dir: str | Path = ALERT_DIR,
    farm_id: str = "",
    detection_date: str = "",
    transform: Affine | None = None,
) -> ChangeResult:
    """
    Compute NDVI change detection between two registered array observations.

    Parameters
    ----------
    ndvi_current   : (H, W) float32 array — most recent NDVI
    ndvi_prior     : (H, W) float32 array — 30-days-prior NDVI (same grid)
    farm_polygon   : shapely Polygon/MultiPolygon defining the field boundary
    crs_str        : CRS string, e.g. "EPSG:32643"
    output_dir     : directory for alert GeoJSON output
    farm_id        : identifier used in output filename
    detection_date : ISO-8601 date string; defaults to today
    transform      : rasterio Affine transform for the arrays; if None, a
                     unit-pixel transform is used (coordinates = pixel indices)

    Returns
    -------
    ChangeResult dataclass
    """
    if ndvi_current.shape != ndvi_prior.shape:
        raise ValueError(
            f"NDVI array shape mismatch: current={ndvi_current.shape} "
            f"vs prior={ndvi_prior.shape}"
        )

    farm_id = farm_id or str(uuid.uuid4())[:8]
    detection_date = detection_date or datetime.utcnow().strftime("%Y-%m-%d")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    H, W = ndvi_current.shape

    # Default transform: pixel (row, col) == spatial coordinate
    if transform is None:
        transform = from_bounds(0, 0, W, H, W, H)

    log.info(
        "Running change detection | farm_id=%s | date=%s | shape=(%d×%d)",
        farm_id, detection_date, H, W,
    )

    # ---- 1. Delta map ----
    ndvi_current = ndvi_current.astype(np.float32)
    ndvi_prior   = ndvi_prior.astype(np.float32)
    delta_array  = ndvi_prior - ndvi_current  # positive → decline

    # ---- 2. Mask to farm boundary using rasterio.features.geometry_mask ----
    farm_mask = rasterio.features.geometry_mask(
        [mapping(farm_polygon)],
        out_shape=(H, W),
        transform=transform,
        invert=True,   # True inside polygon
    )

    # ---- 3. Alert mask: decline > threshold AND inside farm ----
    alert_mask: np.ndarray = (delta_array > DECLINE_THRESHOLD) & farm_mask

    # ---- 4. Alert zone percentage ----
    farm_pixel_count = int(farm_mask.sum())
    alert_pixel_count = int(alert_mask.sum())
    alert_zone_pct = (
        (alert_pixel_count / farm_pixel_count * 100.0)
        if farm_pixel_count > 0
        else 0.0
    )
    severity = _classify_severity(alert_zone_pct)

    log.info(
        "Alert zone: %d / %d farm pixels (%.1f%%) — severity=%s",
        alert_pixel_count, farm_pixel_count, alert_zone_pct, severity,
    )

    # ---- 5. Vectorise alert mask → GeoJSON ----
    alert_geojson = _mask_to_geojson(alert_mask, transform, crs_str)

    # ---- 6. Write GeoJSON ----
    geojson_filename = f"{farm_id}_{detection_date}_alert.geojson"
    geojson_path = output_dir / geojson_filename
    with open(geojson_path, "w", encoding="utf-8") as fh:
        json.dump(alert_geojson, fh, indent=2)
    log.info("Alert GeoJSON written: %s", geojson_path)

    return ChangeResult(
        delta_array=delta_array,
        alert_mask=alert_mask,
        alert_zone_pct=round(alert_zone_pct, 2),
        alert_geojson=alert_geojson,
        severity=severity,
        farm_id=farm_id,
        detection_date=detection_date,
        geojson_path=str(geojson_path.resolve()),
    )


# ---------------------------------------------------------------------------
# __main__ – synthetic validation
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from shapely.geometry import box

    log.info("Running synthetic change detection test …")

    rng = np.random.default_rng(seed=7)
    H, W = 100, 100

    # Simulate healthy prior NDVI
    ndvi_prior = rng.uniform(0.55, 0.75, (H, W)).astype(np.float32)

    # Current NDVI with stressed patch (top-left quadrant)
    ndvi_current = ndvi_prior.copy()
    ndvi_current[:40, :40] -= rng.uniform(0.20, 0.35, (40, 40)).astype(np.float32)
    ndvi_current = np.clip(ndvi_current, -1.0, 1.0)

    # Farm polygon covers the full 100×100 pixel extent (in pixel coords)
    farm_polygon = box(0, 0, W, H)
    crs_str = "EPSG:32643"

    result = detect_change(
        ndvi_current=ndvi_current,
        ndvi_prior=ndvi_prior,
        farm_polygon=farm_polygon,
        crs_str=crs_str,
        output_dir=Path("preprocessing/alerts"),
        farm_id="test_farm",
        detection_date="2024-10-15",
    )

    print("\n── ChangeResult summary ─────────────────────────────────────")
    print(f"  alert_zone_pct : {result.alert_zone_pct:.1f}%")
    print(f"  severity       : {result.severity}")
    print(f"  alert polygons : {len(result.alert_geojson['features'])}")
    print(f"  geojson_path   : {result.geojson_path}")
    print("──────────────────────────────────────────────────────────────\n")
