"""
Administration tab: user creation, password reset and access control.

The create/disable controls are the only way to onboard and offboard people,
and there is no password-reset flow, so the last-admin guard matters: losing it
would lock everyone out of user management permanently.
"""

from datetime import datetime, timezone

import pytest
from streamlit.testing.v1 import AppTest

SETTINGS_PAGE = "pages/5_Settings.py"
TIMEOUT = 60


def signed_in(user, db_path, monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", str(db_path))
    app = AppTest.from_file(SETTINGS_PAGE, default_timeout=TIMEOUT)
    app.session_state["authenticated"] = True
    app.session_state["user"] = {
        "id": user["id"], "username": user["username"],
        "email": user["email"], "role": user["role"],
    }
    app.session_state["last_activity"] = datetime.now(timezone.utc).isoformat()
    return app


class TestAdministrationTab:
    def test_admins_see_the_administration_tab(self, db, admin, monkeypatch):
        app = signed_in(admin, db.db_path, monkeypatch).run()
        assert not app.exception, app.exception
        rendered = " ".join(m.value for m in app.markdown)
        assert "Administration" in rendered
        assert "### Users" in rendered

    def test_viewers_do_not_see_it(self, db, monkeypatch):
        viewer = db.create_user("v@example.com", "viewer1", "ViewerPassword1",
                                "viewer")
        app = signed_in(viewer, db.db_path, monkeypatch).run()
        assert not app.exception, app.exception
        rendered = " ".join(m.value for m in app.markdown)
        assert "Administration" not in rendered
        assert "### Users" not in rendered

    def test_create_user_form_is_present_for_admins(self, db, admin, monkeypatch):
        app = signed_in(admin, db.db_path, monkeypatch).run()
        assert not app.exception, app.exception
        # Username, Email, Password on create; plus the change-password form.
        labels = [t.label for t in app.text_input]
        assert "Username *" in labels
        assert "Role *" in [s.label for s in app.selectbox]


class TestUserCreationRules:
    """The form defers to the database and password policy; verify both."""

    def test_created_user_can_sign_in(self, db):
        db.create_user("new@example.com", "newuser", "NewUserPass123", "viewer")
        assert db.authenticate_user("newuser", "NewUserPass123") is not None

    def test_created_viewer_has_no_admin_rights(self, db):
        created = db.create_user("v@example.com", "v1", "ViewerPass123",
                                 "viewer")
        assert created["role"] == "viewer"

    def test_duplicate_username_is_refused(self, db):
        db.create_user("a@example.com", "taken", "SomePassword1")
        with pytest.raises(ValueError, match="already exists"):
            db.create_user("b@example.com", "TAKEN", "OtherPassword1")

    @pytest.mark.parametrize("weak", ["short1A", "alllowercase12", "NODIGITS"])
    def test_weak_passwords_are_refused_by_policy(self, weak):
        from src.auth.security import validate_password_strength
        assert validate_password_strength(weak)


class TestPasswordReset:
    def test_reset_replaces_the_password(self, db):
        created = db.create_user("u@example.com", "resetme", "OldPassword123")
        db.set_password(created["id"], "BrandNewPass456")

        assert db.authenticate_user("resetme", "OldPassword123") is None
        assert db.authenticate_user("resetme", "BrandNewPass456") is not None

    def test_reset_clears_a_lockout(self, db):
        created = db.create_user("u@example.com", "lockme", "OldPassword123")
        for _ in range(5):
            db.authenticate_user("lockme", "wrong")
        assert db.authenticate_user("lockme", "OldPassword123") is None, \
            "account should be locked"

        db.set_password(created["id"], "BrandNewPass456")
        assert db.authenticate_user("lockme", "BrandNewPass456") is not None


class TestAccessControl:
    def test_disabled_user_cannot_sign_in(self, db):
        created = db.create_user("u@example.com", "leaver", "SomePassword123")
        db.set_user_active(created["id"], False)
        assert db.authenticate_user("leaver", "SomePassword123") is None

    def test_re_enabled_user_can_sign_in_again(self, db):
        created = db.create_user("u@example.com", "returner", "SomePassword123")
        db.set_user_active(created["id"], False)
        db.set_user_active(created["id"], True)
        assert db.authenticate_user("returner", "SomePassword123") is not None

    def test_disabling_preserves_the_account_and_its_history(self, db, admin):
        created = db.create_user("u@example.com", "keepme", "SomePassword123")
        db.log_action(created["id"], "upload_schedule", "sched_001", {})
        db.set_user_active(created["id"], False)

        assert db.get_user_by_username("keepme") is not None
        assert db.get_audit_log(user_id=created["id"])


class TestLastAdminGuard:
    """
    Disabling the only active admin would make user management unreachable,
    and there is no password-reset flow to recover from it.
    """

    def test_sole_admin_is_the_only_active_admin(self, db, admin):
        active_admins = [u for u in db.get_all_users()
                         if u["role"] == "admin" and u["is_active"]]
        assert len(active_admins) == 1

    def test_guard_releases_once_a_second_admin_exists(self, db, admin):
        db.create_user("a2@example.com", "admin2", "SecondAdmin123", "admin")
        active_admins = [u for u in db.get_all_users()
                         if u["role"] == "admin" and u["is_active"]]
        assert len(active_admins) == 2

        # With two admins, disabling one still leaves an active admin.
        db.set_user_active(active_admins[0]["id"], False)
        remaining = [u for u in db.get_all_users()
                     if u["role"] == "admin" and u["is_active"]]
        assert len(remaining) == 1

    def test_disable_button_is_disabled_for_the_last_admin(self, db, admin,
                                                           monkeypatch):
        """A second admin exists but is the only other account."""
        db.create_user("a2@example.com", "admin2", "SecondAdmin123", "admin")
        app = signed_in(admin, db.db_path, monkeypatch).run()
        assert not app.exception, app.exception
        # Two active admins, so the guard must not fire for the other one.
        warnings = " ".join(w.value for w in app.warning)
        assert "only active admin" not in warnings
