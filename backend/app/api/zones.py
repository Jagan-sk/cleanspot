"""Zone list for the frontend (map rectangles, headers, dropdowns)."""
from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.models import User
from app.zones import load_zones

router = APIRouter(prefix="/api", tags=["zones"])


@router.get("/zones")
def list_zones(user: User = Depends(get_current_user)):
    """The SAMPLE zones from app/config/zones.json (restart after editing)."""
    return {"zones": list(load_zones())}
