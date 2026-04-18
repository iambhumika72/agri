"""
ingestion/spectral_indices.py
==============================
Compute per-pixel spectral indices (NDVI, NDWI, SAVI, EVI) from a
multi-band Sentinel-2 GeoTIFF produced by satellite_ingestor.py.

Band order inside the GeoTIFF (1-indexed):
    1 → B02 (Blue)
    2 → B03 (Green)
    3 → B04 (Red)
    4 → B08 (NIR)

Cloud-masked pixels are stored as 0 in every band; they are excluded from
all statistical calculations.

Output
------
- IndexResult  dataclass (in-memory)
- False-color composite PNG (NIR-Red-Green) written to
  preprocessing/composites/{farm_id}_{date}.png
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import rasterio
from PIL import Image

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)

COMPOSITE_DIR = Path("preprocessing/composites")
STRESS_NDVI_THRESHOLD = 0.30  # ndvi_mean below this triggers stress_alert


# ---------------------------------------------------------------------------
# Typed dataclass
# ---------------------------------------------------------------------------

@dataclass
class IndexResult:
    """Container for spectral index arrays and summary statistics."""

    ndvi_array: np.ndarray
    ndwi_array: np.ndarray
    savi_array: np.ndarray
    evi_array: np.ndarray

    ndvi_mean: float
    ndvi_std: float
    ndwi_mean: float

    stress_alert: bool          # True when ndvi_mean < STRESS_NDVI_THRESHOLD
    pixel_coverage_pct: float   # % of non-masked (valid) pixels in scene

    farm_id: str = ""
    acquisition_date: str = ""
    composite_png_path: str = ""


# ---------------------------------------------------------------------------
# Index computation helpers
# ---------------------------------------------------------------------------

def _safe_divide(
    numerator: np.ndarray,
    denominator: np.ndarray,
    fill: float = 0.0,
) -> np.ndarray:
    """Element-wise division with zero-denominator guard."""
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.where(denominator != 0.0, numerator / denominator, fill)
    return result.astype(np.float32)


def compute_ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """NDVI = (NIR − Red) / (NIR + Red)  — range [−1, 1]"""
    return _safe_divide(nir - red, nir + red)


def compute_ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """NDWI = (Green − NIR) / (Green + NIR)  — range [−1, 1]"""
    return _safe_divide(green - nir, green + nir)


def compute_savi(nir: np.ndarray, red: np.ndarray, L: float = 0.5) -> np.ndarray:
    """SAVI = ((NIR − Red) / (NIR + Red + L)) × (1 + L)"""
    return _safe_divide(nir - red, nir + red + L) * (1.0 + L)


def compute_evi(
    nir: np.ndarray,
    red: np.ndarray,
    blue: np.ndarray,
    G: float = 2.5,
    C1: float = 6.0,
    C2: float = 7.5,
    L: float = 1.0,
) -> np.ndarray:
    """EVI = G × (NIR − Red) / (NIR + C1×Red − C2×Blue + L)"""
    denominator = nir + C1 * red - C2 * blue + L
    return _safe_divide(G * (nir - red), denominator)


# ---------------------------------------------------------------------------
# False-color composite export
# ---------------------------------------------------------------------------

def _export_false_color_composite(
    nir: np.ndarray,
    red: np.ndarray,
    green: np.ndarray,
    valid_mask: np.ndarray,
    farm_id: str,
    acquisition_date: str,
    output_dir: Path = COMPOSITE_DIR,
) -> str:
    """
    Save an 8-bit NIR-Red-Green false-color composite PNG.

    Pixel normalisation uses the 2nd–98th percentile of *valid* pixels to
    avoid outlier stretching.  Cloud-masked pixels are rendered as black.

    Returns the absolute path of the written PNG.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / f"{farm_id}_{acquisition_date}.png"

    def stretch(band: np.ndarray) -> np.ndarray:
        valid_values = band[valid_mask]
        if valid_values.size == 0:
            return np.zeros_like(band, dtype=np.uint8)
        p2, p98 = np.percentile(valid_values, (2, 98))
        clipped = np.clip(band, p2, p98)
        if p98 == p2:
            return np.zeros_like(band, dtype=np.uint8)
        scaled = (clipped - p2) / (p98 - p2) * 255.0
        return scaled.astype(np.uint8)

    r_ch = stretch(nir)    # NIR → Red channel (false-color)
    g_ch = stretch(red)    # Red → Green channel
    b_ch = stretch(green)  # Green → Blue channel

    # Black out cloud-masked pixels
    r_ch[~valid_mask] = 0
    g_ch[~valid_mask] = 0
    b_ch[~valid_mask] = 0

    composite = np.stack([r_ch, g_ch, b_ch], axis=-1)
    img = Image.fromarray(composite, mode="RGB")
    img.save(str(png_path))
    log.info("False-color composite saved: %s", png_path)
    return str(png_path.resolve())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_indices(
    geotiff_path: str | Path,
    farm_id: str = "",
    acquisition_date: str = "",
    composite_output_dir: Path | str = COMPOSITE_DIR,
) -> IndexResult:
    """
    Load a multi-band GeoTIFF and compute NDVI, NDWI, SAVI, EVI.

    Parameters
    ----------
    geotiff_path          : path to the 4-band GeoTIFF (B02, B03, B04, B08)
    farm_id               : used in composite filename; read from GeoTIFF tags if empty
    acquisition_date      : used in composite filename; defaults to today if empty
    composite_output_dir  : directory for the false-color PNG

    Returns
    -------
    IndexResult dataclass
    """
    geotiff_path = Path(geotiff_path)
    if not geotiff_path.exists():
        raise FileNotFoundError(f"GeoTIFF not found: {geotiff_path}")

    composite_output_dir = Path(composite_output_dir)

    log.info("Loading GeoTIFF: %s", geotiff_path)
    with rasterio.open(geotiff_path) as src:
        tags = src.tags()
        if not farm_id:
            farm_id = tags.get("farm_id", geotiff_path.stem)
        if not acquisition_date:
            acquisition_date = tags.get(
                "acquisition_date",
                datetime.utcnow().strftime("%Y-%m-%d"),
            )
        # Band order: 1=B02(Blue), 2=B03(Green), 3=B04(Red), 4=B08(NIR)
        blue  = src.read(1).astype(np.float32)
        green = src.read(2).astype(np.float32)
        red   = src.read(3).astype(np.float32)
        nir   = src.read(4).astype(np.float32)

    log.info(
        "Bands loaded | shape=%s | dtype=%s", blue.shape, blue.dtype
    )

    # ---- valid pixel mask (all bands must be non-zero) ----
    valid_mask: np.ndarray = (blue != 0) | (green != 0) | (red != 0) | (nir != 0)
    total_pixels = valid_mask.size
    valid_pixels = int(valid_mask.sum())
    pixel_coverage_pct = (valid_pixels / max(total_pixels, 1)) * 100.0
    log.info(
        "Valid pixels: %d / %d (%.1f%%)",
        valid_pixels, total_pixels, pixel_coverage_pct,
    )

    # ---- spectral index arrays ----
    ndvi_array = compute_ndvi(nir, red)
    ndwi_array = compute_ndwi(green, nir)
    savi_array = compute_savi(nir, red)
    evi_array  = compute_evi(nir, red, blue)

    # Zero-out masked pixels in index arrays
    for arr in (ndvi_array, ndwi_array, savi_array, evi_array):
        arr[~valid_mask] = 0.0

    # ---- statistics (valid pixels only) ----
    def _masked_stats(arr: np.ndarray) -> tuple[float, float]:
        vals = arr[valid_mask]
        if vals.size == 0:
            return 0.0, 0.0
        return float(np.mean(vals)), float(np.std(vals))

    ndvi_mean, ndvi_std = _masked_stats(ndvi_array)
    ndwi_mean, _        = _masked_stats(ndwi_array)

    stress_alert = ndvi_mean < STRESS_NDVI_THRESHOLD
    log.info(
        "NDVI: mean=%.3f std=%.3f | NDWI mean=%.3f | stress_alert=%s",
        ndvi_mean, ndvi_std, ndwi_mean, stress_alert,
    )

    # ---- false-color composite ----
    composite_path = _export_false_color_composite(
        nir=nir,
        red=red,
        green=green,
        valid_mask=valid_mask,
        farm_id=farm_id,
        acquisition_date=acquisition_date,
        output_dir=composite_output_dir,
    )

    return IndexResult(
        ndvi_array=ndvi_array,
        ndwi_array=ndwi_array,
        savi_array=savi_array,
        evi_array=evi_array,
        ndvi_mean=round(ndvi_mean, 4),
        ndvi_std=round(ndvi_std, 4),
        ndwi_mean=round(ndwi_mean, 4),
        stress_alert=stress_alert,
        pixel_coverage_pct=round(pixel_coverage_pct, 2),
        farm_id=farm_id,
        acquisition_date=acquisition_date,
        composite_png_path=composite_path,
    )


