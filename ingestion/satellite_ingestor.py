"""
ingestion/satellite_ingestor.py
================================
Sentinel-2 (Level-2A) satellite imagery ingestion pipeline for AgriSense.

Primary source  : Copernicus Open Access Hub (sentinelsat)
Fallback source : Google Earth Engine (ee) — triggered when Hub returns 0 results

Auth env vars
-------------
COPERNICUS_USER        – Copernicus Hub username
COPERNICUS_PASSWORD    – Copernicus Hub password
GEE_SERVICE_ACCOUNT    – GEE service-account email
GEE_KEY_FILE           – path to GEE service-account JSON key (optional; falls
                         back to Application Default Credentials if absent)
"""

from __future__ import annotations

import json
import logging
import math
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.mask import mask as rasterio_mask
from rasterio.merge import merge as rasterio_merge
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, calculate_default_transform, reproject
from sentinelsat import SentinelAPI, geojson_to_wkt, read_geojson
from shapely.geometry import box, mapping, shape

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SENTINEL_HUB_URL = "https://apihub.copernicus.eu/apihub"
BAND_NAMES = ["B02", "B03", "B04", "B08"]  # Blue, Green, Red, NIR
SCL_BAND = "SCL"
# SCL classes to treat as cloud / invalid
CLOUD_SCL_CLASSES = {3, 8, 9, 10, 11}
OUTPUT_DIR = Path("data/satellite_tiles")


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _bbox_to_geojson(bbox: tuple[float, float, float, float]) -> dict:
    """Convert (minx, miny, maxx, maxy) bbox to a GeoJSON Polygon dict."""
    minx, miny, maxx, maxy = bbox
    return {
        "type": "Feature",
        "geometry": mapping(box(minx, miny, maxx, maxy)),
        "properties": {},
    }


def _load_polygon(geometry_input: dict | tuple) -> dict:
    """
    Accept either a GeoJSON-like dict (Feature / Geometry) or a bbox tuple
    (minx, miny, maxx, maxy) and return a GeoJSON Geometry dict.
    """
    if isinstance(geometry_input, (list, tuple)) and len(geometry_input) == 4:
        return _bbox_to_geojson(geometry_input)["geometry"]
    if isinstance(geometry_input, dict):
        if geometry_input.get("type") == "Feature":
            return geometry_input["geometry"]
        return geometry_input  # already a Geometry
    raise ValueError(
        "geometry_input must be a (minx, miny, maxx, maxy) tuple or GeoJSON dict."
    )


def _compute_cloud_fraction(scl_path: Path) -> float:
    """
    Read SCL raster and return the fraction [0–1] of cloud / shadow pixels.
    """
    with rasterio.open(scl_path) as src:
        scl = src.read(1).astype(np.int32)
    cloud_mask = np.isin(scl, list(CLOUD_SCL_CLASSES))
    return float(cloud_mask.sum()) / max(scl.size, 1)


