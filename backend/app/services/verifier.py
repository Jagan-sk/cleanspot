"""
AI verification for uploaded photos.

Uses the trained TorchScript model (MobileNetV2, 2 classes):
    index 0 = not_garbage, index 1 = garbage
The model is loaded once and cached for the lifetime of the process.

A complaint is NEVER rejected automatically - low confidence photos are
accepted into the system and flagged for human review instead.
"""

import logging

from PIL import Image, ImageOps

from app.config import settings

logger = logging.getLogger("cleanspot.verifier")

# ImageNet preprocessing values - must match training exactly
MEAN = [0.485, 0.456, 0.406]
STD = [0.229, 0.224, 0.225]
IMG_SIZE = (224, 224)

# module-level cache: the model is loaded on first use, then reused
_MODEL = None
_MODEL_ERROR = False


def preprocess_image(image_path: str):
    """Load an image the same way training did -> FloatTensor (3, 224, 224).

    1. open with PIL, honour EXIF rotation, convert to RGB
       (this also drops the alpha channel from PNGs)
    2. resize to 224x224
    3. ToTensor (scales pixels to 0..1)
    4. normalize with the ImageNet mean/std
    """
    from torchvision import transforms  # imported here so tests can run without torch

    with Image.open(image_path) as img:
        img = ImageOps.exif_transpose(img)  # fix rotated phone photos
        img = img.convert("RGB")            # RGBA/P -> RGB
        img = img.resize(IMG_SIZE)

    tf = transforms.Compose(
        [
            transforms.ToTensor(),
            transforms.Normalize(mean=MEAN, std=STD),
        ]
    )
    return tf(img).unsqueeze(0)  # add batch dimension -> (1, 3, 224, 224)


def decide(confidence: float, auto_accept: float, review_below: float) -> str:
    """Map a confidence value to a decision string.

    accepted                    : confidence >= auto_accept
    needs_review                : review_below <= confidence < auto_accept
    needs_review_low_confidence : confidence < review_below

    If the configured thresholds are nonsense we fall back to the older
    AI_CONFIDENCE_THRESHOLD setting instead of crashing.
    """
    if not (0.0 < review_below < auto_accept <= 1.0):
        logger.warning(
            "Invalid AUTO_ACCEPT/REVIEW_BELOW thresholds "
            "(%s/%s), falling back to AI_CONFIDENCE_THRESHOLD=%s",
            auto_accept,
            review_below,
            settings.AI_CONFIDENCE_THRESHOLD,
        )
        return (
            "accepted"
            if confidence >= settings.AI_CONFIDENCE_THRESHOLD
            else "needs_review"
        )

    if confidence >= auto_accept:
        return "accepted"
    if confidence >= review_below:
        return "needs_review"
    return "needs_review_low_confidence"


def _get_model():
    """Load the TorchScript model once (CPU, eval mode); cache it."""
    global _MODEL, _MODEL_ERROR

    if _MODEL is not None:
        return _MODEL
    if _MODEL_ERROR:
        return None  # already failed once, do not retry every upload

    try:
        import torch

        path = settings.resolved_model_path
        model = torch.jit.load(str(path), map_location="cpu")
        model.eval()
        _MODEL = model
        logger.info("Loaded garbage classifier from %s", path)
        return _MODEL
    except Exception as exc:  # missing file, bad file, torch not installed...
        _MODEL_ERROR = True
        logger.error("Could not load model '%s': %s", settings.resolved_model_path, exc)
        return None


def _predict_garbage_prob(image_path: str) -> float:
    """Run inference and return P(garbage), the probability of class 1."""
    import torch

    model = _get_model()
    if model is None:
        raise RuntimeError("model unavailable")

    tensor = preprocess_image(image_path)
    with torch.no_grad():
        logits = model(tensor)          # shape (1, 2)
        probs = torch.softmax(logits, dim=1)[0]  # shape (2,)
    return float(probs[1])              # class 1 = garbage


def verify_image(image_path: str) -> dict:
    """Classify a photo and decide what happens to the complaint.

    Returns:
        {"is_garbage": bool,
         "confidence": float  (rounded to 3 dp, = P(class 1 = garbage)),
         "waste_type": None   (reserved for a future multi-class model),
         "decision": "accepted" | "needs_review" | "needs_review_low_confidence"}
    """
    fallback = {
        "is_garbage": False,
        "confidence": 0.0,
        "waste_type": None,
        "decision": "needs_review",  # submissions keep working, human looks at it
    }

    try:
        confidence = round(_predict_garbage_prob(image_path), 3)
        decision = decide(
            confidence,
            auto_accept=settings.AUTO_ACCEPT,
            review_below=settings.REVIEW_BELOW,
        )
        return {
            "is_garbage": confidence >= 0.5,  # the model's raw yes/no answer
            "confidence": confidence,
            "waste_type": None,
            "decision": decision,
        }
    except Exception as exc:
        logger.error("AI verification failed for %s: %s", image_path, exc)
        return fallback
