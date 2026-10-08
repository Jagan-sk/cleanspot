from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Complaint, User
from app.timeutils import utcnow
from app.zones import UNASSIGNED, zone_ids

router = APIRouter(prefix="/api", tags=["stats"])

DONE_STATUSES = ("Resolved", "Confirmed")
MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MAX_AREAS = 8
MAX_MONTH_AREAS = 5


def area_label(c: Complaint) -> str:
    """Grouping key for an area: street/locality part of the address, else a coord bucket."""
    if c.address:
        first = c.address.split(",")[0].strip()
        tokens = first.split()
        while tokens and tokens[0].isdigit():
            tokens.pop(0)
        label = " ".join(tokens)
        if label:
            return label
    return f"Near {c.latitude:.2f}, {c.longitude:.2f}"


def category_label(c: Complaint) -> str:
    return c.waste_type or c.category or "Other"


def top_counts(counter: Counter, limit: int, key_name: str) -> list[dict]:
    ranked = sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0])))
    return [{key_name: k, "count": v} for k, v in ranked[:limit]]


@router.get("/stats")
def complaint_stats(
    months: int = Query(8, ge=2, le=24),
    zone: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Aggregated statistics for the dashboard.

    Zone scoping (Phase 2): officers always see THEIR zone only; admins can
    pass ?zone=<id> (including "unassigned"); citizens see the global numbers.
    """
    complaints = db.query(Complaint).all()

    if user.role == "officer":
        complaints = [c for c in complaints if c.zone_id == user.zone_id]
    elif user.role == "admin" and zone and zone != "all":
        if zone not in zone_ids() and zone != UNASSIGNED:
            raise HTTPException(status_code=400, detail="Unknown zone")
        complaints = [c for c in complaints if c.zone_id == zone]

    now = utcnow()

    # last N month keys, ascending, including the current (possibly empty) month
    keys: list[str] = []
    y, m = now.year, now.month
    for _ in range(months):
        keys.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    keys.reverse()

    by_month: dict[str, list[Complaint]] = {k: [] for k in keys}
    for c in complaints:
        k = f"{c.created_at.year:04d}-{c.created_at.month:02d}"
        if k in by_month:
            by_month[k].append(c)

    monthly = []
    for k in keys:
        items = by_month[k]
        monthly.append(
            {
                "key": k,
                "label": MONTH_LABELS[int(k[5:7]) - 1],
                "count": len(items),
                "done": sum(1 for c in items if c.status in DONE_STATUSES),
                "areas": top_counts(Counter(area_label(c) for c in items), MAX_MONTH_AREAS, "area"),
                "categories": top_counts(
                    Counter(category_label(c) for c in items), MAX_MONTH_AREAS, "name"
                ),
            }
        )

    all_areas = top_counts(Counter(area_label(c) for c in complaints), MAX_AREAS, "area")
    all_categories = top_counts(Counter(category_label(c) for c in complaints), MAX_AREAS, "name")

    open_count = sum(1 for c in complaints if c.status not in DONE_STATUSES and c.status != "Duplicate")
    done_count = sum(1 for c in complaints if c.status in DONE_STATUSES)

    return {
        "totals": {
            "total": len(complaints),
            "open": open_count,
            "done": done_count,
            "duplicate": sum(1 for c in complaints if c.status == "Duplicate"),
            "this_month": monthly[-1]["count"],
            "last_month": monthly[-2]["count"],
        },
        "monthly": monthly,
        "areas": all_areas,
        "categories": all_categories,
    }
