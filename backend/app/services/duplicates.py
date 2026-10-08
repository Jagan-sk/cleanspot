import math
from sqlalchemy.orm import Session
from app.models import Complaint


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000  # meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def find_duplicate(db: Session, lat: float, lon: float, max_dist_m: float = 30.0) -> Complaint | None:
    # Look for open complaints (not resolved/confirmed/closed) within distance
    for c in db.query(Complaint).filter(
        Complaint.status.in_(["Reported", "Assigned", "Reopened", "Needs review"])
    ):
        if haversine_distance(lat, lon, c.latitude, c.longitude) <= max_dist_m:
            return c
    return None
