"""Sample ward zones (Phase 2).

The rectangles live in app/config/zones.json - SAMPLE zones for the demo,
not real municipal ward boundaries. Edit the JSON and restart the backend
to change them.

A complaint's zone is computed from its latitude/longitude at submission
time; points outside every rectangle get zone "unassigned".
"""
import json
from functools import lru_cache
from pathlib import Path

ZONES_FILE = Path(__file__).resolve().parent / "config" / "zones.json"
UNASSIGNED = "unassigned"


@lru_cache(maxsize=1)
def load_zones() -> tuple[dict, ...]:
    """Read zones.json once at startup (restart after editing the file)."""
    data = json.loads(ZONES_FILE.read_text())
    return tuple(data.get("zones", []))


def zone_ids() -> set[str]:
    return {z["id"] for z in load_zones()}


def zone_for(latitude: float, longitude: float) -> str:
    """Which sample zone contains this point? ("unassigned" if none)."""
    for z in load_zones():
        if (
            z["min_lat"] <= latitude <= z["max_lat"]
            and z["min_lng"] <= longitude <= z["max_lng"]
        ):
            return z["id"]
    return UNASSIGNED


def can_access(user, complaint) -> bool:
    """Server-side zone/ownership rules (Phase 2):
    - admin: everything
    - officer: only complaints inside their OWN zone (never "unassigned")
    - citizen: only their own complaints
    """
    if user.role == "admin":
        return True
    if user.role == "officer":
        return bool(user.zone_id) and complaint.zone_id == user.zone_id and complaint.zone_id != UNASSIGNED
    return complaint.reporter_id == user.id
