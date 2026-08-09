"""
Session lifecycle and authorization.

AuthManager's only Streamlit dependency is ``st.session_state``, so these tests
substitute a stand-in with the same semantics (attribute access, item access,
``get``, ``pop``, ``in``). That is faster and far more stable than driving a
real script context, which entangles with Streamlit's multipage machinery.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.auth.auth_manager import AuthManager


class FakeSessionState(dict):
    """Mimics streamlit's session_state: dict access plus attribute access."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value

    def __delattr__(self, name):
        del self[name]


@pytest.fixture
def session(monkeypatch):
    """Install a fresh fake session_state for the modules under test."""
    state = FakeSessionState()
    monkeypatch.setattr("streamlit.session_state", state, raising=False)
    monkeypatch.setattr("src.auth.auth_manager.st.session_state", state,
                        raising=False)
    return state


@pytest.fixture
def auth(db, session):
    return AuthManager(db)


class TestLogin:
    def test_successful_login_populates_the_session(self, auth, session):
        assert auth.login("admin", "BootstrapAdminPw1") is True
        assert session["authenticated"] is True
        assert session["user"]["username"] == "admin"
        assert session["user"]["role"] == "admin"

    def test_session_never_holds_the_password(self, auth, session):
        auth.login("admin", "BootstrapAdminPw1")
        user = session["user"]
        assert "password" not in user and "password_hash" not in user

    def test_failed_login_leaves_the_session_anonymous(self, auth, session):
        assert auth.login("admin", "wrong-password") is False
        assert session["authenticated"] is False
        assert session["user"] is None

    def test_login_clears_data_left_by_a_previous_user(self, auth, session):
        """State from one account must not leak into the next on a shared browser."""
        session["current_schedule"] = {"id": "sched_from_previous_user"}
        session["current_analysis"] = {"id": "analysis_from_previous_user"}

        assert auth.login("admin", "BootstrapAdminPw1") is True
        assert "current_schedule" not in session
        assert "current_analysis" not in session

    def test_login_is_recorded_in_the_audit_log(self, auth, db, session):
        auth.login("admin", "BootstrapAdminPw1")
        assert any(e["action_type"] == "login" for e in db.get_audit_log())


class TestLogout:
    def test_logout_clears_the_session(self, auth, session):
        auth.login("admin", "BootstrapAdminPw1")
        session["current_schedule"] = {"id": "sched_001"}

        auth.logout()

        assert auth.is_authenticated() is False
        assert session["authenticated"] is False
        assert session["user"] is None
        assert "current_schedule" not in session

    def test_logout_is_recorded_in_the_audit_log(self, auth, db, session):
        auth.login("admin", "BootstrapAdminPw1")
        auth.logout()
        assert any(e["action_type"] == "logout" for e in db.get_audit_log())


class TestSessionExpiry:
    def test_expired_session_is_rejected(self, auth, session):
        auth.login("admin", "BootstrapAdminPw1")
        session["last_activity"] = (
            datetime.now(timezone.utc) - timedelta(hours=3)
        ).isoformat()

        assert auth.is_authenticated() is False, "stale session still valid"
        assert session["authenticated"] is False

    def test_active_session_is_accepted(self, auth, session):
        auth.login("admin", "BootstrapAdminPw1")
        assert auth.is_authenticated() is True

    def test_activity_timestamp_is_refreshed(self, auth, session):
        auth.login("admin", "BootstrapAdminPw1")
        session["last_activity"] = (
            datetime.now(timezone.utc) - timedelta(minutes=5)
        ).isoformat()
        stale = session["last_activity"]

        auth.is_authenticated()
        assert session["last_activity"] > stale

    def test_corrupt_activity_timestamp_expires_the_session(self, auth, session):
        auth.login("admin", "BootstrapAdminPw1")
        session["last_activity"] = "not-a-timestamp"
        assert auth.is_authenticated() is False

    def test_anonymous_session_is_not_authenticated(self, auth):
        assert auth.is_authenticated() is False


class TestAuthorization:
    def test_admin_flags(self, auth, session):
        auth.login("admin", "BootstrapAdminPw1")
        assert auth.is_admin() is True
        assert auth.is_viewer() is False

    def test_viewer_flags(self, auth, db, session):
        db.create_user("v@example.com", "viewer1", "ViewerPassword1", "viewer")
        auth.login("viewer1", "ViewerPassword1")
        assert auth.is_admin() is False
        assert auth.is_viewer() is True

    def test_anonymous_is_neither(self, auth):
        assert auth.is_admin() is False
        assert auth.is_viewer() is False
        assert auth.get_user_display_name() == "Guest"

    def test_display_name_when_signed_in(self, auth, session):
        auth.login("admin", "BootstrapAdminPw1")
        assert auth.get_user_display_name() == "admin"


class TestChangePassword:
    def test_password_can_be_changed_and_is_then_required(self, auth, db, session):
        auth.login("admin", "BootstrapAdminPw1")

        ok, message = auth.change_password("BootstrapAdminPw1", "NewStrongPw123")
        assert ok is True, message

        assert db.authenticate_user("admin", "NewStrongPw123") is not None
        assert db.authenticate_user("admin", "BootstrapAdminPw1") is None

    def test_wrong_current_password_is_rejected(self, auth, session):
        auth.login("admin", "BootstrapAdminPw1")
        ok, message = auth.change_password("not-the-password", "NewStrongPw123")
        assert ok is False
        assert "incorrect" in message.lower()

    def test_weak_new_password_is_rejected(self, auth, session):
        auth.login("admin", "BootstrapAdminPw1")
        ok, message = auth.change_password("BootstrapAdminPw1", "short")
        assert ok is False
        assert "at least" in message.lower()

    def test_reusing_the_current_password_is_rejected(self, auth, session):
        auth.login("admin", "BootstrapAdminPw1")
        ok, message = auth.change_password("BootstrapAdminPw1", "BootstrapAdminPw1")
        assert ok is False
        assert "different" in message.lower()

    def test_anonymous_cannot_change_a_password(self, auth):
        ok, message = auth.change_password("a", "NewStrongPw123")
        assert ok is False
        assert "signed in" in message.lower()
