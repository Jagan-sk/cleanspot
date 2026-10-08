from datetime import timedelta

from tests.helpers import CITIZEN, OFFICER, submit

from app.timeutils import utcnow


def test_stats_requires_auth(client):
    r = client.get("/api/stats")
    assert r.status_code == 401


def test_stats_shape_and_months(client):
    r = client.get("/api/stats", headers=CITIZEN)
    assert r.status_code == 200
    body = r.json()

    assert set(body) == {"totals", "monthly", "areas", "categories"}
    assert set(body["totals"]) == {
        "total", "open", "done", "duplicate", "this_month", "last_month"
    }

    monthly = body["monthly"]
    assert len(monthly) == 8
    # ascending month keys, ending with the current month
    keys = [m["key"] for m in monthly]
    assert keys == sorted(keys)
    now = utcnow()
    assert keys[-1] == f"{now.year:04d}-{now.month:02d}"
    for m in monthly:
        assert set(m) == {"key", "label", "count", "done", "areas", "categories"}


def test_stats_month_filtering_and_counts(client, db):
    now = utcnow()
    last_month = (now.replace(day=1) - timedelta(days=1))

    assert submit(client, lat=12.0, lon=77.0, address="42 Church Street, Bengaluru", color=(1, 2, 3)).status_code == 200
    assert submit(client, lat=12.1, lon=77.1, address="7 Church Street, Bengaluru", color=(4, 5, 6)).status_code == 200
    assert submit(client, lat=12.2, lon=77.2, address="Lake View Road, Bengaluru", color=(7, 8, 9)).status_code == 200

    # one resolved complaint dated last month (direct insert, bypasses flow)
    from app.models import Complaint
    old = Complaint(
        photo_path="uploads/old.jpg",
        latitude=12.3,
        longitude=77.3,
        address="42 Church Street, Bengaluru",
        created_at=last_month.replace(hour=12),
        status="Resolved",
        reporter_id=1,
    )
    db.add(old)
    db.commit()

    body = client.get("/api/stats", headers=CITIZEN).json()

    assert body["totals"]["total"] == 4
    assert body["totals"]["done"] == 1
    assert body["totals"]["open"] == 3
    assert body["totals"]["this_month"] == 3
    assert body["totals"]["last_month"] == 1

    # current month bucket holds only the 3 fresh reports
    this_month = body["monthly"][-1]
    assert this_month["count"] == 3
    assert this_month["done"] == 0

    old_month = body["monthly"][-2]
    assert old_month["count"] == 1
    assert old_month["done"] == 1

    # area grouping: "42"/"7 Church Street" collapse to "Church Street"
    assert body["areas"][0] == {"area": "Church Street", "count": 3}
    assert {"area": "Lake View Road", "count": 1} in body["areas"]

    # this month's areas are scoped to the month
    assert this_month["areas"][0] == {"area": "Church Street", "count": 2}


def test_stats_works_for_officer_and_without_address(client):
    # inside zone1 so the zone-scoped officer stats include it
    assert submit(client, lat=12.93, lon=77.58, headers=OFFICER).status_code == 200
    body = client.get("/api/stats", headers=OFFICER).json()
    assert body["totals"]["total"] == 1
    # no address -> coordinate bucket label
    assert body["areas"][0]["area"].startswith("Near 12.93")
    assert body["categories"][0] == {"name": "Garbage dumping", "count": 1}


def test_stats_months_param_validation(client):
    r = client.get("/api/stats?months=1", headers=CITIZEN)
    assert r.status_code == 422
    r = client.get("/api/stats?months=99", headers=CITIZEN)
    assert r.status_code == 422
    r = client.get("/api/stats?months=3", headers=CITIZEN)
    assert r.status_code == 200
    assert len(r.json()["monthly"]) == 3