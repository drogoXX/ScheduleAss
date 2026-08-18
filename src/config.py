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


# Folder names that indicate a file-synchronisation client owns the directory.
# A sync client rewrites files the application holds open, which corrupts SQLite
# and tears down Streamlit sessions mid-use - with nothing in the server log.
_SYNC_TREE_MARKERS = ("onedrive", "dropbox", "google drive", "googledrive",
                      "icloud", "creative cloud", "box sync", "nextcloud")


def data_dir_warnings() -> list:
    """Reasons the configured data directory is unsafe for a live database.

    Returns an empty list when the location is fine. See
    docs/TECHNICAL_SPECIFICATION_v2.md §5.6 - this check exists because a
    OneDrive-hosted database caused repeated session loss that produced no
    server-side error at all.
    """
    problems = []
    resolved = str(settings.DATA_DIR.resolve())
    lowered = resolved.lower()

    for marker in _SYNC_TREE_MARKERS:
        if marker in lowered:
            problems.append(
                f"The data directory is inside a '{marker}' synced folder ({resolved}). "
                "A sync client modifying the database while the app has it open causes "
                "corruption and dropped sessions. Set APP_DATA_DIR to a local path "
                "outside the synced tree."
            )
            break

    if resolved.startswith("\\\\") or resolved.startswith("//"):
        problems.append(
            f"The data directory is on a network share ({resolved}). SQLite locking is "
            "unreliable over SMB/NFS. Use a local disk, or move to PostgreSQL."
        )

    try:
        if BASE_DIR.resolve() in settings.DATA_DIR.resolve().parents or \
                settings.DATA_DIR.resolve() == BASE_DIR.resolve():
            problems.append(
                f"The data directory sits inside the code tree ({resolved}). Runtime data "
                "is destroyed by redeploys and risks client data being committed. Set "
                "APP_DATA_DIR to a location outside the repository."
            )
    except (OSError, ValueError):  # pragma: no cover - unresolvable paths
        pass

    return problems


def ensure_directories() -> None:
    """Create the runtime directories the app writes to."""
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.log_dir.mkdir(parents=True, exist_ok=True)
