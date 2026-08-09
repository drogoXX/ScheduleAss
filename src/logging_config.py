"""
Centralised logging configuration.

Logs go to a rotating file under the instance directory and to stderr, so
operational problems are diagnosable without exposing internals to end users.
"""

import logging
import logging.handlers
import sys
import uuid

from src.config import ensure_directories, settings

_CONFIGURED = False

_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"


def configure_logging() -> None:
    """Install handlers once per process."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    ensure_directories()

    root = logging.getLogger("schedule_analyzer")
    root.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))
    root.propagate = False

    formatter = logging.Formatter(_FORMAT)

    file_handler = logging.handlers.RotatingFileHandler(
        settings.log_dir / "app.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Get a namespaced logger, configuring logging on first use."""
    configure_logging()
    return logging.getLogger(f"schedule_analyzer.{name}")


def new_error_reference() -> str:
    """Short opaque id shown to the user and logged alongside the traceback."""
    return uuid.uuid4().hex[:8].upper()
