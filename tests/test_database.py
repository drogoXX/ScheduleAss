"""Persistence, authentication throttling and referential integrity."""

import pandas as pd
import pytest

from src.database.db_manager import DatabaseManager


class TestBootstrap:
    def test_bootstrap_admin_is_created(self, db):
        assert db.get_user_by_username("admin")["role"] == "admin"

    def test_bootstrap_runs_only_once(self, db, tmp_path):
        """Re-opening the same database must not create a second admin."""
        reopened = DatabaseManager(db_path=db.db_path)
        assert len(reopened.get_all_users()) == 1

    def test_stored_password_is_hashed(self, db):
        """No code path may expose a password, and none is stored in plaintext."""
        user = db.get_user_by_username("admin")
        assert "password" not in user and "password_hash" not in user

        import sqlite3
        conn = sqlite3.connect(db.db_path)
        stored = conn.execute("SELECT password_hash FROM users").fetchone()[0]
        conn.close()
        assert "BootstrapAdminPw1" not in stored
        assert stored.startswith("pbkdf2_sha256$")


class TestAuthentication:
    def test_correct_credentials_succeed(self, db):
        assert db.authenticate_user("admin", "BootstrapAdminPw1") is not None

    def test_username_is_case_insensitive(self, db):
        assert db.authenticate_user("ADMIN", "BootstrapAdminPw1") is not None

    def test_wrong_password_fails(self, db):
        assert db.authenticate_user("admin", "wrong") is None

    def test_unknown_user_fails(self, db):
        assert db.authenticate_user("nobody", "whatever") is None

    @pytest.mark.parametrize("username,password", [
        ("", "x"), ("admin", ""), (None, None),
    ])
    def test_blank_credentials_fail(self, db, username, password):
        assert db.authenticate_user(username, password) is None

    def test_sql_injection_in_username_is_inert(self, db):
        """Parameterised queries mean this is just a username that does not exist."""
        assert db.authenticate_user("admin' OR '1'='1", "x") is None
        assert db.authenticate_user("'; DROP TABLE users; --", "x") is None
        # The table must still be there.
        assert len(db.get_all_users()) == 1

    def test_account_locks_after_repeated_failures(self, db):
        for _ in range(5):
            db.authenticate_user("admin", "wrong")
        assert db.authenticate_user("admin", "BootstrapAdminPw1") is None, \
            "correct password accepted while the account should be locked"

    def test_successful_login_resets_the_failure_counter(self, db):
        for _ in range(3):
            db.authenticate_user("admin", "wrong")
        assert db.authenticate_user("admin", "BootstrapAdminPw1") is not None
        for _ in range(4):
            db.authenticate_user("admin", "wrong")
        # Counter was reset, so 4 more failures must not have locked it.
        assert db.authenticate_user("admin", "BootstrapAdminPw1") is not None

    def test_disabled_user_cannot_log_in(self, db):
        user = db.create_user("u@example.com", "someone", "SomePassword1", "viewer")
        assert db.authenticate_user("someone", "SomePassword1") is not None
        db.set_user_active(user["id"], False)
        assert db.authenticate_user("someone", "SomePassword1") is None


class TestUsers:
    def test_duplicate_username_is_rejected(self, db):
        db.create_user("a@example.com", "dupe", "SomePassword1")
        with pytest.raises(ValueError):
            db.create_user("b@example.com", "DUPE", "OtherPassword1")

    def test_invalid_role_is_rejected(self, db):
        with pytest.raises(ValueError):
            db.create_user("a@example.com", "x", "SomePassword1", role="superuser")

    def test_set_password_changes_the_credential(self, db):
        user = db.create_user("a@example.com", "changer", "OldPassword123")
        db.set_password(user["id"], "NewPassword456")
        assert db.authenticate_user("changer", "OldPassword123") is None
        assert db.authenticate_user("changer", "NewPassword456") is not None


class TestProjects:
    def test_create_and_fetch(self, db, admin):
        project = db.create_project("Refinery", "R-1", "desc", admin["id"])
        assert db.get_project_by_id(project["id"])["project_name"] == "Refinery"
        assert db.get_project_by_code("r-1") is not None

    def test_duplicate_code_is_rejected(self, db, admin):
        db.create_project("A", "DUP-1", "", admin["id"])
        with pytest.raises(ValueError):
            db.create_project("B", "dup-1", "", admin["id"])

    @pytest.mark.parametrize("name,code", [("", "C-1"), ("N", ""), ("  ", "C-2")])
    def test_blank_fields_are_rejected(self, db, admin, name, code):
        with pytest.raises(ValueError):
            db.create_project(name, code, "", admin["id"])


