from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.citizen import MAX_NOTE_LENGTH, save_upload
from app.auth import actor_name, require_role
from app.database import get_db
from app.models import Complaint, StatusEvent, User
from app.schemas import ComplaintResponse
from app.zones import UNASSIGNED, can_access, load_zones, zone_ids

router = APIRouter(prefix="/municipal", tags=["municipal"])

OFFICERS = require_role("officer", "admin")


def _zone_filter_or_400(zone: str | None) -> str | None:
    """Admin-only ?zone= parameter: a known zone id, "unassigned", or None/"all"."""
    if not zone or zone == "all":
        return None
    if zone not in zone_ids() and zone != UNASSIGNED:
        raise HTTPException(status_code=400, detail="Unknown zone")
    return zone


def _assert_zone_access(user: User, c: Complaint) -> None:
    """403 unless this officer/admin may act on this complaint (Phase 2 zones)."""
    if not can_access(user, c):
        raise HTTPException(status_code=403, detail="Complaint is not in your zone")


@router.post("/complaints")
def receive_complaint(payload: dict, user: User = Depends(OFFICERS)):
    # Simulated municipal inbox (called by services/integration.py in production).
    # Phase 1: requires an officer/admin token - no more public injection.
    return {"received": True, "id": payload.get("id")}


@router.get("/complaints", response_model=list[ComplaintResponse])
def list_complaints(
    zone: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(OFFICERS),
):
    """Officers see ONLY their own zone; admins see everything and can filter
    with ?zone=<id> (including zone=unassigned)."""
    q = db.query(Complaint)
    if user.role == "admin":
        wanted = _zone_filter_or_400(zone)
        if wanted:
            q = q.filter(Complaint.zone_id == wanted)
    else:
        if not user.zone_id:
            return []  # officer with no zone assigned sees nothing
        q = q.filter(Complaint.zone_id == user.zone_id).filter(Complaint.zone_id != UNASSIGNED)
    return q.order_by(Complaint.created_at.desc(), Complaint.id.desc()).all()


@router.get("/complaints/{complaint_id}")
def get_complaint_status(
    complaint_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(OFFICERS),
):
    c = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found")
    _assert_zone_access(user, c)
    events = (
        db.query(StatusEvent)
        .filter(StatusEvent.complaint_id == complaint_id)
        .order_by(StatusEvent.timestamp, StatusEvent.id)
        .all()
    )
    return {
        "id": c.id,
        "status": c.status,
        "history": [
            {
                "status": e.status,
                "timestamp": e.timestamp,
                "actor": e.actor,
                "photo": e.photo,
            }
            for e in events
        ],
    }


@router.post("/complaints/{complaint_id}/assign")
def assign_complaint(
    complaint_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(OFFICERS),
):
    c = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found")
    _assert_zone_access(user, c)
    if c.status in ("Resolved", "Confirmed"):
        raise HTTPException(status_code=400, detail="Already resolved")
    if c.status == "Duplicate":
        raise HTTPException(status_code=400, detail="Duplicate report; act on the original complaint")
    if c.status == "Assigned":
        return {"id": complaint_id, "status": c.status}
    c.status = "Assigned"
    db.add(StatusEvent(complaint_id=complaint_id, status="Assigned", actor=actor_name(db, user)))
    db.commit()
    return {"id": complaint_id, "status": c.status}


@router.post("/complaints/{complaint_id}/resolve")
async def resolve_complaint(
    complaint_id: int,
    note: Optional[str] = Form(None),
    # optional "after" photo proving the cleanup is done - the reporter sees it
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(OFFICERS),
):
    c = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found")
    _assert_zone_access(user, c)
    if c.status == "Duplicate":
        raise HTTPException(status_code=400, detail="Duplicate report; act on the original complaint")
    if c.status == "Confirmed":
        raise HTTPException(status_code=400, detail="Already confirmed by the reporter")

    has_photo = photo is not None and bool(photo.filename)
    if note and len(note) > MAX_NOTE_LENGTH:
        raise HTTPException(status_code=400, detail="Note is too long")

    after_photo = None
    if has_photo:
        # reuses the same validation/re-encode/strip pipeline as reports
        _abs_path, _h, fname = save_upload(photo)
        after_photo = f"uploads/{fname}"

    if c.status == "Resolved":
        # already resolved: only allowed to ATTACH a late after-photo
        if not has_photo:
            return {"id": complaint_id, "status": c.status}
    else:
        c.status = "Resolved"

    db.add(
        StatusEvent(
            complaint_id=complaint_id,
            status="Resolved",
            actor=actor_name(db, user),
            photo=after_photo,
            note=note,
        )
    )
    db.commit()
    return {"id": complaint_id, "status": c.status, "after_photo": after_photo}
