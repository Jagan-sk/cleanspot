import pytest
from app.config import settings
from app.models import Complaint, RateLimitRecord, StatusEvent
from tests.helpers import CITIZEN, OFFICER, image_file, make_image_bytes, submit


def test_submit_requires_auth(client):
    r = client.post(
        "/api/citizen/submit",
        data={"latitude": "12.0", "longitude": "77.0"},
        files=image_file(),
    )
    assert r.status_code == 401


def test_submit_rejects_bad_token(client):
    r = client.post(
        "/api/citizen/submit",
        data={"latitude": "12.0", "longitude": "77.0"},
        files=image_file(),
        headers={"Authorization": "Bearer nope"},
    )
    assert r.status_code == 401


def test_submit_success_creates_complaint_with_event(client, db):
    r = submit(client, address="Some street")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "Reported"
    assert body["reporter_id"] == 1  # from token, not client input
    events = db.query(StatusEvent).filter_by(complaint_id=body["id"]).all()
    assert [e.status for e in events] == ["Reported"]


def test_submit_ignores_client_reporter_id(client):
    # reporter_id is no longer a form field; identity comes from the token
    r = client.post(
        "/api/citizen/submit",
        data={"latitude": "12.0", "longitude": "77.0", "reporter_id": "999"},
        files=image_file(),
        headers=CITIZEN,
    )
    assert r.status_code == 200
    assert r.json()["reporter_id"] == 1


def test_hash_duplicate_rejected(client):
    payload = make_image_bytes((5, 5, 5))
    r1 = client.post(
        "/api/citizen/submit",
        data={"latitude": "12.0", "longitude": "77.0"},
        files={"image": ("a.jpg", payload, "image/jpeg")},
        headers=CITIZEN,
    )
    assert r1.status_code == 200
    r2 = client.post(
        "/api/citizen/submit",
        data={"latitude": "13.0", "longitude": "78.0"},
        files={"image": ("b.jpg", payload, "image/jpeg")},
        headers=CITIZEN,
    )
    assert r2.status_code == 400
    assert "Duplicate photo" in r2.json()["detail"]


def test_location_duplicate_links_instead_of_500(client, db):
    # regression: this path used to crash with NOT NULL on status_events.complaint_id
    first = submit(client, lat=12.0, lon=77.0, color=(1, 2, 3))
    assert first.status_code == 200
    first_id = first.json()["id"]

    # different photo (~22 m away, within the 30 m threshold)
    second = submit(client, lat=12.0, lon=77.0002, color=(9, 8, 7))
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["status"] == "Duplicate"
    assert body["duplicate_of"] == first_id

    events = db.query(StatusEvent).filter_by(complaint_id=body["id"]).all()
    assert [e.status for e in events] == ["Duplicate"]


def test_far_apart_complaints_not_linked(client):
    a = submit(client, lat=12.0, lon=77.0, color=(11, 12, 13))
    b = submit(client, lat=12.01, lon=77.01, color=(14, 15, 16))
    assert a.status_code == 200 and b.status_code == 200
    assert b.json()["status"] == "Reported"
    assert b.json()["duplicate_of"] is None


def test_invalid_image_rejected(client):
    r = client.post(
        "/api/citizen/submit",
        data={"latitude": "12.0", "longitude": "77.0"},
        files={"image": ("fake.jpg", b"not an image at all", "image/jpeg")},
        headers=CITIZEN,
    )
    assert r.status_code == 400
    assert "valid image" in r.json()["detail"]


def test_unsupported_extension_rejected(client):
    # extension is not trusted - content is checked, so garbage bytes fail
    r = client.post(
        "/api/citizen/submit",
        data={"latitude": "12.0", "longitude": "77.0"},
        files={"image": ("evil.exe", b"anything", "application/octet-stream")},
        headers=CITIZEN,
    )
    assert r.status_code == 400
    assert "valid image" in r.json()["detail"]


def test_oversized_upload_rejected(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 0)
    r = submit(client)
    assert r.status_code == 400
    assert r.json()["detail"] == "Image too large"


