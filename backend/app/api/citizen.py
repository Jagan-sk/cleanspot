from typing import Optional

import os

from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import actor_name, get_current_user
from app.config import settings
from app.database import get_db
from app.models import Complaint, StatusEvent, User
from app.schemas import ComplaintResponse, ComplaintDetail
from app.services.antabuse import hash_exists, is_rate_limited, record_submission
from app.services.duplicates import find_duplicate
from app.services.sanitizer import InvalidImageError, sanitize_upload
from app.services.verifier import verify_image
from app.zones import can_access, zone_for

router = APIRouter(prefix="/api/citizen", tags=["citizen"])

# what the app allows the citizen to pick (privacy: collect only what we need)
WASTE_TYPES = {"Mixed", "Plastic", "Organic", "Construction", "Hazardous"}
MAX_ADDRESS_LENGTH = 300
MAX_NOTE_LENGTH = 500


def save_upload(file: UploadFile) -> tuple[str, str, str]:
    """Read, validate and re-encode an uploaded photo (see services/sanitizer.py).
    Returns (absolute_path, sha256, filename)."""
    # read in chunks so an oversized upload is never fully buffered
    max_bytes = settings.max_upload_size_bytes
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = file.file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status_code=400, detail="Image too large")
        chunks.append(chunk)
    content = b"".join(chunks)
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        return sanitize_upload(content, str(settings.UPLOAD_DIR))
    except InvalidImageError:
        raise HTTPException(status_code=400, detail="File is not a valid image")


def _accessible_complaint(db: Session, complaint_id: int, user: User) -> Complaint:
    """Zone/ownership rules are enforced here (see app/zones.py):
    citizens only their own (403), officers only their zone, admins all."""
    c = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found")
    if not can_access(user, c):
        raise HTTPException(status_code=403, detail="Not your complaint")
    return c


def _validate_text_inputs(address: Optional[str], waste_type: Optional[str], category: str):
    if address and len(address) > MAX_ADDRESS_LENGTH:
        raise HTTPException(status_code=400, detail="Address is too long")
    if waste_type and waste_type not in WASTE_TYPES:
        raise HTTPException(status_code=400, detail="Unknown waste type")
    if category and len(category) > 100:
        raise HTTPException(status_code=400, detail="Category is too long")


@router.post("/submit", response_model=ComplaintResponse)
async def submit_report(
    request: Request,
    latitude: float = Form(...),
    longitude: float = Form(...),
    address: Optional[str] = Form(None),
    category: str = Form("Garbage dumping"),
    waste_type: Optional[str] = Form(None),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise HTTPException(status_code=400, detail="Invalid coordinates")
    _validate_text_inputs(address, waste_type, category)

    # identity always comes from the token, never from the form
    reporter_id = user.id
    client_ip = request.client.host if request.client else "unknown"

    if is_rate_limited(db, reporter_id, client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    # every attempt that passes the limiter counts, including later rejections
    record_submission(db, reporter_id, client_ip)

    abs_path, content_hash, fname = save_upload(image)
    rel_store = f"uploads/{fname}"  # NOT served publicly anymore

    # hash dedup (reject if same photo content already submitted)
    if hash_exists(db, content_hash):
        os.remove(abs_path)
        raise HTTPException(status_code=400, detail="Duplicate photo already submitted")

    # AI verify (never rejects - low confidence just flags human review)
    ai = verify_image(abs_path)
    confidence = ai.get("confidence", 0.0)
    decision = ai.get("decision", "needs_review")

    # check duplicates by location (30 m): link via duplicate_of instead of
    # creating another open item
    dup = find_duplicate(db, latitude, longitude, max_dist_m=30.0)
    if dup:
        c = Complaint(
            photo_path=rel_store,
            photo_hash=content_hash,
            latitude=latitude,
            longitude=longitude,
            address=address,
            category=category,
            waste_type=waste_type,
            status="Duplicate",
            duplicate_of=dup.id,
            reporter_id=reporter_id,
            ai_confidence=confidence,
            ai_decision=decision,
            zone_id=zone_for(latitude, longitude),
        )
        db.add(c)
        db.flush()  # assign c.id before creating the event
        db.add(StatusEvent(complaint_id=c.id, status="Duplicate", actor="system"))
        db.commit()
        db.refresh(c)
        return c

    # only an "accepted" photo skips human review
    initial_status = "Reported" if decision == "accepted" else "Needs review"

    c = Complaint(
        photo_path=rel_store,
        photo_hash=content_hash,
        latitude=latitude,
        longitude=longitude,
        address=address,
        category=category,
        waste_type=waste_type,
        status=initial_status,
        ai_confidence=confidence,
        ai_decision=decision,
        reporter_id=reporter_id,
        zone_id=zone_for(latitude, longitude),
    )
    db.add(c)
    db.flush()
    db.add(StatusEvent(complaint_id=c.id, status=initial_status, actor=actor_name(db, user)))
    db.commit()
    db.refresh(c)
    return c


@router.get("/complaints", response_model=list[ComplaintResponse])
def my_reports(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Every user sees only their OWN complaints here (officers use /municipal)."""
    return (
        db.query(Complaint)
        .filter(Complaint.reporter_id == user.id)
        .order_by(Complaint.created_at.desc(), Complaint.id.desc())
        .all()
    )


@router.get("/complaints/{complaint_id}", response_model=ComplaintDetail)
def complaint_detail(
    complaint_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _accessible_complaint(db, complaint_id, user)


@router.post("/complaints/{complaint_id}/confirm", response_model=ComplaintResponse)
async def confirm_cleanup(
    complaint_id: int,
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = _accessible_complaint(db, complaint_id, user)
    if user.role != "citizen":
        raise HTTPException(status_code=403, detail="Only the reporter can confirm cleanup")
    if c.status != "Resolved":
        raise HTTPException(status_code=400, detail="Complaint not resolved yet")

    after_photo = None
    if image is not None and image.filename:
        abs_path, _h, fname = save_upload(image)
        after_photo = f"uploads/{fname}"  # kept on the event; original photo preserved

    c.status = "Confirmed"
    db.add(
        StatusEvent(
            complaint_id=c.id,
            status="Confirmed",
            actor=actor_name(db, user),
            photo=after_photo,
        )
    )
    db.commit()
    db.refresh(c)
    return c


@router.post("/complaints/{complaint_id}/reopen", response_model=ComplaintResponse)
def reopen(
    complaint_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = _accessible_complaint(db, complaint_id, user)
    if c.status not in ("Resolved", "Confirmed"):
        raise HTTPException(status_code=400, detail="Cannot reopen unless resolved")
    c.status = "Reopened"
    db.add(StatusEvent(complaint_id=c.id, status="Reopened", actor=actor_name(db, user)))
    db.commit()
    db.refresh(c)
    return c
