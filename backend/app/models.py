from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base
from app.timeutils import utcnow


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    role = Column(String, default="citizen", nullable=False)  # citizen | officer | admin
    # bcrypt hash - never the plain password (NULL on very old rows)
    password_hash = Column(String, nullable=True)
    # officers only: which sample zone they patrol (NULL = no zone)
    zone_id = Column(String, nullable=True)


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    photo_path = Column(String, nullable=False)
    photo_hash = Column(String, nullable=True, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    category = Column(String, default="Garbage dumping", nullable=False)
    waste_type = Column(String, nullable=True)
    # Reported, Needs review, Assigned, Resolved, Confirmed, Reopened, Duplicate
    status = Column(String, default="Reported", nullable=False)
    duplicate_of = Column(Integer, ForeignKey("complaints.id"), nullable=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    ai_confidence = Column(Float, nullable=True)
    # "accepted" | "needs_review" | "needs_review_low_confidence" (NULL = old rows)
    ai_decision = Column(String, nullable=True)
    # sample zone from app/config/zones.json, or "unassigned" (NULL = old rows)
    zone_id = Column(String, nullable=True)

    events = relationship(
        "StatusEvent",
        back_populates="complaint",
        cascade="all, delete-orphan",
        order_by="StatusEvent.id",
    )


class StatusEvent(Base):
    __tablename__ = "status_events"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False, index=True)
    status = Column(String, nullable=False)
    timestamp = Column(DateTime, default=utcnow, nullable=False)
    actor = Column(String, nullable=True)
    photo = Column(String, nullable=True)
    # short officer note shown to the reporter (e.g. on resolve)
    note = Column(String, nullable=True)

    complaint = relationship("Complaint", back_populates="events")


class RateLimitRecord(Base):
    __tablename__ = "rate_limit_records"

    id = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    ip_address = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
