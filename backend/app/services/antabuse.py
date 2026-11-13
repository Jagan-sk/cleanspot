from datetime import timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Complaint, RateLimitRecord
from app.timeutils import utcnow


def is_rate_limited(db: Session, reporter_id: int | None, ip_address: str | None) -> bool:
    window_start = utcnow() - timedelta(hours=1)
    conditions = []
    if ip_address:
        conditions.append(RateLimitRecord.ip_address == ip_address)
    if reporter_id is not None:
        conditions.append(RateLimitRecord.reporter_id == reporter_id)
    if not conditions:
        conditions.append(RateLimitRecord.ip_address == "unknown")

    count = (
        db.query(RateLimitRecord)
        .filter(RateLimitRecord.created_at >= window_start)
        .filter(or_(*conditions))
        .count()
    )
    return count >= settings.REPORT_RATE_LIMIT_PER_HOUR


def record_submission(db: Session, reporter_id: int | None, ip_address: str | None):
    # Keep the anti-abuse table from growing forever; only the 1h window matters.
    cutoff = utcnow() - timedelta(hours=24)
    db.query(RateLimitRecord).filter(RateLimitRecord.created_at < cutoff).delete(
        synchronize_session=False
    )
    db.add(RateLimitRecord(reporter_id=reporter_id, ip_address=ip_address or "unknown"))
    db.commit()


def hash_exists(db: Session, photo_hash: str) -> bool:
    return db.query(Complaint).filter(Complaint.photo_hash == photo_hash).first() is not None
