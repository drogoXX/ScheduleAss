"""
Authentication Manager
Handles user authentication, session lifetime and authorization checks.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import streamlit as st

from src.auth.security import validate_password_strength
from src.config import settings
from src.database.db_manager import DatabaseManager
from src.logging_config import get_logger

logger = get_logger("auth")

# Sessions idle for longer than this must re-authenticate.
SESSION_IDLE_MINUTES = 60


class AuthManager:
    """Manages user authentication and authorization."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self._init_session_state()

    def _init_session_state(self):
        if 'authenticated' not in st.session_state:
            st.session_state.authenticated = False
        if 'user' not in st.session_state:
            st.session_state.user = None
        if 'last_activity' not in st.session_state:
            st.session_state.last_activity = None

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------
    def login(self, username: str, password: str) -> bool:
        """Authenticate a user and start a session."""
        user = self.db.authenticate_user(username, password)
        if not user:
            return False

        # Clear any pre-existing session data before establishing the new one,
        # so state cannot leak between accounts on a shared browser session.
        self._clear_session_data()

        st.session_state.authenticated = True
        st.session_state.user = {
            'id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'role': user['role'],
        }
        st.session_state.last_activity = datetime.now(timezone.utc).isoformat()
        self.db.log_action(user['id'], 'login', user['id'], {})
        return True

    def logout(self):
        """End the session and clear all user-scoped state."""
        user = self.get_current_user()
        if user:
            self.db.log_action(user['id'], 'logout', user['id'], {})
            logger.info("User %r logged out", user['username'])

        self._clear_session_data()
        st.session_state.authenticated = False
        st.session_state.user = None
        st.session_state.last_activity = None

    @staticmethod
    def _clear_session_data():
        """Drop cached per-user data so it cannot outlive the session."""
        for key in ('current_schedule', 'current_analysis', 'dcma_14_point',
                    'comparison_a', 'comparison_b'):
            st.session_state.pop(key, None)

    def _session_expired(self) -> bool:
        last_activity = st.session_state.get('last_activity')
        if not last_activity:
            return False
        try:
            last = datetime.fromisoformat(last_activity)
        except (TypeError, ValueError):
            return True
        return datetime.now(timezone.utc) - last > timedelta(minutes=SESSION_IDLE_MINUTES)

    def is_authenticated(self) -> bool:
        """True when a valid, unexpired session exists."""
        if not st.session_state.get('authenticated', False):
            return False

        if self._session_expired():
            logger.info("Session expired for %r", self.get_user_display_name())
            self.logout()
            return False

        st.session_state.last_activity = datetime.now(timezone.utc).isoformat()
        return True

    # ------------------------------------------------------------------
    # Authorization
    # ------------------------------------------------------------------
    def get_current_user(self) -> Optional[Dict]:
        return st.session_state.get('user', None)

    def is_admin(self) -> bool:
        user = self.get_current_user()
        return bool(user) and user.get('role') == 'admin'

    def is_viewer(self) -> bool:
        user = self.get_current_user()
        return bool(user) and user.get('role') == 'viewer'

    def require_auth(self):
        """Stop rendering the page unless the visitor is signed in."""
        if not self.is_authenticated():
            st.warning("Please log in to access this page.")
            st.info("Return to the main page to sign in.")
            st.stop()

    def require_admin(self):
        """Stop rendering the page unless the visitor is an admin."""
        self.require_auth()
        if not self.is_admin():
            user = self.get_current_user()
            logger.warning(
                "Denied admin page to non-admin user %r",
                user.get('username') if user else 'unknown',
            )
            st.error("This page requires admin privileges.")
            st.stop()

    def get_user_display_name(self) -> str:
        user = self.get_current_user()
        return user.get('username', 'User') if user else 'Guest'

    # ------------------------------------------------------------------
    # Credential management
    # ------------------------------------------------------------------
    def change_password(self, current_password: str,
                        new_password: str) -> tuple[bool, str]:
        """
        Change the signed-in user's password.

        Returns (success, message). Requires the current password so a hijacked
        session cannot lock the real owner out.
        """
        user = self.get_current_user()
        if not user:
            return False, "You must be signed in to change your password."

        if not self.db.authenticate_user(user['username'], current_password):
            logger.warning("Failed password change for %r: bad current password",
                           user['username'])
            return False, "Current password is incorrect."

        problems = validate_password_strength(new_password)
        if problems:
            return False, " ".join(problems)

        if new_password == current_password:
            return False, "The new password must be different from the current one."

        self.db.set_password(user['id'], new_password)
        self.db.log_action(user['id'], 'change_password', user['id'], {})
        logger.info("Password changed for %r", user['username'])
        return True, "Password updated successfully."
