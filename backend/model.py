"""Model loading and inference.

If a trained Keras model exists at ``models/currency_model.keras`` it is used.
Otherwise the app falls back to an explicitly-labelled demo mode so the full
web flow (upload -> result -> history -> report) stays testable.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import numpy as np
from PIL import Image

from .config import MODEL_META_PATH, MODEL_PATH

logger = logging.getLogger(__name__)

_model = None
_class_names: list[str] | None = None
_image_size: tuple[int, int] = (224, 224)
_load_attempted = False
_load_error: str | None = None

DEMO_WARNING = (
    "Demo mode: no trained model found, so this result is simulated and must "
    "not be treated as a real authenticity check."
)


def _normalise_label(name: str) -> str | None:
    value = name.strip().lower()
    if value in {"fake", "counterfeit", "forged", "invalid", "0"}:
        return "FAKE"
    if value in {"real", "genuine", "authentic", "valid", "1"}:
        return "REAL"
    return None


def _load_trained_model():
    global _model, _class_names, _image_size, _load_attempted, _load_error

    if _model is not None:
        return _model
    if _load_attempted:
        return None

    _load_attempted = True
    if not MODEL_PATH.exists():
        return None

    try:
        import tensorflow as tf  # lazy import: only needed for real inference

        _model = tf.keras.models.load_model(str(MODEL_PATH))
        input_shape = _model.input_shape
        if isinstance(input_shape, list):
            input_shape = input_shape[0]
        if input_shape and len(input_shape) >= 3 and input_shape[1] and input_shape[2]:
            _image_size = (int(input_shape[1]), int(input_shape[2]))

        if MODEL_META_PATH.exists():
            meta = json.loads(MODEL_META_PATH.read_text(encoding="utf-8"))
            names = meta.get("class_names") if isinstance(meta, dict) else meta
            if isinstance(names, list) and len(names) == 2:
                _class_names = [str(name) for name in names]
        if _class_names is None:
            # ``image_dataset_from_directory`` sorts class folders alphabetically.
            _class_names = ["fake", "real"]

        logger.info("Loaded trained model from %s", MODEL_PATH)
    except Exception as exc:  # pragma: no cover - depends on local ML install
        _model = None
        _load_error = str(exc)
        logger.warning(
            "Could not load trained model (%s). Falling back to demo mode.", exc
        )

    return _model


def _predict_trained(image_path: Path) -> dict:
    image = (
        Image.open(image_path)
        .convert("RGB")
        .resize(_image_size, Image.Resampling.LANCZOS)
    )
    array = np.asarray(image, dtype="float32")[None, ...]
    predictions = np.asarray(_model.predict(array, verbose=0))[0]

    if predictions.ndim == 0 or predictions.size == 1:
        probability_real = float(predictions.reshape(-1)[0])
        index = 1 if probability_real >= 0.5 else 0
        confidence = (
            probability_real if index == 1 else 1.0 - probability_real
        )
    else:
        index = int(np.argmax(predictions))
        confidence = float(predictions[index])

    label = None
    if _class_names and index < len(_class_names):
        label = _normalise_label(_class_names[index])
    if label is None:
        label = "REAL" if index == 1 else "FAKE"

    return {
        "result": label,
        "confidence": round(float(confidence), 4),
        "model_mode": "trained",
        "warning": None,
    }


def _predict_demo(image_path: Path) -> dict:
    digest = hashlib.sha256(image_path.read_bytes()).digest()
    score = digest[0] / 255.0
    result = "FAKE" if score < 0.5 else "REAL"
    confidence = round(0.52 + (digest[1] / 255.0) * 0.26, 4)
    return {
        "result": result,
        "confidence": confidence,
        "model_mode": "demo",
        "warning": DEMO_WARNING,
    }


def predict(image_path: Path) -> dict:
    model = _load_trained_model()
    if model is None:
        return _predict_demo(image_path)
    return _predict_trained(image_path)


def get_model_status() -> dict:
    model = _load_trained_model()
    trained = model is not None
    return {
        "mode": "trained" if trained else "demo",
        "model_file": MODEL_PATH.name if MODEL_PATH.exists() else None,
        "classes": _class_names or ["fake", "real"],
        "error": _load_error,
        "message": (
            "Trained model loaded."
            if trained
            else (_load_error or "No trained model found. Running in demo mode.")
        ),
    }
