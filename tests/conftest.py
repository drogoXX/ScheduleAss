"""
Shared test fixtures.

Every test runs against a throwaway data directory so the suite never touches a
real database, and configuration is set before src.config is imported.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Redirect the data directory at IMPORT time, not in a fixture.
#
# logging_config.configure_logging() installs its file handler on first use and
# caches it for the process, resolving settings.log_dir at that moment. That
# happens while pytest is collecting - before any per-test fixture runs - so a
# fixture-level monkeypatch is too late and the suite ends up writing into the
# real runtime log directory (whatever .env points at). That pollutes the very
# log used to diagnose production problems, so it is set here instead.
_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="scheduleass-tests-"))
os.environ["APP_DATA_DIR"] = str(_TEST_DATA_DIR)
os.environ.setdefault("APP_ENV", "test")


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    """Point the app at a temporary data directory for the duration of a test."""
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "instance"))
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_ADMIN_PASSWORD", "BootstrapAdminPw1")
    monkeypatch.setenv("APP_DATE_ORDER", "auto")
    monkeypatch.setenv("APP_MAX_UPLOAD_MB", "50")
    monkeypatch.setenv("APP_MAX_ACTIVITIES", "100000")

    # Settings resolve environment variables on access, so no reload is needed.
    from src.config import settings

    yield settings


@pytest.fixture
def db(isolated_environment, tmp_path):
    """A fresh DatabaseManager backed by a temporary SQLite file."""
    from src.database.db_manager import DatabaseManager

    return DatabaseManager(db_path=str(tmp_path / "test.db"))


@pytest.fixture
def admin(db):
    """The bootstrap administrator, already authenticated once."""
    return db.authenticate_user("admin", "BootstrapAdminPw1")


# ---------------------------------------------------------------------------
# CSV builders
# ---------------------------------------------------------------------------

CSV_HEADER = (
    "Activity ID,Activity Name,Activity Status,WBS Code,At Completion Duration,"
    "Start,Finish,Free Float,Total Float,Predecessor Details,Successor Details,"
    "Primary Constraint,Activity Type,Duration Type,Resource Names\n"
)


def build_row(activity_id="A100", name="Task", status="Not Started", wbs="1.1",
              duration=10, start="01/03/2025 08:00", finish="15/03/2025 17:00",
              free_float=0, total_float=0, predecessors="", successors="",
              constraint="", activity_type="Task Dependent",
              duration_type="Fixed Duration & Units", resources=""):
    """Build one CSV row. Fields containing commas are quoted."""
    def q(value):
        text = "" if value is None else str(value)
        return f'"{text}"' if "," in text else text

    return ",".join(q(v) for v in [
        activity_id, name, status, wbs, duration, start, finish, free_float,
        total_float, predecessors, successors, constraint, activity_type,
        duration_type, resources,
    ]) + "\n"


def build_csv(rows) -> bytes:
    """Assemble a complete CSV document from row strings."""
    return (CSV_HEADER + "".join(rows)).encode("utf-8")


@pytest.fixture
def csv_builder():
    """Expose the CSV helpers to tests."""
    return build_csv, build_row


@pytest.fixture
def sample_csv_bytes():
    """The repository's checked-in sample schedule."""
    return (ROOT / "data" / "sample_schedule.csv").read_bytes()


@pytest.fixture
def real_export_bytes():
    """A real 1,261-activity P6 export used as a regression corpus."""
    path = ROOT / "data" / "Schedule export.csv"
    if not path.exists():
        pytest.skip("Real P6 export not available")
    return path.read_bytes()


@pytest.fixture
def parsed_sample(sample_csv_bytes):
    from src.parsers.schedule_parser import ScheduleParser

    data = ScheduleParser().parse_csv(sample_csv_bytes, "sample_schedule.csv")
    assert data["success"], data.get("errors")
    return data