class TestSchedulePersistence:
    def test_schedule_survives_a_new_manager(self, db, admin, parsed_sample):
        project = db.create_project("P", "P-1", "", admin["id"])
        schedule = db.create_schedule(project["id"], parsed_sample, "s.csv", admin["id"])

        reopened = DatabaseManager(db_path=db.db_path)
        loaded = reopened.get_schedule_by_id(schedule["id"])
        assert loaded is not None
        assert (loaded["schedule_data"]["total_activities"]
                == parsed_sample["total_activities"])

    def test_datetime_columns_survive_the_round_trip(self, db, admin, parsed_sample):
        """The analysis layer does date arithmetic, so dtypes must be preserved."""
        project = db.create_project("P", "P-1", "", admin["id"])
        schedule = db.create_schedule(project["id"], parsed_sample, "s.csv", admin["id"])

        loaded = DatabaseManager(db_path=db.db_path).get_schedule_by_id(schedule["id"])
        before = pd.DataFrame(parsed_sample["activities"])
        after = pd.DataFrame(loaded["schedule_data"]["activities"])

        for column in ("Start", "Finish"):
            assert pd.api.types.is_datetime64_any_dtype(after[column]), \
                f"{column} lost its datetime dtype"
            assert after[column].equals(before[column]), f"{column} values changed"

    def test_relationships_survive_the_round_trip(self, db, admin, parsed_sample):
        project = db.create_project("P", "P-1", "", admin["id"])
        schedule = db.create_schedule(project["id"], parsed_sample, "s.csv", admin["id"])
        loaded = DatabaseManager(db_path=db.db_path).get_schedule_by_id(schedule["id"])

        before = pd.DataFrame(parsed_sample["activities"])["predecessor_list"]
        after = pd.DataFrame(loaded["schedule_data"]["activities"])["predecessor_list"]
        assert [list(x) for x in after] == [list(x) for x in before]

    def test_version_numbers_increment_per_project(self, db, admin, parsed_sample):
        project = db.create_project("P", "P-1", "", admin["id"])
        versions = [
            db.create_schedule(project["id"], parsed_sample, f"v{i}.csv",
                               admin["id"])["version_number"]
            for i in range(3)
        ]
        assert versions == [1, 2, 3]

    def test_schedule_for_unknown_project_is_rejected(self, db, admin, parsed_sample):
        with pytest.raises(ValueError):
            db.create_schedule("proj_does_not_exist", parsed_sample, "s.csv",
                               admin["id"])


class TestAnalysisPersistence:
    def _make_schedule(self, db, admin, parsed_sample):
        project = db.create_project("P", "P-1", "", admin["id"])
        return db.create_schedule(project["id"], parsed_sample, "s.csv", admin["id"])

    def test_analysis_is_saved_and_reloaded(self, db, admin, parsed_sample):
        schedule = self._make_schedule(db, admin, parsed_sample)
        db.save_analysis_result(schedule["id"], {"m": 1}, [{"i": 1}], [{"r": 1}], 72.5)

        loaded = DatabaseManager(db_path=db.db_path).get_analysis_by_schedule(
            schedule["id"])
        assert loaded["health_score"] == 72.5
        assert loaded["metrics"] == {"m": 1}

    def test_extra_payload_is_persisted(self, db, admin, parsed_sample):
        """performance_metrics used to live only in memory and vanish on refresh."""
        schedule = self._make_schedule(db, admin, parsed_sample)
        db.save_analysis_result(
            schedule["id"], {}, [], [], 50.0,
            extra={"performance_metrics": {"health_score": {"rating": "Fair"}}},
        )
        loaded = DatabaseManager(db_path=db.db_path).get_analysis_by_schedule(
            schedule["id"])
        assert loaded["performance_metrics"]["health_score"]["rating"] == "Fair"

    def test_resaving_replaces_rather_than_duplicates(self, db, admin, parsed_sample):
        schedule = self._make_schedule(db, admin, parsed_sample)
        db.save_analysis_result(schedule["id"], {}, [], [], 10.0)
        db.save_analysis_result(schedule["id"], {}, [], [], 90.0)

        assert db.count_analyses() == 1
        assert db.get_analysis_by_schedule(schedule["id"])["health_score"] == 90.0

    def test_saving_marks_the_schedule_complete(self, db, admin, parsed_sample):
        schedule = self._make_schedule(db, admin, parsed_sample)
        assert schedule["analysis_status"] == "pending"
        db.save_analysis_result(schedule["id"], {}, [], [], 10.0)
        assert db.get_schedule_by_id(schedule["id"])["analysis_status"] == "complete"

    def test_deleting_a_schedule_cascades_to_its_analysis(self, db, admin,
                                                          parsed_sample):
        schedule = self._make_schedule(db, admin, parsed_sample)
        db.save_analysis_result(schedule["id"], {}, [], [], 10.0)
        db.delete_schedule(schedule["id"], admin["id"])

        assert db.get_analysis_by_schedule(schedule["id"]) is None
        assert db.count_analyses() == 0

    def test_deleting_a_project_cascades_to_schedules(self, db, admin, parsed_sample):
        project = db.create_project("P", "P-1", "", admin["id"])
        db.create_schedule(project["id"], parsed_sample, "s.csv", admin["id"])
        db.delete_project(project["id"], admin["id"])

        assert db.count_schedules() == 0


class TestAuditLog:
    def test_actions_are_recorded(self, db, admin):
        db.create_project("P", "P-1", "", admin["id"])
        actions = [e["action_type"] for e in db.get_audit_log()]
        assert "create_project" in actions

    def test_filtering_by_action(self, db, admin):
        db.create_project("P", "P-1", "", admin["id"])
        db.log_action(admin["id"], "export", "sched_001", {"format": "docx"})

        exports = db.get_audit_log(action_type="export")
        assert len(exports) == 1
        assert exports[0]["details"] == {"format": "docx"}
