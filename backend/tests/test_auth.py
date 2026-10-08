"""Registration + login + password storage tests (Phase 1 auth)."""
import bcrypt
import jwt as pyjwt
import pytest

from app.config import settings
from app.database import SessionLocal
from app.models import User
from tests.helpers import ADMIN, CITIZEN, OFFICER, login


def test_register_creates_citizen_with_hashed_password(client, db):
    r = client.post("/api/auth/register", json={"username": "ramu", "password": "secure-pass-1"})
    assert r.status_code == 201
    body = r.json()
    assert body["role"] == "citizen"

    user = db.query(User).filter_by(username="ramu").first()
    assert user is not None
    # stored value is a bcrypt hash, never the plain password
    assert user.password_hash.startswith("$2")
    assert "secure-pass-1" not in user.password_hash
    assert bcrypt.checkpw(b"secure-pass-1", user.password_hash.encode())


def test_register_rejects_duplicate_username(client):
    assert client.post("/api/auth/register", json={"username": "dup", "password": "long-enough-pw"}).status_code == 201
    r = client.post("/api/auth/register", json={"username": "dup", "password": "another-long-pw"})
    assert r.status_code == 409


def test_register_validates_username_and_password(client):
    # too short for pydantic -> 422
    assert client.post("/api/auth/register", json={"username": "a", "password": "long-enough-pw"}).status_code == 422
    # invalid characters -> our 400
    assert client.post("/api/auth/register", json={"username": "ok name", "password": "long-enough-pw"}).status_code == 400
    # pydantic rejects short passwords with 422
    assert client.post("/api/auth/register", json={"username": "okname", "password": "short"}).status_code == 422


def test_login_returns_signed_token(client):
    r = login(client, "citizen", settings.SEED_CITIZEN_PASSWORD)
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "citizen"
    # the token works on a protected route
    assert client.get("/api/citizen/complaints", headers={"Authorization": f"Bearer {body['token']}"}).status_code == 200


def test_seeded_accounts_all_login(client):
    for username, password, role in [
        ("citizen", settings.SEED_CITIZEN_PASSWORD, "citizen"),
        ("officer", settings.SEED_OFFICER_PASSWORD, "officer"),
        ("admin", settings.SEED_ADMIN_PASSWORD, "admin"),
    ]:
        r = login(client, username, password)
        assert r.status_code == 200, username
        assert r.json()["role"] == role


def test_login_failures_are_generic(client):
    r = login(client, "citizen", "wrong-password-here")
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid username or password"
    # unknown user gets the SAME message (no user enumeration)
    r2 = login(client, "no-such-user", "whatever-it-is")
    assert r2.status_code == 401
    assert r2.json()["detail"] == "Invalid username or password"


def test_login_rate_limited_after_repeated_failures(client):
    for _ in range(5):
        assert login(client, "citizen", "wrong-password").status_code == 401
    r = login(client, "citizen", settings.SEED_CITIZEN_PASSWORD)  # even correct now blocked
    assert r.status_code == 429


def test_tokens_expire_and_cannot_be_forged():
    from app.auth import _decode_token
    from fastapi import HTTPException

    # expired token
    past = pyjwt.encode(
        {"sub": "1", "role": "citizen", "exp": 1}, settings.SECRET_KEY, algorithm="HS256"
    )
    with pytest.raises(HTTPException) as exc:
        _decode_token(past)
    assert exc.value.status_code == 401

    # forged with the wrong key
    forged = pyjwt.encode(
        {"sub": "2", "role": "officer", "exp": 9999999999}, "attacker-key", algorithm="HS256"
    )
    with pytest.raises(HTTPException) as exc:
        _decode_token(forged)
    assert exc.value.status_code == 401


def test_role_guards_enforced_on_server(client):
    # citizen cannot use officer or admin endpoints
    assert client.get("/municipal/complaints", headers=CITIZEN).status_code == 403
    assert client.delete("/admin/complaints/1", headers=CITIZEN).status_code == 403
    assert client.delete("/admin/complaints/1", headers=OFFICER).status_code == 403
    # officer cannot use admin endpoints
    assert client.delete("/admin/complaints/1", headers=OFFICER).status_code == 403
    # officer and admin CAN use the queue
    assert client.get("/municipal/complaints", headers=OFFICER).status_code == 200
    assert client.get("/municipal/complaints", headers=ADMIN).status_code == 200


def test_municipal_inbox_requires_auth(client):
    # the simulated municipal inbox used to be public - not anymore
    assert client.post("/municipal/complaints", json={"id": 1}).status_code == 401
    assert client.post("/municipal/complaints", json={"id": 1}, headers=CITIZEN).status_code == 403
    assert client.post("/municipal/complaints", json={"id": 1}, headers=OFFICER).status_code == 200
