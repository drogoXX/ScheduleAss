"""
Page-level tests using Streamlit's own harness.

These actually execute app.py and each page script, which is the only way to
catch import errors, stale session_state references and broken auth gates -
starting the server alone proves nothing, because Streamlit does not run the
script until a session connects.
"""

import pytest
from streamlit.testing.v1 import AppTest

from src.analysis.dcma_analyzer import DCMAAnalyzer
from src.analysis.metrics_calculator import MetricsCalculator
from src.database.db_manager import DatabaseManager
from src.parsers.schedule_parser import ScheduleParser

TIMEOUT = 60

PAGES = [
    "pages/1_Upload_Schedule.py",
    "pages/2_Analysis_Dashboard.py",
    "pages/3_Comparison.py",
    "pages/4_Reports.py",
    "pages/5_Settings.py",
]


def seed(db, sample_csv_bytes, admin, versions=1):
    """Create a project with analysed schedule(s)."""
    data = ScheduleParser().parse_csv(sample_csv_bytes, "sample.csv")
    project = db.create_project("Seeded", "SEED-1", "", admin["id"])

    schedules = []
    for index in range(versions):
        schedule = db.create_schedule(project["id"], data, f"v{index + 1}.csv",
                                      admin["id"])
        analyzer = DCMAAnalyzer(data)
        dcma = analyzer.analyze()
        performance = MetricsCalculator(data, dcma["metrics"]).calculate_all_metrics()
        db.save_analysis_result(
            schedule["id"], dcma["metrics"], dcma["issues"], [],
            performance["health_score"]["score"],
            extra={
                "performance_metrics": performance,
                "dcma_metrics": dcma["metrics"],
                "dcma_14_point": analyzer.get_dcma_14_point_summary(
                    performance["cpli"]["value"], performance["bei"]["value"]),
            },
        )
        schedules.append(schedule)
    return project, schedules


def signed_in(script, user):
    """Run a script with an authenticated session."""
    from datetime import datetime, timezone

    app = AppTest.from_file(script, default_timeout=TIMEOUT)
    app.session_state["authenticated"] = True
    app.session_state["user"] = {
        "id": user["id"], "username": user["username"],
        "email": user["email"], "role": user["role"],
    }
    app.session_state["last_activity"] = datetime.now(timezone.utc).isoformat()
    return app


class TestMainApp:
    def test_login_page_renders_for_anonymous_visitors(self, isolated_environment):
        app = AppTest.from_file("app.py", default_timeout=TIMEOUT).run()
        assert not app.exception, app.exception
        assert any("Schedule Quality Analyzer" in t.value for t in app.title)

    def test_demo_credentials_are_not_published(self, isolated_environment):
        """The login page used to print working admin/viewer passwords."""
        app = AppTest.from_file("app.py", default_timeout=TIMEOUT).run()
        rendered = " ".join(
            [m.value for m in app.markdown]
            + [i.value for i in app.info]
            + [t.value for t in app.title]
            + [s.value for s in app.subheader]
        )
        for secret in ("admin123", "viewer123", "Demo Credentials"):
            assert secret not in rendered, f"login page still exposes {secret!r}"

    def test_home_page_renders_when_signed_in(self, db, admin, isolated_environment,
                                              monkeypatch):
        monkeypatch.setenv("APP_DB_PATH", str(db.db_path))
        app = signed_in("app.py", admin).run()
        assert not app.exception, app.exception
        assert any("Welcome" in m.value for m in app.markdown)

    def test_home_metrics_read_from_the_database(self, db, admin, sample_csv_bytes,
                                                 monkeypatch):
        monkeypatch.setenv("APP_DB_PATH", str(db.db_path))
        seed(db, sample_csv_bytes, admin)

        app = signed_in("app.py", admin).run()
        assert not app.exception, app.exception

        labelled = {m.label: m.value for m in app.metric}
        assert labelled.get("Projects") == "1"
        assert labelled.get("Schedules") == "1"
        assert labelled.get("Analyses") == "1"


class TestAuthenticationGates:
    @pytest.mark.parametrize("script", PAGES)
    def test_pages_block_anonymous_access(self, script, isolated_environment):
        """Every page must stop before rendering content to a signed-out visitor."""
        app = AppTest.from_file(script, default_timeout=TIMEOUT).run()
        assert not app.exception, app.exception

        warnings = " ".join(w.value for w in app.warning)
        assert "log in" in warnings.lower(), \
            f"{script} did not gate anonymous access"

    def test_upload_page_blocks_viewers(self, db, isolated_environment, monkeypatch):
        monkeypatch.setenv("APP_DB_PATH", str(db.db_path))
        viewer = db.create_user("v@example.com", "viewer1", "ViewerPassword1",
                                "viewer")

        app = signed_in("pages/1_Upload_Schedule.py", viewer).run()
        errors = " ".join(e.value for e in app.error)
        assert "admin privileges" in errors.lower()

    def test_upload_page_allows_admins(self, db, admin, monkeypatch):
        monkeypatch.setenv("APP_DB_PATH", str(db.db_path))
        app = signed_in("pages/1_Upload_Schedule.py", admin).run()
        assert not app.exception, app.exception
        assert not any("admin privileges" in e.value.lower() for e in app.error)


class TestPagesRenderWithData:
    @pytest.fixture
    def seeded(self, db, admin, sample_csv_bytes, monkeypatch):
        monkeypatch.setenv("APP_DB_PATH", str(db.db_path))
        seed(db, sample_csv_bytes, admin, versions=2)
        return admin

    @pytest.mark.parametrize("script", PAGES)
    def test_page_renders_without_exception(self, script, seeded):
        app = signed_in(script, seeded).run()
        assert not app.exception, f"{script} raised: {app.exception}"

    def test_dashboard_shows_a_known_rating(self, seeded):
        """
        The rating comes from performance_metrics, which previously lived only
        in memory and left the dashboard showing "Unknown" after a refresh.
        """
        app = signed_in("pages/2_Analysis_Dashboard.py", seeded).run()
        assert not app.exception, app.exception

        rendered = " ".join(m.value for m in app.markdown)
        assert "Schedule Health Score" in rendered
        assert "Unknown" not in rendered.split("Schedule Health Score")[0][-400:]

    def test_reports_page_offers_both_formats(self, seeded):
        app = signed_in("pages/4_Reports.py", seeded).run()
        assert not app.exception, app.exception
        labels = [b.label for b in app.button]
        assert any("DOCX" in label for label in labels)
        assert any("Excel" in label for label in labels)

    def test_comparison_page_accepts_two_versions(self, seeded):
        app = signed_in("pages/3_Comparison.py", seeded).run()
        assert not app.exception, app.exception
        # With two versions seeded it must not fall back to the "need more
        # schedules" message.
        infos = " ".join(i.value for i in app.info)
        assert "at least 2 schedules" not in infos


class TestEmptyState:
    """A fresh deployment with no data must not error."""

    @pytest.fixture
    def empty(self, db, admin, monkeypatch):
        monkeypatch.setenv("APP_DB_PATH", str(db.db_path))
        return admin

    @pytest.mark.parametrize("script", PAGES)
    def test_page_handles_no_data(self, script, empty):
        app = signed_in(script, empty).run()
        assert not app.exception, f"{script} raised on empty data: {app.exception}"
