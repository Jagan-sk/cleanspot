from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict


class ComplaintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    photo_path: str
    latitude: float
    longitude: float
    address: Optional[str] = None
    created_at: datetime
    category: str
    waste_type: Optional[str] = None
    status: str
    duplicate_of: Optional[int] = None
    reporter_id: Optional[int] = None
    ai_confidence: Optional[float] = None
    ai_decision: Optional[str] = None
    zone_id: Optional[str] = None


class StatusEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    complaint_id: int
    status: str
    timestamp: datetime
    actor: Optional[str] = None
    photo: Optional[str] = None
    note: Optional[str] = None


class ComplaintDetail(ComplaintResponse):
    events: List[StatusEventResponse] = []
