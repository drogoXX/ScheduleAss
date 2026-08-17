"""
Application configuration.

All deployment-specific settings are read from environment variables (or a
.env file loaded via python-dotenv) so that no credentials or paths are baked
into the source tree.

Values are resolved lazily on each access rather than snapshotted at import
time. Modules that do ``from src.config import settings`` therefore always see
the current environment, which keeps configuration overridable at runtime and
in tests.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Repository / installation root
BASE_DIR = Path(__file__).resolve().parent.parent


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value is None or not value.strip() else value.strip()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


class Settings:
    """Resolved application settings, read from the environment on access."""

    # --- Environment ---------------------------------------------------
    @property
    def ENV(self) -> str:
        """Deployment environment; "production" hides debug affordances."""
        return _env_str("APP_ENV", "production").lower()

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"

    @property
    def DEBUG(self) -> bool:
        """Render full tracebacks in the UI. Off in production by default."""
        return _env_bool("APP_DEBUG", False)

    # --- Storage -------------------------------------------------------
    @property
    def DATA_DIR(self) -> Path:
        return Path(_env_str("APP_DATA_DIR", str(BASE_DIR / "instance")))

    @property
    def db_path(self) -> Path:
        return Path(_env_str("APP_DB_PATH",
                             str(self.DATA_DIR / "schedule_analyzer.db")))

    # --- Logging -------------------------------------------------------
    @property
    def LOG_LEVEL(self) -> str:
        return _env_str("APP_LOG_LEVEL", "INFO").upper()

    @property
    def log_dir(self) -> Path:
        return Path(_env_str("APP_LOG_DIR", str(self.DATA_DIR / "logs")))

    # --- Upload limits -------------------------------------------------
    @property
    def MAX_UPLOAD_MB(self) -> int:
        """
        Hard ceiling enforced in application code, independent of Streamlit's
        server.maxUploadSize (which only guards the transport layer).
        """
        return _env_int("APP_MAX_UPLOAD_MB", 50)

    @property
    def MAX_ACTIVITIES(self) -> int:
        return _env_int("APP_MAX_ACTIVITIES", 100_000)

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024

    # --- Authentication -------------------------------------------------
    @property
    def BOOTSTRAP_ADMIN_USERNAME(self) -> str:
        return _env_str("APP_ADMIN_USERNAME", "admin")

    @property
    def BOOTSTRAP_ADMIN_EMAIL(self) -> str:
        return _env_str("APP_ADMIN_EMAIL", "admin@example.com")

    @property
    def BOOTSTRAP_ADMIN_PASSWORD(self) -> str | None:
        """Applied only when the user table is empty."""
        return os.getenv("APP_ADMIN_PASSWORD") or None

    @property
    def MIN_PASSWORD_LENGTH(self) -> int:
        return _env_int("APP_MIN_PASSWORD_LENGTH", 12)

    @property
    def MAX_LOGIN_ATTEMPTS(self) -> int:
        return _env_int("APP_MAX_LOGIN_ATTEMPTS", 5)

    @property
    def LOCKOUT_SECONDS(self) -> int:
        return _env_int("APP_LOCKOUT_SECONDS", 300)

    # --- Parsing --------------------------------------------------------
    @property
    def DATE_ORDER(self) -> str:
        """
        P6 exports are locale-dependent. "auto" infers day-first vs month-first
        from the data; "day" / "month" force an interpretation.
        """
        return _env_str("APP_DATE_ORDER", "auto").lower()


settings = Settings()


def ensure_directories() -> None:
    """Create the runtime directories the app writes to."""
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.log_dir.mkdir(parents=True, exist_ok=True)
