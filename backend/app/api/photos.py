"""Authenticated photo serving.

Uploads are NOT a public static folder anymore. Every photo is fetched
through this endpoint with a valid token:

    GET /api/photos/{complaint_id}/{kind}     kind: report | cleanup | after

- report  -> the original complaint photo
- after   -> the most recent "after" photo (officer resolve photo or the
             reporter's own confirm photo)
- cleanup -> alias of "after" (kept for clarity)

Allowed: the complaint's owner, officers and admins.
(Zone-restricted officers arrive in Phase 2.)
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import Complaint, StatusEvent, User
from app.zones import can_access

import os

router = APIRouter(tags=["photos"])

KINDS = {"report", "cleanup", "after"}
_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
# status events that may carry an "after" photo
_AFTER_STATUSES = ("Resolved", "Confirmed")


def _media_type(path: str) -> str:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return _MEDIA_TYPES.get("." + ext, "application/octet-stream")


def _file_response(rel_path: str):
    """Stream a stored upload file (path is basename-sanitised)."""
    fname = os.path.basename(rel_path)  # never trust stored path components
    abs_path = os.path.join(str(settings.UPLOAD_DIR), fname)
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail="Photo file missing")
    return FileResponse(
        abs_path,
        media_type=_media_type(fname),
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.get("/api/photos/event/{event_id}")
def get_event_photo(
    event_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """A photo attached to a specific status event (timeline view)."""
    e = db.get(StatusEvent, event_id)
    if e is None or not e.photo:
        raise HTTPException(status_code=404, detail="No photo")
    c = db.get(Complaint, e.complaint_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Complaint not found")
    if not can_access(user, c):
        raise HTTPException(status_code=403, detail="Not your complaint")
    return _file_response(e.photo)


@router.get("/api/photos/{complaint_id}/{kind}")
def get_photo(
    complaint_id: int,
    kind: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if kind not in KINDS:
        raise HTTPException(status_code=400, detail="Unknown photo kind")

    c = db.get(Complaint, complaint_id)
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found")

    # owner / same-zone officer / admin only (Phase 2 zones)
    if not can_access(user, c):
        raise HTTPException(status_code=403, detail="Not your complaint")

    if kind == "report":
        rel_path = c.photo_path
    else:
        # newest after/cleanup confirmation photo from the event history
        rel_path = (
            db.query(StatusEvent)
            .filter(
                StatusEvent.complaint_id == complaint_id,
                StatusEvent.status.in_(_AFTER_STATUSES),
                StatusEvent.photo.isnot(None),
            )
            .order_by(StatusEvent.id.desc())
            .first()
        )
        rel_path = rel_path.photo if rel_path else None

    if not rel_path:
        raise HTTPException(status_code=404, detail="No photo")

    return _file_response(rel_path)
