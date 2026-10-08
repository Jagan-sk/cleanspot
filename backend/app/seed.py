from datetime import timedelta
from pathlib import Path

from PIL import Image, ImageDraw

from app.auth import hash_password, verify_password
from app.config import settings
from app.database import SessionLocal
from app.models import Complaint, StatusEvent, User
from app.timeutils import utcnow

SAMPLE_PHOTOS = {
    "uploads/sample_c1.jpg": ("#8fbf7f", "#4a7c3f", "SAMPLE REPORT #1"),
    "uploads/sample_c2.jpg": ("#a8c8e8", "#3a6ea5", "SAMPLE REPORT #2"),
}


def _ensure_sample_photo(rel_path: str, bg: str, bar: str, label: str) -> None:
    out = Path(settings.UPLOAD_DIR) / Path(rel_path).name
    if out.exists():
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (640, 480), bg)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 340, 640, 480], fill=bar)
    draw.rectangle([40, 60, 600, 300], outline=bar, width=8)
    draw.text((60, 380), label, fill="white")
    draw.text((60, 410), "CleanSpot demo seed image", fill="white")
    img.save(out, "JPEG", quality=85)


def _seed_users(db) -> None:
    """Create/refresh the demo accounts.

    - citizen / officer / admin (the legacy "officer" now patrols zone1)
    - officer_zone1 .. officer_zone4: one officer per SAMPLE zone

    Passwords come from the environment (see .env) - the README tells you to
    change them before any real use. Existing rows get their hash refreshed
    on startup so changing the env password actually applies.
    """
    demo = [
        # username, role, zone_id, password env value
        ("citizen", "citizen", None, settings.SEED_CITIZEN_PASSWORD),
        ("officer", "officer", "zone1", settings.SEED_OFFICER_PASSWORD),
        ("admin", "admin", None, settings.SEED_ADMIN_PASSWORD),
        ("officer_zone1", "officer", "zone1", settings.SEED_ZONE_OFFICER_PASSWORD),
        ("officer_zone2", "officer", "zone2", settings.SEED_ZONE_OFFICER_PASSWORD),
        ("officer_zone3", "officer", "zone3", settings.SEED_ZONE_OFFICER_PASSWORD),
        ("officer_zone4", "officer", "zone4", settings.SEED_ZONE_OFFICER_PASSWORD),
    ]
    for username, role, zone_id, password in demo:
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            db.add(User(username=username, role=role, zone_id=zone_id,
                        password_hash=hash_password(password)))
        else:
            user.role = role
            user.zone_id = zone_id
            # only re-hash when the stored hash does not match the env password
            # (keeps startup fast; changing the env password still applies)
            if not verify_password(password, user.password_hash or ""):
                user.password_hash = hash_password(password)
    db.commit()


def seed_data():
    db = SessionLocal()
    try:
        _seed_users(db)

        if db.query(Complaint).count() == 0:
            for rel, (bg, bar, label) in SAMPLE_PHOTOS.items():
                _ensure_sample_photo(rel, bg, bar, label)

            c1 = Complaint(
                photo_path="uploads/sample_c1.jpg",
                latitude=12.9762,
                longitude=77.6010,
                address="Sample address, Bangalore",
                created_at=utcnow() - timedelta(hours=5),
                category="Garbage dumping",
                waste_type="Mixed",
                status="Reported",
                ai_confidence=0.95,
                ai_decision="accepted",
                reporter_id=1,
            )
            c2 = Complaint(
                photo_path="uploads/sample_c2.jpg",
                latitude=12.9815,
                longitude=77.6083,
                address="Another location, Bangalore",
                created_at=utcnow() - timedelta(hours=2),
                category="Garbage dumping",
                waste_type="Plastic",
                status="Assigned",
                ai_confidence=0.98,
                ai_decision="accepted",
                reporter_id=1,
            )
            db.add_all([c1, c2])
            db.commit()
            db.refresh(c1)
            db.refresh(c2)

            db.add_all([
                StatusEvent(complaint_id=c1.id, status="Reported", actor="citizen"),
                StatusEvent(complaint_id=c2.id, status="Reported", actor="citizen"),
                StatusEvent(complaint_id=c2.id, status="Assigned", actor="officer"),
            ])
            db.commit()
    finally:
        db.close()
