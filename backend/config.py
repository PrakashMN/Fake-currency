"""Application configuration and shared paths."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

FRONTEND_DIR = BASE_DIR / "frontend"
UPLOAD_DIR = BASE_DIR / "uploads"
REPORT_DIR = BASE_DIR / "reports"
MODEL_DIR = BASE_DIR / "models"

DB_PATH = BASE_DIR / "detections.db"
MODEL_PATH = MODEL_DIR / "currency_model.keras"
MODEL_META_PATH = MODEL_DIR / "class_names.json"

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
DENOMINATIONS = {"10", "20", "50", "100", "200", "500", "2000", "unknown"}

for directory in (UPLOAD_DIR, REPORT_DIR, MODEL_DIR):
    directory.mkdir(parents=True, exist_ok=True)
