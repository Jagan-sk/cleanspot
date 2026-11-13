"""Tests for the AI verifier: thresholds, fallback, preprocessing, storage."""

import torch
from PIL import Image

from app.config import settings
from app.services import verifier
from tests.helpers import CITIZEN, submit


# ---------- decision thresholds (pure function) ----------

def test_accepted_at_and_above_auto_accept():
    assert verifier.decide(0.80, 0.80, 0.50) == "accepted"
    assert verifier.decide(0.99, 0.80, 0.50) == "accepted"


def test_needs_review_between_thresholds():
    assert verifier.decide(0.79, 0.80, 0.50) == "needs_review"
    assert verifier.decide(0.50, 0.80, 0.50) == "needs_review"


def test_low_confidence_below_review_below():
    assert verifier.decide(0.49, 0.80, 0.50) == "needs_review_low_confidence"
    assert verifier.decide(0.0, 0.80, 0.50) == "needs_review_low_confidence"


def test_invalid_thresholds_fall_back_to_ai_confidence_threshold(monkeypatch):
    monkeypatch.setattr(settings, "AI_CONFIDENCE_THRESHOLD", 0.7)
    # review_below >= auto_accept is nonsense -> old threshold takes over
    assert verifier.decide(0.70, 0.50, 0.80) == "accepted"
    assert verifier.decide(0.69, 0.50, 0.80) == "needs_review"


# ---------- verify_image with mocked model output ----------

def _make_image(tmp_path, name="pic.jpg", color=(10, 200, 10), fmt="JPEG"):
    path = tmp_path / name
    Image.new("RGB", (300, 240), color).save(path, fmt)
    return str(path)


def test_verify_image_with_mocked_probabilities(tmp_path, monkeypatch):
    cases = [
        (0.92, "accepted", True),
        (0.61, "needs_review", True),
        (0.31, "needs_review_low_confidence", False),
    ]
    for prob, expected_decision, expected_garbage in cases:
        monkeypatch.setattr(verifier, "_predict_garbage_prob", lambda p, v=prob: v)
        result = verifier.verify_image(_make_image(tmp_path))
        assert result["decision"] == expected_decision
        assert result["confidence"] == prob
        assert result["is_garbage"] is expected_garbage
        assert result["waste_type"] is None


def test_missing_model_file_falls_back(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "MODEL_PATH", tmp_path / "does_not_exist.pt")
    verifier._MODEL = None
    verifier._MODEL_ERROR = False
    try:
        result = verifier.verify_image(_make_image(tmp_path, "fallback.png", fmt="PNG"))
    finally:
        verifier._MODEL = None
        verifier._MODEL_ERROR = False
    assert result["decision"] == "needs_review"
    assert result["confidence"] == 0.0
    assert result["is_garbage"] is False


# ---------- preprocessing ----------

def test_preprocess_rotated_jpeg(tmp_path):
    path = tmp_path / "rotated.jpg"
    img = Image.new("RGB", (400, 300), (200, 30, 30))
    exif = img.getexif()
    exif[0x0112] = 6  # EXIF orientation tag: image needs a 90 degree rotation
    img.save(path, exif=exif)

    tensor = verifier.preprocess_image(str(path))
    assert tensor.shape == (1, 3, 224, 224)
    assert tensor.dtype == torch.float32
    assert torch.isfinite(tensor).all()


def test_preprocess_png_with_transparency(tmp_path):
    path = tmp_path / "alpha.png"
    Image.new("RGBA", (100, 80), (0, 255, 0, 128)).save(path)

    tensor = verifier.preprocess_image(str(path))
    assert tensor.shape == (1, 3, 224, 224)
    assert tensor.dtype == torch.float32


# ---------- decision is stored on the complaint ----------

def test_submit_stores_accepted_decision(client, monkeypatch):
    from app.api import citizen as citizen_api

    monkeypatch.setattr(
        citizen_api,
        "verify_image",
        lambda p: {"is_garbage": True, "confidence": 0.91, "waste_type": None, "decision": "accepted"},
    )
    body = submit(client, color=(31, 181, 91)).json()
    assert body["ai_decision"] == "accepted"
    assert body["ai_confidence"] == 0.91
    assert body["status"] == "Reported"  # accepted skips human review


def test_reject_non_garbage_is_opt_in(client, monkeypatch):
    from app.api import citizen as citizen_api

    monkeypatch.setattr(settings, "REJECT_NON_GARBAGE", True)
    monkeypatch.setattr(
        citizen_api,
        "verify_image",
        lambda p: {"is_garbage": False, "confidence": 0.1, "waste_type": None,
                   "decision": "needs_review_low_confidence"},
    )
    r = submit(client, color=(33, 183, 93))
    assert r.status_code == 422
    assert "does not appear to contain garbage" in r.json()["detail"]
    assert client.get("/api/citizen/complaints", headers=CITIZEN).json() == []


def test_submit_stores_low_confidence_and_flags_review(client, monkeypatch):
    from app.api import citizen as citizen_api

    monkeypatch.setattr(
        citizen_api,
        "verify_image",
        lambda p: {"is_garbage": False, "confidence": 0.22, "waste_type": None,
                   "decision": "needs_review_low_confidence"},
    )
    body = submit(client, color=(32, 182, 92)).json()
    assert body["ai_decision"] == "needs_review_low_confidence"
    assert body["ai_confidence"] == 0.22
    assert body["status"] == "Needs review"  # never rejected, just flagged