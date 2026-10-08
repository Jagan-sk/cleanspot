import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api import admin, citizen, municipal, photos, stats, zones
from app.api import auth as auth_api
from app.config import settings
from app.database import Base, engine
from app.seed import seed_data

log = logging.getLogger("cleanspot")

# ---------------------------------------------------------------------------
# Refuse to start with a missing/default secret outside DEBUG mode:
# unsigned/weakly-signed tokens would let anyone forge an officer session.
# ---------------------------------------------------------------------------
if not settings.DEBUG and (not settings.SECRET_KEY or len(settings.SECRET_KEY) < 16):
    raise RuntimeError(
        "SECRET_KEY is missing or too short. Set it in backend/.env "
        "(generate one with: openssl rand -hex 32), or set DEBUG=1 for local dev only."
    )

app = FastAPI(title="CleanSpot API")

_origins = settings.cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    # credentials + wildcard origins would let any site make credentialed calls
    allow_credentials="*" not in _origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Basic web hardening headers on every response."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Generic 500 - no stack traces to clients (details go to the server log)."""
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    if settings.DEBUG:
        return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


Base.metadata.create_all(bind=engine)


def _migrate() -> None:
    """Add columns that newer code expects to an existing SQLite database."""
    with engine.connect() as conn:
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(complaints)"))]
        if "ai_decision" not in cols:
            conn.execute(text("ALTER TABLE complaints ADD COLUMN ai_decision VARCHAR"))
        if "zone_id" not in cols:
            conn.execute(text("ALTER TABLE complaints ADD COLUMN zone_id VARCHAR"))
        user_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(users)"))]
        if "password_hash" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR"))
        if "zone_id" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN zone_id VARCHAR"))
        event_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(status_events)"))]
        if "note" not in event_cols:
            conn.execute(text("ALTER TABLE status_events ADD COLUMN note VARCHAR"))
        conn.commit()


def _backfill_zones() -> None:
    """One-off backfill: existing complaints get a zone from their coordinates."""
    from app.database import SessionLocal
    from app.models import Complaint
    from app.zones import zone_for

    db = SessionLocal()
    try:
        changed = 0
        for c in db.query(Complaint).filter(Complaint.zone_id.is_(None)).all():
            c.zone_id = zone_for(c.latitude, c.longitude)
            changed += 1
        if changed:
            db.commit()
            log.info("Backfilled zone_id on %d complaint(s)", changed)
    finally:
        db.close()


_migrate()
seed_data()
_backfill_zones()

settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
# NOTE: uploads are intentionally NOT mounted as static files - photos are
# served through the authenticated GET /api/photos/{id}/{kind} endpoint.

app.include_router(citizen.router)
app.include_router(municipal.router)
app.include_router(stats.router)
app.include_router(auth_api.router)
app.include_router(photos.router)
app.include_router(admin.router)
app.include_router(zones.router)


@app.get("/health")
def health():
    return {"status": "ok"}
