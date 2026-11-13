from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# backend/ directory (this file lives in backend/app/config/)
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENV: str = "development"
    DATABASE_URL: str = "sqlite:///./cleanspot.db"
    UPLOAD_DIR: Path = Path("./uploads")

    # --- security (Phase 1) -------------------------------------------------
    # Secret key used to sign JWT tokens. REQUIRED unless DEBUG=1.
    # Generate one with:  openssl rand -hex 32
    SECRET_KEY: str = ""
    # DEBUG=1 is only for local development: it allows an empty SECRET_KEY
    # and shows error details. NEVER set DEBUG=1 in production.
    DEBUG: bool = False
    # signed tokens expire after this many hours
    TOKEN_EXPIRE_HOURS: int = 12
    # passwords for the seeded demo accounts (change these before real use!)
    SEED_CITIZEN_PASSWORD: str = "citizen-demo-123"
    SEED_OFFICER_PASSWORD: str = "officer-demo-123"
    # authority demo login: username "admin", password "admin"
    SEED_ADMIN_PASSWORD: str = "admin"
    # the per-zone demo officers (officer_zone1 .. officer_zone4 share one password)
    SEED_ZONE_OFFICER_PASSWORD: str = "zone-officer-demo-123"

    # --- uploads ------------------------------------------------------------
    MAX_UPLOAD_SIZE_MB: int = 8
    # images larger than this (either side) are downscaled on upload
    MAX_IMAGE_DIMENSION: int = 4096
    # comma-separated, e.g. ".jpg,.jpeg,.png,.webp"
    ALLOWED_IMAGE_EXTENSIONS: str = ".jpg,.jpeg,.png,.webp"

    # --- AI (unchanged in Phase 1) -----------------------------------------
    AI_CONFIDENCE_THRESHOLD: float = 0.7
    # trained TorchScript classifier (2 classes: 0 = not_garbage, 1 = garbage)
    MODEL_PATH: Path = Path("models/garbage_classifier.pt")
    # AI decision thresholds (see app/services/verifier.py)
    # confidence >= AUTO_ACCEPT -> accepted; below REVIEW_BELOW -> human review
    AUTO_ACCEPT: float = 0.80
    REVIEW_BELOW: float = 0.50
    # Optional: reject photos the model is confident are NOT garbage.
    # Off by default so low-confidence reports still reach a human reviewer.
    REJECT_NON_GARBAGE: bool = False

    MUNICIPAL_BASE_URL: str = "http://localhost:8000/municipal"
    REPORT_RATE_LIMIT_PER_HOUR: int = 10
    # comma-separated origins; "*" allowed but disables credentials
    CORS_ALLOW_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173"

    @property
    def allowed_image_extensions(self) -> set[str]:
        return {e.strip().lower() for e in self.ALLOWED_IMAGE_EXTENSIONS.split(",") if e.strip()}

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOW_ORIGINS.split(",") if o.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def resolved_model_path(self) -> Path:
        """Absolute model path; relative values are resolved from backend/."""
        path = self.MODEL_PATH
        return path if path.is_absolute() else BACKEND_DIR / path


settings = Settings()
