from typing import Optional

import httpx

from app.config import settings


def forward_complaint(complaint_data: dict, cleanup_photo_path: Optional[str] = None) -> dict:
    """
    Forward complaint to municipal server.
    This is the ONLY place that calls municipal routes. Base URL comes from
    MUNICIPAL_BASE_URL env var so it can point to real system later.
    """
    base = settings.MUNICIPAL_BASE_URL.rstrip("/")
    url = f"{base}/complaints"
    payload = complaint_data.copy()
    if cleanup_photo_path:
        payload["cleanup_photo"] = cleanup_photo_path
    try:
        resp = httpx.post(url, json=payload, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        # Graceful fallback - return simulated response if municipal server unreachable
        return {"id": complaint_data.get("id"), "status": "forwarded_simulated", "error": str(e)}


def get_municipal_status(complaint_id: int) -> dict:
    base = settings.MUNICIPAL_BASE_URL.rstrip("/")
    url = f"{base}/complaints/{complaint_id}"
    try:
        resp = httpx.get(url, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"id": complaint_id, "status": "unknown", "error": str(e)}
