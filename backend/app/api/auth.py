"""Public auth endpoints: citizen registration + login for every role.

The old officer access-code screen is replaced by username/password login.
Officers and admins are seeded accounts (see app/seed.py / README).
"""
import re
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

# simple in-memory login rate limit (per client IP)
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 60
_login_attempts: dict[str, list[float]] = {}

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _check_login_rate(ip: str) -> None:
    now = time.time()
    recent = [t for t in _login_attempts.get(ip, []) if now - t < LOGIN_WINDOW_SECONDS]
    _login_attempts[ip] = recent
    if len(recent) >= LOGIN_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many login attempts - try again in a minute")


def _record_failed(ip: str) -> None:
    _login_attempts.setdefault(ip, []).append(time.time())


@router.post("/register", status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    """Public: create a citizen account (officers/admins are seeded)."""
    if not USERNAME_RE.match(payload.username):
        raise HTTPException(
            status_code=400,
            detail="Username must be 3-32 characters: letters, digits, _ . -",
        )
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=409, detail="Username already taken")
    user = User(
        username=payload.username,
        role="citizen",
        password_hash=hash_password(payload.password),  # bcrypt, never plain text
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "username": user.username, "role": user.role}


@router.post("/login")
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    """Public: exchange username+password for a signed token (expires in 12h)."""
    ip = _client_ip(request)
    _check_login_rate(ip)

    user = db.query(User).filter(User.username == payload.username).first()
    # generic message whether the username exists or the password is wrong
    if user is None or not verify_password(payload.password, user.password_hash or ""):
        _record_failed(ip)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    _login_attempts.pop(ip, None)  # a successful login clears the failure window
    return {"token": create_access_token(user), "role": user.role, "zone_id": user.zone_id}
