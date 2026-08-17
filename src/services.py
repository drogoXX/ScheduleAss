"""
Shared application services.

Streamlit re-executes the whole script on every interaction, so constructing a
DatabaseManager at page scope meant re-running the schema script and the
bootstrap check on every widget change. Caching the manager here gives all
pages one shared, correctly initialised instance.

The database path is part of the cache key so that changing the configured
location (deployments, tests) yields a new instance rather than silently
reusing the old one.
"""

import streamlit as st

from src.auth.auth_manager import AuthManager
from src.config import settings
from src.database.db_manager import DatabaseManager


@st.cache_resource(show_spinner=False)
def _database_for_path(db_path: str) -> DatabaseManager:
    return DatabaseManager(db_path=db_path)


def get_database() -> DatabaseManager:
    """The shared, process-wide database manager."""
    return _database_for_path(str(settings.db_path))


def get_auth(db: DatabaseManager | None = None) -> AuthManager:
    """
    An AuthManager bound to the shared database.

    Not cached: it reads and writes st.session_state, which is per-session, so
    it must be constructed against the current session on each run.
    """
    return AuthManager(db or get_database())


# ---------------------------------------------------------------------------
# Cached schedule reads
# ---------------------------------------------------------------------------
# A parsed schedule is ~2.6 MB of JSON, and reading one was measured at
# 1.7-2.2 s. Streamlit re-executes the whole script on every navigation and
# every widget change, so that cost was being paid over and over for data that
# had not changed. Caching it keeps page loads responsive, which also stops
# script runs piling up when a user clicks faster than a page renders.
#
# Correctness: every write that can change what these return calls
# invalidate_schedule_caches(). st.cache_data returns a copy of the cached
# value, so a page mutating its result cannot corrupt another page's view.
# max_entries bounds memory - a handful of schedules at a few MB each.

@st.cache_data(show_spinner=False, max_entries=8)
def load_schedule(schedule_id: str) -> dict | None:
    """The full schedule record, including parsed activities."""
    return get_database().get_schedule_by_id(schedule_id)


@st.cache_data(show_spinner=False, max_entries=8)
def load_analysis(schedule_id: str) -> dict | None:
    """The stored analysis results for a schedule."""
    return get_database().get_analysis_by_schedule(schedule_id)


def invalidate_schedule_caches() -> None:
    """
    Drop cached schedule and analysis reads.

    Must be called after any write that changes them - uploading a schedule,
    saving an analysis, or deleting a schedule or project. Clearing everything
    rather than a single id is deliberate: deletes cascade to schedules and
    analyses, so per-id invalidation would be easy to get subtly wrong, and
    rebuilding a cache entry costs about two seconds.
    """
    load_schedule.clear()
    load_analysis.clear()
