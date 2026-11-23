"""FastAPI application for the Fake Currency Detector."""
from __future__ import annotations

import io
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError

from . import database, model, reports
from .config import (
    ALLOWED_EXTENSIONS,
    DENOMINATIONS,
    FRONTEND_DIR,
    MAX_UPLOAD_BYTES,
    UPLOAD_DIR,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    logger.info("Database ready")
    yield


app = FastAPI(
    title="Fake Currency Detector",
    description="Educational Indian currency authenticity detector.",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


def _save_upload(original_name: str, contents: bytes) -> tuple[Path, str]:
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Use JPG, PNG, WEBP, or BMP.",
        )
    if not contents:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413, detail="Image is too large (maximum 10 MB)."
        )

    try:
        image = Image.open(io.BytesIO(contents))
        image = ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(
            status_code=400, detail="The uploaded file is not a valid image."
        )

    image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    filename = f"{uuid.uuid4().hex}.jpg"
    destination = UPLOAD_DIR / filename
    image.save(destination, "JPEG", quality=90, optimize=True)
    return destination, filename


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/model")
def model_info():
    return model.get_model_status()


@app.get("/api/stats")
def stats():
    return database.get_stats()


@app.post("/api/detect")
async def detect(
    file: UploadFile = File(...),
    denomination: str = Form("unknown"),
):
    if denomination not in DENOMINATIONS:
        denomination = "unknown"

    contents = await file.read()
    image_path, image_filename = _save_upload(
        file.filename or "upload.jpg", contents
    )

    try:
        prediction = model.predict(image_path)
    except Exception:
        logger.exception("Prediction failed")
        image_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=500,
            detail="Could not analyse the image. Please try again.",
        )

    record = database.insert_detection(
        original_filename=file.filename or "upload.jpg",
        image_filename=image_filename,
        result=prediction["result"],
        confidence=prediction["confidence"],
        denomination=denomination,
        model_mode=prediction["model_mode"],
    )

    try:
        reports.create_report(record)
    except Exception:
        logger.exception("Failed to create report for detection %s", record["id"])

    return {**record, "warning": prediction.get("warning")}


@app.get("/api/detections")
def list_detections(
    result: str | None = Query(None, pattern="^(REAL|FAKE)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    items, total = database.list_detections(
        result=result, limit=limit, offset=offset
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@app.get("/api/detections/{detection_id}")
def get_detection(detection_id: int):
    record = database.get_detection(detection_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Detection not found.")
    return record


@app.delete("/api/detections/{detection_id}")
def delete_detection(detection_id: int):
    record = database.delete_detection(detection_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Detection not found.")

    (UPLOAD_DIR / record["image_filename"]).unlink(missing_ok=True)
    reports.report_path(detection_id).unlink(missing_ok=True)
    return {"deleted": True, "id": detection_id}


@app.get("/api/detections/{detection_id}/report")
def download_report(detection_id: int):
    record = database.get_detection(detection_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Detection not found.")

    path = reports.report_path(detection_id)
    if not path.exists():
        reports.create_report(record)

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"detection_report_{detection_id:04d}.pdf",
    )