def _stack_bands_to_geotiff(
    band_paths: dict[str, Path],
    scl_path: Path,
    polygon_geom: dict,
    output_path: Path,
) -> tuple[float, str]:
    """
    Stack individual band GeoTIFFs into a multi-band output, apply SCL cloud
    mask (set masked pixels to 0), clip to the farm polygon, and write the
    result to *output_path*.

    Returns (cloud_cover_pct: float, crs: str).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ---- read all bands; reproject to a common CRS (first band's CRS) ----
    band_arrays: list[np.ndarray] = []
    ref_meta: dict | None = None
    ref_crs: CRS | None = None
    ref_transform = None
    ref_shape: tuple[int, int] | None = None

    with rasterio.open(band_paths[BAND_NAMES[0]]) as ref_src:
        ref_crs = ref_src.crs
        ref_transform = ref_src.transform
        ref_shape = ref_src.shape
        ref_meta = ref_src.meta.copy()

    for band_name in BAND_NAMES:
        with rasterio.open(band_paths[band_name]) as src:
            if src.crs != ref_crs:
                data = np.zeros(ref_shape, dtype=np.float32)
                reproject(
                    source=rasterio.band(src, 1),
                    destination=data,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=ref_transform,
                    dst_crs=ref_crs,
                    resampling=Resampling.bilinear,
                )
            else:
                data = src.read(1).astype(np.float32)
        band_arrays.append(data)

    # ---- cloud mask from SCL ----
    with rasterio.open(scl_path) as scl_src:
        if scl_src.crs != ref_crs or scl_src.shape != ref_shape:
            scl_data = np.zeros(ref_shape, dtype=np.int32)
            reproject(
                source=rasterio.band(scl_src, 1),
                destination=scl_data,
                src_transform=scl_src.transform,
                src_crs=scl_src.crs,
                dst_transform=ref_transform,
                dst_crs=ref_crs,
                resampling=Resampling.nearest,
            )
        else:
            scl_data = scl_src.read(1).astype(np.int32)

    cloud_mask = np.isin(scl_data, list(CLOUD_SCL_CLASSES))
    cloud_cover_pct = float(cloud_mask.sum()) / max(scl_data.size, 1) * 100.0
    log.info("Cloud cover for tile: %.1f%%", cloud_cover_pct)

    # Apply cloud mask (set masked pixels → 0 in every band)
    stacked = np.stack(band_arrays, axis=0)  # shape (4, H, W)
    stacked[:, cloud_mask] = 0.0

    # ---- write temp multi-band raster ----
    tmp_path = output_path.with_suffix(".tmp.tif")
    meta = ref_meta.copy()
    meta.update(
        count=len(BAND_NAMES),
        dtype="float32",
        driver="GTiff",
        compress="lzw",
    )
    with rasterio.open(tmp_path, "w", **meta) as dst:
        for i, arr in enumerate(stacked, start=1):
            dst.write(arr, i)
        dst.update_tags(BAND_NAMES=",".join(BAND_NAMES))

    # ---- clip to farm polygon ----
    with rasterio.open(tmp_path) as src:
        clipped, clipped_transform = rasterio_mask(
            src,
            [polygon_geom],
            crop=True,
            nodata=0.0,
            filled=True,
        )
        clip_meta = src.meta.copy()
        clip_meta.update(
            {
                "height": clipped.shape[1],
                "width": clipped.shape[2],
                "transform": clipped_transform,
            }
        )

    with rasterio.open(output_path, "w", **clip_meta) as dst:
        dst.write(clipped)
        dst.update_tags(BAND_NAMES=",".join(BAND_NAMES))

    tmp_path.unlink(missing_ok=True)
    crs_str = str(ref_crs)
    log.info("Multi-band GeoTIFF written: %s  (CRS=%s)", output_path, crs_str)
    return cloud_cover_pct, crs_str


# ---------------------------------------------------------------------------
# Primary source: Copernicus Hub via sentinelsat
# ---------------------------------------------------------------------------

class CopernicusIngestor:
    """Wraps sentinelsat for Sentinel-2 L2A product search and download."""

    def __init__(self) -> None:
        user = os.environ["COPERNICUS_USER"]
        password = os.environ["COPERNICUS_PASSWORD"]
        self.api = SentinelAPI(user, password, SENTINEL_HUB_URL)
        log.info("SentinelAPI authenticated as '%s'", user)

    def search(
        self,
        footprint_wkt: str,
        start_date: str,
        end_date: str,
        cloud_cover_threshold: float,
    ) -> dict:
        """Return {product_id: product_info} matching search criteria."""
        products = self.api.query(
            area=footprint_wkt,
            date=(start_date.replace("-", ""), end_date.replace("-", "")),
            platformname="Sentinel-2",
            processinglevel="Level-2A",
            cloudcoverpercentage=(0, cloud_cover_threshold * 100),
        )
        log.info("Copernicus Hub returned %d product(s).", len(products))
        return products

    def download(
        self,
        product_id: str,
        download_dir: Path,
    ) -> Path:
        """Download a single product and return the path to its .SAFE directory."""
        download_dir.mkdir(parents=True, exist_ok=True)
        info = self.api.download(str(product_id), directory_path=str(download_dir))
        safe_path = Path(info["path"])
        log.info("Downloaded product to: %s", safe_path)
        return safe_path

    def locate_bands(
        self,
        safe_path: Path,
    ) -> tuple[dict[str, Path], Path]:
        """
        Walk the .SAFE directory tree and locate each required band JP2 + SCL.
        Returns (band_paths_dict, scl_path).
        """
        band_paths: dict[str, Path] = {}
        scl_path: Path | None = None

        for jp2 in safe_path.rglob("*.jp2"):
            stem = jp2.stem.upper()
            for band in BAND_NAMES:
                if band in stem and band not in band_paths:
                    band_paths[band] = jp2
            if SCL_BAND in stem and scl_path is None:
                scl_path = jp2

        missing = set(BAND_NAMES) - set(band_paths)
        if missing:
            raise FileNotFoundError(
                f"Could not locate bands {missing} in {safe_path}"
            )
        if scl_path is None:
            raise FileNotFoundError(f"SCL band not found in {safe_path}")

        log.info("Located bands: %s | SCL: %s", band_paths, scl_path)
        return band_paths, scl_path


# ---------------------------------------------------------------------------
# Fallback source: Google Earth Engine
# ---------------------------------------------------------------------------

class GEEIngestor:
    """
    Exports Sentinel-2 SR imagery + SCL from Google Earth Engine.
    Requires earthengine-api to be installed and authenticated.
    """

    def __init__(self) -> None:
        import ee  # local import — optional dependency

        svc_account = os.environ.get("GEE_SERVICE_ACCOUNT")
        key_file = os.environ.get("GEE_KEY_FILE")
        if svc_account and key_file:
            credentials = ee.ServiceAccountCredentials(svc_account, key_file)
            ee.Initialize(credentials)
            log.info("GEE initialized with service account: %s", svc_account)
        else:
            ee.Initialize()
            log.info("GEE initialized with Application Default Credentials.")
        self._ee = ee

    def fetch_and_export(
        self,
        polygon_geom: dict,
        start_date: str,
        end_date: str,
        cloud_cover_threshold: float,
        farm_id: str,
        output_dir: Path,
    ) -> tuple[dict[str, Path], Path, str]:
        """
        Export Sentinel-2 L2A bands + SCL to local GeoTIFFs via Drive export
        (synchronous poll).  Returns (band_paths, scl_path, acquisition_date).
        """
        ee = self._ee
        region = ee.Geometry(polygon_geom)

        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterDate(start_date, end_date)
            .filterBounds(region)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_cover_threshold * 100))
            .sort("CLOUDY_PIXEL_PERCENTAGE")
        )

        size = collection.size().getInfo()
        log.info("GEE collection size: %d image(s).", size)

        if size == 0:
            # Relax cloud threshold — return the least cloudy image in range
            log.warning(
                "GEE: no scene below threshold; relaxing to 100%% cloud cover."
            )
            collection = (
                ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                .filterDate(start_date, end_date)
                .filterBounds(region)
                .sort("CLOUDY_PIXEL_PERCENTAGE")
            )
            size = collection.size().getInfo()
            if size == 0:
                raise RuntimeError(
                    "GEE returned 0 images for the requested AOI and date range."
                )

        image = collection.first()
        acq_date = (
            ee.Date(image.get("system:time_start"))
            .format("YYYY-MM-dd")
            .getInfo()
        )
        log.info("GEE selected image acquisition date: %s", acq_date)

        output_dir.mkdir(parents=True, exist_ok=True)
        band_paths: dict[str, Path] = {}

        all_bands = BAND_NAMES + [SCL_BAND]
        for band in all_bands:
            band_img = image.select([band]).clip(region)
            url = band_img.getDownloadURL(
                {
                    "bands": [band],
                    "region": region,
                    "scale": 10,
                    "format": "GEO_TIFF",
                    "crs": "EPSG:4326",
                }
            )
            import urllib.request

            dest = output_dir / f"{farm_id}_{acq_date}_{band}.tif"
            log.info("Downloading GEE band %s → %s", band, dest)
            urllib.request.urlretrieve(url, dest)  # noqa: S310

            if band == SCL_BAND:
                scl_path = dest
            else:
                band_paths[band] = dest

        return band_paths, scl_path, acq_date


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ingest_sentinel2(
    geometry_input: dict | tuple,
    start_date: str,
    end_date: str,
    farm_id: str | None = None,
    cloud_cover_threshold: float = 0.20,
    output_dir: Path | str = OUTPUT_DIR,
) -> dict[str, Any]:
    """
    Fetch Sentinel-2 (L2A) imagery for the given geometry and date range.

    Parameters
    ----------
    geometry_input        : GeoJSON Feature/Geometry dict **or** (minx,miny,maxx,maxy) bbox tuple
    start_date, end_date  : ISO-8601 date strings, e.g. "2024-05-01"
    farm_id               : unique farm identifier (auto-generated UUID if None)
    cloud_cover_threshold : maximum acceptable cloud fraction (0–1)
    output_dir            : root directory for GeoTIFF outputs

    Returns
    -------
    dict with keys:
        geotiff_path     (str)
        acquisition_date (str)  ISO-8601
        cloud_cover_pct  (float)
        farm_id          (str)
        crs              (str)
        stale            (bool)  – True when best available scene exceeds threshold
    """
    farm_id = farm_id or str(uuid.uuid4())[:8]
    output_dir = Path(output_dir)
    polygon_geom = _load_polygon(geometry_input)
    footprint_wkt = shape(polygon_geom).wkt

    log.info(
        "Starting ingestion | farm_id=%s | %s → %s | cloud_thresh=%.0f%%",
        farm_id, start_date, end_date, cloud_cover_threshold * 100,
    )
    
    # ------------------------------------------------------------------ #
    # Step 0: Check DB for existing 'Ground-Truth' records                #
    # ------------------------------------------------------------------ #
    from historical_db.db_connector import HistoricalDBConnector
    from datetime import date as dt_date
    
    try:
        with HistoricalDBConnector() as db:
            s_date = dt_date.fromisoformat(start_date)
            e_date = dt_date.fromisoformat(end_date)
            db_records = db.get_satellite_imagery(farm_id, s_date, e_date)
            
            if not db_records.empty:
                # Pick the latest/best one
                best = db_records.iloc[0]
                log.info("Found seeded/historical record in DB: %s", best["image_path"])
                return {
                    "geotiff_path": best["image_path"],
                    "acquisition_date": best.name[1].strftime("%Y-%m-%d"),
                    "cloud_cover_pct": best["cloud_cover_pct"],
                    "farm_id": farm_id,
                    "crs": "EPSG:4326", # Default for seeded data
                    "stale": False,
                }
    except Exception as db_err:
        log.warning("DB lookup for satellite imagery failed: %s", db_err)

    band_paths: dict[str, Path] | None = None
    scl_path: Path | None = None
    acquisition_date: str | None = None
    stale = False
    used_gee = False

    # ------------------------------------------------------------------ #
    # Step 1: Try Copernicus Hub                                          #
    # ------------------------------------------------------------------ #
    try:
        copernicus = CopernicusIngestor()
        products = copernicus.search(
            footprint_wkt, start_date, end_date, cloud_cover_threshold
        )

        if len(products) == 0:
            log.warning(
                "Copernicus Hub returned 0 results — trying without cloud filter."
            )
            # Attempt stale fallback via Hub (relaxed threshold)
            products = copernicus.search(footprint_wkt, start_date, end_date, 1.0)
            if len(products) > 0:
                stale = True

        if len(products) > 0:
            # Sort by cloud cover ascending; pick best
            products_df = copernicus.api.to_dataframe(products)
            best_pid = products_df.sort_values("cloudcoverpercentage").index[0]
            safe_path = copernicus.download(best_pid, output_dir / "raw")
            band_paths, scl_path = copernicus.locate_bands(safe_path)
            # Parse acquisition date from product title (e.g. S2B_MSIL2A_20240601T…)
            title: str = products[best_pid]["title"]
            date_part = title.split("_")[2][:8]
            acquisition_date = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:]}"

    except Exception as hub_err:  # noqa: BLE001
        log.warning("Copernicus Hub step failed (%s) — switching to GEE.", hub_err)

    # ------------------------------------------------------------------ #
    # Step 2: GEE fallback                                                #
    # ------------------------------------------------------------------ #
    if band_paths is None:
        used_gee = True
        log.info("Activating GEE fallback ingestor.")
        gee = GEEIngestor()
        tmp_dir = output_dir / "gee_raw" / farm_id
        band_paths, scl_path, acquisition_date = gee.fetch_and_export(
            polygon_geom,
            start_date,
            end_date,
            cloud_cover_threshold,
            farm_id,
            tmp_dir,
        )
        # If GEE also had to relax threshold, mark stale
        # (GEEIngestor already logs the relaxation; we check cloud cover after stack)

    # ------------------------------------------------------------------ #
    # Step 3: Stack bands, apply cloud mask, clip, write GeoTIFF         #
    # ------------------------------------------------------------------ #
    output_path = output_dir / f"{farm_id}_{acquisition_date}.tif"
    cloud_cover_pct, crs = _stack_bands_to_geotiff(
        band_paths, scl_path, polygon_geom, output_path
    )

    # Confirm stale flag post-hoc: if cloud cover still exceeds threshold
    if cloud_cover_pct / 100.0 > cloud_cover_threshold:
        stale = True
        log.warning(
            "Best available scene has %.1f%% cloud cover (threshold %.0f%%). "
            "Returning stale observation.",
            cloud_cover_pct, cloud_cover_threshold * 100,
        )

    result: dict[str, Any] = {
        "geotiff_path": str(output_path.resolve()),
        "acquisition_date": acquisition_date,
        "cloud_cover_pct": round(cloud_cover_pct, 2),
        "farm_id": farm_id,
        "crs": crs,
        "stale": stale,
    }
    log.info("Ingestion complete: %s", result)
    return result


# ---------------------------------------------------------------------------
# __main__ – quick smoke test over Punjab, India
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Bounding box: a small farm polygon in the Ludhiana district, Punjab
    PUNJAB_BBOX = (75.85, 30.90, 75.95, 30.98)  # (minx, miny, maxx, maxy) WGS-84

    result = ingest_sentinel2(
        geometry_input=PUNJAB_BBOX,
        start_date="2024-10-01",
        end_date="2024-10-31",
        farm_id="punjab_farm_001",
        cloud_cover_threshold=0.20,
        output_dir=Path("data/satellite_tiles"),
    )
    print(json.dumps(result, indent=2))
