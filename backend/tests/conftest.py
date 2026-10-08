import os
import tempfile
from pathlib import Path

# Isolate the test database/uploads BEFORE any `app.*` module is imported.
_TEST_DB = Path(__file__).resolve().parent / "test_cleanspot.db"
if _TEST_DB.exists():
    _TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="cleanspot_test_")
# signed tokens need a secret; deterministic is fine for tests
os.environ["SECRET_KEY"] = "test-secret-key-for-pytest-only-0123456789abcdef"
os.environ["DEBUG"] = "0"
os.environ["SEED_CITIZEN_PASSWORD"] = "citizen-test-pw"
os.environ["SEED_OFFICER_PASSWORD"] = "officer-test-pw"
os.environ["SEED_ADMIN_PASSWORD"] = "admin-test-pw"
os.environ["SEED_ZONE_OFFICER_PASSWORD"] = "zone-officer-test-pw"

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models import Complaint, RateLimitRecord, StatusEvent, User

SEED_USERNAMES = ("citizen", "officer", "admin", "officer_zone1", "officer_zone2", "officer_zone3", "officer_zone4")


@pytest.fixture(autouse=True)
def _stub_ai(monkeypatch):
    """API/status tests must not depend on the real model's opinion of a
    solid-colour test image. Tests that care about AI behaviour stub it
    themselves (see test_verifier.py)."""
    from app.api import citizen

    monkeypatch.setattr(
        citizen,
        "verify_image",
        lambda path: {
            "is_garbage": True,
            "confidence": 0.99,
            "waste_type": None,
            "decision": "accepted",
        },
    )


@pytest.fixture(autouse=True)
def _reset_login_rate():
    """The login rate limiter is in-memory - reset it around every test."""
    from app.api import auth as auth_api

    auth_api._login_attempts.clear()
    yield
    auth_api._login_attempts.clear()


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _wipe(session):
    session.query(StatusEvent).delete()
    session.query(Complaint).delete()
    session.query(RateLimitRecord).delete()
    # keep the three seeded accounts; drop anything created by register tests
    session.query(User).filter(~User.username.in_(SEED_USERNAMES)).delete()
    session.commit()


@pytest.fixture(autouse=True)
def _clean_tables(db):
    _wipe(db)
    yield
    _wipe(db)


@pytest.fixture(scope="session")
def app_module():
    from app.main import app

    return app


@pytest.fixture()
def client(app_module, db):
    with TestClient(app_module) as c:
        _wipe(db)  # drop seed-time sample complaints so tests start deterministic
        yield c
