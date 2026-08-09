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
