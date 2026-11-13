from app.models import StatusEvent
from tests.helpers import CITIZEN, OFFICER, submit


def _assign(client, cid, headers=OFFICER):
    return client.post(f"/municipal/complaints/{cid}/assign", headers=headers)


def _resolve(client, cid, headers=OFFICER):
    return client.post(f"/municipal/complaints/{cid}/resolve", headers=headers)


def test_full_status_flow(client, db):
    cid = submit(client).json()["id"]

    # citizen cannot drive officer transitions
    assert _assign(client, cid, headers=CITIZEN).status_code == 403

    assert _assign(client, cid).status_code == 200
    assert client.get(f"/api/citizen/complaints/{cid}", headers=CITIZEN).json()["status"] == "Assigned"

    # re-assigning an already assigned complaint is a no-op
    assert _assign(client, cid).json()["status"] == "Assigned"

    assert _resolve(client, cid).status_code == 200
    # idempotent resolve
    assert _resolve(client, cid).json()["status"] == "Resolved"

    # cannot assign a resolved complaint
    assert _assign(client, cid).status_code == 400

    # citizen confirms cleanup -> Confirmed (terminal)
    r = client.post(f"/api/citizen/complaints/{cid}/confirm", headers=CITIZEN)
    assert r.status_code == 200
    assert r.json()["status"] == "Confirmed"

    # cannot confirm twice
    assert client.post(f"/api/citizen/complaints/{cid}/confirm", headers=CITIZEN).status_code == 400

    # reopen a confirmed complaint -> Reopened, then it can be assigned again
    r = client.post(f"/api/citizen/complaints/{cid}/reopen", headers=CITIZEN)
    assert r.status_code == 200
    assert r.json()["status"] == "Reopened"
    assert _assign(client, cid).status_code == 200

    statuses = [e.status for e in db.query(StatusEvent).filter_by(complaint_id=cid).order_by(StatusEvent.id)]
    assert statuses == ["Reported", "Assigned", "Resolved", "Confirmed", "Reopened", "Assigned"]


def test_cannot_confirm_before_resolved(client):
    cid = submit(client).json()["id"]
    assert client.post(f"/api/citizen/complaints/{cid}/confirm", headers=CITIZEN).status_code == 400
    assert client.post(f"/api/citizen/complaints/{cid}/reopen", headers=CITIZEN).status_code == 400


def test_confirm_keeps_original_photo_and_stores_after_photo(client):
    import io

    from PIL import Image

    cid = submit(client).json()["id"]
    before = client.get(f"/api/citizen/complaints/{cid}", headers=CITIZEN).json()["photo_path"]

    _resolve(client, cid)

    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (200, 30, 30)).save(buf, "JPEG")
    r = client.post(
        f"/api/citizen/complaints/{cid}/confirm",
        files={"image": ("after.jpg", buf.getvalue(), "image/jpeg")},
        headers=CITIZEN,
    )

    assert r.status_code == 200
    detail = client.get(f"/api/citizen/complaints/{cid}", headers=CITIZEN).json()
    assert detail["photo_path"] == before  # original evidence photo preserved
    after_events = [e for e in detail["events"] if e["status"] == "Confirmed"]
    assert after_events and after_events[0]["photo"]


def test_reopen_requires_resolved_or_confirmed(client):
    cid = submit(client).json()["id"]
    _resolve(client, cid)
    r = client.post(f"/api/citizen/complaints/{cid}/reopen", headers=CITIZEN)
    assert r.status_code == 200
    assert r.json()["status"] == "Reopened"


def test_only_reporter_can_reopen(client):
    cid = submit(client).json()["id"]
    _resolve(client, cid)
    # an officer in the same zone can read it, but reopening is the reporter's call
    r = client.post(f"/api/citizen/complaints/{cid}/reopen", headers=OFFICER)
    assert r.status_code == 403
