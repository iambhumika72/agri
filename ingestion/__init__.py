# ingestion package
# ---------------------------------------------------------------------------
# Imports are kept lazy (inside __getattr__) so that heavyweight optional
# dependencies (rasterio, shapely, etc.) are only loaded when explicitly
# accessed.  This allows lightweight modules like farmer_input_ingestion to
# be imported without requiring the full geospatial stack.
# ---------------------------------------------------------------------------

__all__ = [
    "ingest_sentinel2",
    "compute_indices",
    "IndexResult",
    "detect_change",
    "ChangeResult",
]


def __getattr__(name: str):
    if name == "ingest_sentinel2":
        from ingestion.satellite_ingestor import ingest_sentinel2
        return ingest_sentinel2
    if name in ("compute_indices", "IndexResult"):
        import ingestion.spectral_indices as _si
        return getattr(_si, name)
    if name in ("detect_change", "ChangeResult"):
        import ingestion.change_detection as _cd
        return getattr(_cd, name)
    raise AttributeError(f"module 'ingestion' has no attribute {name!r}")
