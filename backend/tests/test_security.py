"""Phase 1 security tests: photos, upload hardening, headers, after-photo."""
import io
import os

from PIL import Image

from app.config import settings
from tests.helpers import ADMIN, CITIZEN, OFFICER, image_file, make_image_bytes, submit


def _jpeg_with_exif() -> bytes:
    """A real JPEG carrying EXIF metadata (like a phone photo)."""
    buf = io.BytesIO()
    img = Image.new("RGB", (60, 60), (10, 120, 60))
    exif = Image.Exif()
    exif[271] = "TestCam"  # Make tag - proves metadata survived if still present
    img.save(buf, "JPEG", exif=exif.tobytes())
    return buf.getvalue()


def test_protected_routes_require_auth(client):
    for method, url in [
        ("GET", "/api/citizen/complaints"),
        ("GET", "/api/citizen/complaints/1"),
        ("GET", "/api/stats"),
        ("GET", "/municipal/complaints"),
        ("GET", "/api/photos/1/report"),
        ("DELETE", "/admin/complaints/1"),
    ]:
        r = client.request(method, url)
        assert r.status_code == 401, url


def test_citizen_cannot_read_others_complaint_or_photo(client):
    # officer (id 2) reports a real complaint with a real photo file
    cid = submit(client, headers=OFFICER, color=(90, 91, 92)).json()["id"]

    assert client.get(f"/api/citizen/complaints/{cid}", headers=CITIZEN).status_code == 403
    assert client.get(f"/api/photos/{cid}/report", headers=CITIZEN).status_code == 403
    # the owner and an admin can fetch it
    assert client.get(f"/api/photos/{cid}/report", headers=OFFICER).status_code == 200
    assert client.get(f"/api/photos/{cid}/report", headers=ADMIN).status_code == 200


def test_fake_image_renamed_jpg_rejected(client):
    r = client.post(
        "/api/citizen/submit",
        data={"latitude": "12.0", "longitude": "77.0"},
        files={"image": ("fake.jpg", b"this is just text, not an image", "image/jpeg")},
        headers=CITIZEN,
    )
    assert r.status_code == 400
    assert "valid image" in r.json()["detail"]


def test_oversized_file_rejected(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 0)
    r = submit(client)
    assert r.status_code == 400
    assert r.json()["detail"] == "Image too large"


def test_uploaded_images_have_no_exif_after_saving(client):
    r = client.post(
        "/api/citizen/submit",
        data={"latitude": "12.0", "longitude": "77.0"},
        files={"image": ("gps.jpg", _jpeg_with_exif(), "image/jpeg")},
        headers=CITIZEN,
    )
    assert r.status_code == 200, r.text
    rel = r.json()["photo_path"]
    abs_path = settings.UPLOAD_DIR / os.path.basename(rel)
    with Image.open(abs_path) as saved:
        exif = saved.getexif()
        assert len(exif) == 0, f"EXIF metadata survived sanitising: {dict(exif)}"
        # GPS IFD specifically gone too
        assert not exif.get_ifd(34853)


def test_large_images_downscaled(client):
    r = submit(client, color=(7, 7, 7))  # 80x80 default is fine
    assert r.status_code == 200
    # now force a tiny dimension limit and upload a bigger image
    import tests.helpers as h
    from app.config import settings as st
    old = st.MAX_IMAGE_DIMENSION
    st.MAX_IMAGE_DIMENSION = 50
    try:
        r2 = client.post(
            "/api/citizen/submit",
            data={"latitude": "12.0", "longitude": "78.0"},
            files={"image": ("big.jpg", h.make_image_bytes(size=(300, 200)), "image/jpeg")},
            headers=CITIZEN,
        )
        assert r2.status_code == 200
        abs_path = st.UPLOAD_DIR / os.path.basename(r2.json()["photo_path"])
        with Image.open(abs_path) as saved:
            assert max(saved.size) <= 50
    finally:
        st.MAX_IMAGE_DIMENSION = old


