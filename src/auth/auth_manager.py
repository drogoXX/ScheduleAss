"""
Authentication Manager
Handles user authentication and session management
"""

import streamlit as st
from typing import Optional, Dict
from src.database.db_manager import DatabaseManager


class AuthManager:
    """Manages user authentication and authorization"""

    def __init__(self, db_manager: DatabaseManager):
        """Initialize the authentication manager"""
        self.db = db_manager
        self._init_session_state()

    def _init_session_state(self):
        """Initialize session state for authentication"""
        if 'authenticated' not in st.session_state:
            st.session_state.authenticated = False
        if 'user' not in st.session_state:
            st.session_state.user = None

    def login(self, username: str, password: str) -> bool:
        """
        Authenticate user and create session
        Returns True if successful, False otherwise
        """
        user = self.db.authenticate_user(username, password)
        if user:
            st.session_state.authenticated = True
            st.session_state.user = {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'role': user['role']
            }
            return True
        return False

    def logout(self):
        """Clear session and log out user"""
        st.session_state.authenticated = False
        st.session_state.user = None

    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        return st.session_state.get('authenticated', False)

    def get_current_user(self) -> Optional[Dict]:
        """Get current authenticated user"""
        return st.session_state.get('user', None)

    def is_admin(self) -> bool:
        """Check if current user is admin"""
        user = self.get_current_user()
        return user and user.get('role') == 'admin'

    def is_viewer(self) -> bool:
        """Check if current user is viewer"""
        user = self.get_current_user()
        return user and user.get('role') == 'viewer'

    def require_auth(self):
        """Decorator/function to require authentication"""
        if not self.is_authenticated():
            st.warning("Please log in to access this page.")
            st.stop()

    def require_admin(self):
        """Require admin role"""
        self.require_auth()
        if not self.is_admin():
            st.error("This page requires admin privileges.")
            st.stop()

    def get_user_display_name(self) -> str:
        """Get display name for current user"""
        user = self.get_current_user()
        if user:
            return user.get('username', 'User')
        return 'Guest'
