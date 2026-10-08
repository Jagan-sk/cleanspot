"""Admin-only endpoints: privacy / retention helpers."""
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_role
from app.config import settings
from app.database import get_db
from app.models import Complaint, StatusEvent, User

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN = require_role("admin")


def delete_complaint_completely(db: Session, complaint_id: int) -> int:
    """Remove a complaint, its status events and its photo files from disk.
    Returns the number of files deleted. Shared with scripts/purge_complaint.py."""
    c = db.get(Complaint, complaint_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Complaint not found")

    paths = [c.photo_path] + [e.photo for e in c.events if e.photo]
    db.query(StatusEvent).filter(StatusEvent.complaint_id == complaint_id).delete()
    db.delete(c)
    db.commit()

    deleted = 0
    for rel in paths:
        if not rel:
            continue
        fname = os.path.basename(rel)  # never trust stored path components
        abs_path = os.path.join(str(settings.UPLOAD_DIR), fname)
        try:
            os.remove(abs_path)
            deleted += 1
        except FileNotFoundError:
            pass
    return deleted


@router.delete("/complaints/{complaint_id}")
def admin_delete_complaint(
    complaint_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(ADMIN),
):
    """Privacy/retention: erase a complaint and all its photos (admin only)."""
    files = delete_complaint_completely(db, complaint_id)
    return {"deleted": True, "id": complaint_id, "files_removed": files}