def test_photos_not_served_from_public_static(client):
    # the old /uploads static mount must be gone
    r = client.get("/uploads/sample_c1.jpg")
    assert r.status_code == 404


def test_authed_photo_endpoint_serves_report(client):
    cid = submit(client, color=(31, 32, 33)).json()["id"]
    r = client.get(f"/api/photos/{cid}/report", headers=CITIZEN)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"


def test_after_photo_flow(client):
    cid = submit(client, color=(41, 42, 43)).json()["id"]

    # officer assigns, then resolves WITH an after photo + note
    assert client.post(f"/municipal/complaints/{cid}/assign", headers=OFFICER).status_code == 200
    r = client.post(
        f"/municipal/complaints/{cid}/resolve",
        data={"note": "Cleaned up, bin relocated"},
        files={"photo": ("after.jpg", make_image_bytes((200, 30, 30)), "image/jpeg")},
        headers=OFFICER,
    )
    assert r.status_code == 200, r.text
    assert r.json()["after_photo"]

    # reporter sees the after photo in their detail (event) and can fetch it
    detail = client.get(f"/api/citizen/complaints/{cid}", headers=CITIZEN).json()
    resolved_events = [e for e in detail["events"] if e["status"] == "Resolved"]
    assert resolved_events and resolved_events[0]["photo"]
    assert resolved_events[0]["note"] == "Cleaned up, bin relocated"

    r = client.get(f"/api/photos/{cid}/after", headers=CITIZEN)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/")

    # another citizen cannot fetch it
    client.post("/api/auth/register", json={"username": "nosy", "password": "long-enough-pw"})
    nosy = client.post("/api/auth/login", json={"username": "nosy", "password": "long-enough-pw"}).json()
    r = client.get(f"/api/photos/{cid}/after", headers={"Authorization": f"Bearer {nosy['token']}"})
    assert r.status_code == 403

    # resolve again with no photo: idempotent, no new event
    events_before = len(detail["events"])
    r = client.post(f"/municipal/complaints/{cid}/resolve", headers=OFFICER)
    assert r.status_code == 200
    detail2 = client.get(f"/api/citizen/complaints/{cid}", headers=CITIZEN).json()
    assert len(detail2["events"]) == events_before


def test_late_after_photo_on_resolved_complaint(client):
    cid = submit(client, color=(51, 52, 53)).json()["id"]
    assert client.post(f"/municipal/complaints/{cid}/resolve", headers=OFFICER).status_code == 200
    # attaching the proof photo afterwards is allowed
    r = client.post(
        f"/municipal/complaints/{cid}/resolve",
        files={"photo": ("late.jpg", make_image_bytes((1, 200, 3)), "image/jpeg")},
        headers=OFFICER,
    )
    assert r.status_code == 200
    assert client.get(f"/api/photos/{cid}/after", headers=CITIZEN).status_code == 200


def test_address_and_waste_type_validated(client):
    r = submit(client, address="x" * 400)
    assert r.status_code == 400
    r = submit(client, waste_type="Nuclear")
    assert r.status_code == 400
    r = submit(client, waste_type="Plastic", address="Short")
    assert r.status_code == 200


def test_admin_can_delete_complaint_and_files(client, db):
    cid = submit(client, color=(61, 62, 63)).json()["id"]
    rel = client.get(f"/api/citizen/complaints/{cid}", headers=CITIZEN).json()["photo_path"]
    abs_path = settings.UPLOAD_DIR / os.path.basename(rel)
    assert abs_path.exists()

    r = client.delete(f"/admin/complaints/{cid}", headers=ADMIN)
    assert r.status_code == 200
    assert r.json()["deleted"] is True
    assert not abs_path.exists()
    assert client.get(f"/api/citizen/complaints/{cid}", headers=CITIZEN).status_code == 404


def test_security_headers_present(client):
    r = client.get("/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("Referrer-Policy") == "no-referrer"
