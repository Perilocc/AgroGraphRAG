from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

STRUCTURED_DIR = DATA_DIR / "structured"
UNSTRUCTURED_DIR = DATA_DIR / "unstructured"
METADATA_DIR = DATA_DIR / "metadata"

PROCESSED_DIR = DATA_DIR / "processed"
EXTRACTED_DIR = DATA_DIR / "extracted"
