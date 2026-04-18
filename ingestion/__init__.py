# ingestion package
from ingestion.satellite_ingestor import ingest_sentinel2
from ingestion.spectral_indices import compute_indices, IndexResult
from ingestion.change_detection import detect_change, ChangeResult

__all__ = [
    "ingest_sentinel2",
    "compute_indices",
    "IndexResult",
    "detect_change",
    "ChangeResult",
]