def test_invalid_coordinates_rejected(client):
    r = client.post(
        "/api/citizen/submit",
        data={"latitude": "999", "longitude": "0"},
        files=image_file(),
        headers=CITIZEN,
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "Invalid coordinates"


def test_rate_limit_blocks_and_ip_cannot_be_bypassed(client, db):
    for _ in range(settings.REPORT_RATE_LIMIT_PER_HOUR):
        db.add(RateLimitRecord(reporter_id=1, ip_address="testclient"))
    db.commit()

    r = submit(client)
    assert r.status_code == 429

    # even a different reporter_id from the same client IP stays limited
    r2 = client.post(
        "/api/citizen/submit",
        data={"latitude": "12.0", "longitude": "77.0", "reporter_id": "999"},
        files=image_file(color=(3, 3, 3)),
        headers=CITIZEN,
    )
    assert r2.status_code == 429


def test_my_reports_scoped_to_owner(client, db):
    # a complaint belonging to the officer account must be invisible to the citizen
    db.add(Complaint(photo_path="uploads/x.jpg", latitude=1.0, longitude=2.0,
                     status="Reported", reporter_id=2))
    db.commit()

    submit(client)  # citizen's own
    ids = [c["id"] for c in client.get("/api/citizen/complaints", headers=CITIZEN).json()]
    assert len(ids) == 1

    # citizens' list is OWN complaints only for everyone (officers use /municipal)
    officer_ids = [c["id"] for c in client.get("/api/citizen/complaints", headers=OFFICER).json()]
    assert officer_ids == [1]  # only the officer's own (the seeded one above)


def test_my_reports_requires_auth(client):
    assert client.get("/api/citizen/complaints").status_code == 401


def test_complaint_detail_hidden_from_other_citizens(client, db):
    other = Complaint(photo_path="uploads/y.jpg", latitude=1.0, longitude=2.0,
                      status="Reported", reporter_id=2, zone_id="zone1")
    db.add(other)
    db.commit()

    # another citizen gets 403 (not 404 - we do not hide ids in this app)
    assert client.get(f"/api/citizen/complaints/{other.id}", headers=CITIZEN).status_code == 403
    assert client.get(f"/api/citizen/complaints/{other.id}", headers=OFFICER).status_code == 200
    assert client.get(f"/api/citizen/complaints/{other.id}").status_code == 401


def test_municipal_queue_requires_officer(client):
    assert client.get("/municipal/complaints").status_code == 401
    assert client.get("/municipal/complaints", headers=CITIZEN).status_code == 403
    assert client.get("/municipal/complaints", headers=OFFICER).status_code == 200


def test_assign_resolve_require_officer(client):
    cid = submit(client).json()["id"]
    assert client.post(f"/municipal/complaints/{cid}/assign").status_code == 401
    assert client.post(f"/municipal/complaints/{cid}/assign", headers=CITIZEN).status_code == 403
    assert client.post(f"/municipal/complaints/{cid}/resolve", headers=CITIZEN).status_code == 403

    assert client.post(f"/municipal/complaints/{cid}/assign", headers=OFFICER).status_code == 200
    assert client.post(f"/municipal/complaints/{cid}/resolve", headers=OFFICER).status_code == 200


def test_municipal_status_history(client):
    cid = submit(client).json()["id"]
    client.post(f"/municipal/complaints/{cid}/assign", headers=OFFICER)

    r = client.get(f"/municipal/complaints/{cid}", headers=OFFICER)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "Assigned"
    assert [h["status"] for h in body["history"]] == ["Reported", "Assigned"]


def test_duplicate_cannot_be_assigned_or_resolved(client):
    # inside zone1 so the zone-1 officer is allowed to try (and gets 400 for dupe)
    submit(client, lat=12.93, lon=77.58, color=(21, 22, 23))
    # ~22 m east - within the 30 m duplicate radius
    dup_id = submit(client, lat=12.93, lon=77.5802, color=(24, 25, 26)).json()["id"]

    assert client.post(f"/municipal/complaints/{dup_id}/assign", headers=OFFICER).status_code == 400
    assert client.post(f"/municipal/complaints/{dup_id}/resolve", headers=OFFICER).status_code == 400


def test_assign_missing_complaint_404(client):
    assert client.post("/municipal/complaints/99999/assign", headers=OFFICER).status_code == 404
