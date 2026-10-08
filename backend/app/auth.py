"""Authentication helpers: password hashing (bcrypt) and signed JWT tokens.

Phase 1 security: real usernames + passwords, signed tokens with expiry.
The old static demo tokens (citizen_token / officer_token) are GONE.
"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User

_bearer = HTTPBearer(auto_error=False)  # extracts "Authorization: Bearer <token>"
ALGORITHM = "HS256"


def actor_name(db, user) -> str:
    """Display name recorded on status events ("who did this")."""
    return getattr(user, "username", None) or "system"


def hash_password(password: str) -> str:
    """One-way bcrypt hash. Never store or log the plain password."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Check a plain password against a stored hash (False if hash missing/broken)."""
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


def create_access_token(user: User) -> str:
    """Signed token containing the user id and role, expiring after
    TOKEN_EXPIRE_HOURS (default 12h). Signed with SECRET_KEY from the env."""
    payload = {
        "sub": str(user.id),
        "role": user.role,                      # informational; DB is the source of truth
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.TOKEN_EXPIRE_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired - please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency: resolve the bearer token to a User row.
    Raises 401 for missing/expired/forged tokens."""
    if creds is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = _decode_token(creds.credentials)
    try:
        user_id = int(payload.get("sub", 0))
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


def require_role(*roles: str):
    """Reusable role guard for SERVER-side enforcement, e.g.
        user = Depends(require_role("officer", "admin"))
    Raises 403 when the logged-in user's role is not allowed."""
    allowed = set(roles)

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail="You do not have permission to do that")
        return user

    return checker
