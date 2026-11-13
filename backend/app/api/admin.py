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


def _duplicate_tree_ids(db: Session, root_id: int) -> set[int]:
    """All complaint ids that (directly or transitively) point at root_id via
    duplicate_of. Deleting the original must clean these children up too,
    otherwise SQLite's foreign-key check refuses the DELETE."""
    ids = {root_id}
    frontier = [root_id]
    while frontier:
        rows = db.query(Complaint.id).filter(Complaint.duplicate_of.in_(frontier)).all()
        new_ids = {row[0] for row in rows} - ids
        if not new_ids:
            break
        ids.update(new_ids)
        frontier = list(new_ids)
    return ids


def delete_complaint_completely(db: Session, complaint_id: int) -> int:
    """Remove a complaint, its linked duplicate reports, their status events and
    photo files from disk. Returns the number of files deleted.
    Shared with scripts/purge_complaint.py."""
    c = db.get(Complaint, complaint_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Complaint not found")

    ids = _duplicate_tree_ids(db, complaint_id)
    complaints = db.query(Complaint).filter(Complaint.id.in_(ids)).all()
    events = db.query(StatusEvent).filter(StatusEvent.complaint_id.in_(ids)).all()

    paths = {cc.photo_path for cc in complaints if cc.photo_path}
    paths.update(e.photo for e in events if e.photo)

    # Break the self-referencing duplicate links first so the bulk DELETE
    # cannot violate the duplicate_of foreign key, then remove rows.
    db.query(Complaint).filter(Complaint.duplicate_of.in_(ids)).update(
        {Complaint.duplicate_of: None}, synchronize_session=False
    )
    db.query(StatusEvent).filter(StatusEvent.complaint_id.in_(ids)).delete(
        synchronize_session=False
    )
    db.query(Complaint).filter(Complaint.id.in_(ids)).delete(synchronize_session=False)
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