# ---------------------------------------------------------------------------
# __main__ – synthetic GeoTIFF smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import tempfile
    from rasterio.transform import from_bounds

    log.info("Generating synthetic GeoTIFF for spectral index smoke test …")

    rng = np.random.default_rng(seed=42)
    H, W = 256, 256

    # Simulate reflectance values [0, 1] — healthy vegetation: NIR high, Red low
    blue  = rng.uniform(0.02, 0.08, (H, W)).astype(np.float32)
    green = rng.uniform(0.04, 0.12, (H, W)).astype(np.float32)
    red   = rng.uniform(0.03, 0.10, (H, W)).astype(np.float32)
    nir   = rng.uniform(0.30, 0.70, (H, W)).astype(np.float32)

    # Introduce a 10% cloud-masked region (set to 0)
    cloud_y, cloud_x = slice(0, 26), slice(0, 26)
    for arr in (blue, green, red, nir):
        arr[cloud_y, cloud_x] = 0.0

    transform = from_bounds(75.85, 30.90, 75.95, 30.98, W, H)

    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    with rasterio.open(
        tmp_path,
        "w",
        driver="GTiff",
        height=H,
        width=W,
        count=4,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
    ) as dst:
        dst.write(blue, 1)
        dst.write(green, 2)
        dst.write(red, 3)
        dst.write(nir, 4)

    log.info("Synthetic GeoTIFF: %s", tmp_path)

    result = compute_indices(
        geotiff_path=tmp_path,
        farm_id="test_farm",
        acquisition_date="2024-10-15",
    )

    print("\n── IndexResult summary ──────────────────────────────────────")
    print(f"  NDVI  mean={result.ndvi_mean:.4f}  std={result.ndvi_std:.4f}")
    print(f"  NDWI  mean={result.ndwi_mean:.4f}")
    print(f"  stress_alert      : {result.stress_alert}")
    print(f"  pixel_coverage_pct: {result.pixel_coverage_pct:.1f}%")
    print(f"  composite PNG     : {result.composite_png_path}")
    print("──────────────────────────────────────────────────────────────\n")

    tmp_path.unlink(missing_ok=True)
