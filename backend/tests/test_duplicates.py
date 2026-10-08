from app.models import Complaint
from app.services.duplicates import find_duplicate, haversine_distance


def test_haversine():
    # ~30m apart approx
    d = haversine_distance(12.9716, 77.5946, 12.9716 + 0.00027, 77.5946)
    assert 20 < d < 40


def test_find_duplicate_open_complaint_matches(db):
    db.add(Complaint(photo_path="x.jpg", latitude=12.0, longitude=77.0, status="Reported"))
    db.commit()

    dup = find_duplicate(db, 12.0, 77.00027, max_dist_m=40)
    assert dup is not None
    assert dup.latitude == 12.0


def test_find_duplicate_resolved_complaint_ignored(db):
    db.add(Complaint(photo_path="x.jpg", latitude=12.0, longitude=77.0, status="Resolved"))
    db.commit()

    assert find_duplicate(db, 12.0, 77.0, max_dist_m=40) is None


def test_find_duplicate_too_far_returns_none(db):
    db.add(Complaint(photo_path="x.jpg", latitude=12.0, longitude=77.0, status="Reported"))
    db.commit()

    # ~0.01 deg lon at lat 12 is well over 1 km
    assert find_duplicate(db, 12.0, 77.01, max_dist_m=30) is None
