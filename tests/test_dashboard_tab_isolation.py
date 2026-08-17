"""A tab that has no data must not take the rest of the dashboard down with it.

st.stop() raises StopException, which subclasses BaseException - so it escapes the
tab's `except Exception` handler and halts the whole script. Two of them sat inside
the Float Analysis tab, which meant a schedule that tripped either guard rendered
tabs 1-3 and silently lost tabs 4-7 (WBS, Issues, Recommendations, Activities).
"""

from datetime import datetime, timezone

import pytest
from streamlit.testing.v1 import AppTest

TIMEOUT = 180
DASHBOARD = "pages/2_Analysis_Dashboard.py"


def seed_schedule_without_activities():
    """A schedule whose stored data has no activity list - trips the tab 3 guard."""
    from src.services import get_database, invalidate_schedule_caches

    db = get_database()
    admin = db.authenticate_user("admin", "BootstrapAdminPw1")
    project = db.create_project("Empty", "EMPTY-1", "", admin["id"])
    schedule_data = {
        "success": True,
        "file_name": "empty.csv",
        "upload_date": datetime.now(timezone.utc).isoformat(),
        "total_activities": 0,
        "activities": [],          # <- the condition tab 3 guards against
        "metadata": {},
        "warnings": [],
    }
    sched = db.create_schedule(project["id"], schedule_data, "empty.csv", admin["id"])
    db.save_analysis_result(
        schedule_id=sched["id"], metrics={}, issues=[], recommendations=[],
        health_score=50.0, extra={"performance_metrics": {}, "dcma_14_point": {}},
    )
    invalidate_schedule_caches()
    return admin


def run_dashboard(admin):
    app = AppTest.from_file(DASHBOARD, default_timeout=TIMEOUT)
    app.session_state["authenticated"] = True
    app.session_state["user"] = {
        "id": admin["id"], "username": "admin",
        "email": "admin@example.com", "role": "admin",
    }
    app.session_state["last_activity"] = datetime.now(timezone.utc).isoformat()
    return app.run()


def test_empty_activities_does_not_truncate_the_page():
    """The whole dashboard must still render when Float Analysis has no data."""
    admin = seed_schedule_without_activities()
    app = run_dashboard(admin)

    assert not app.exception, [str(e.value) for e in app.exception]

    # The tabs container is rendered whole, so presence of the tab labels is not
    # proof. What proves the script ran to the end is content emitted *after*
    # tab 3 - the later tabs' own markdown.
    rendered = " ".join(str(m.value) for m in app.markdown)
    assert "Activity Details" in rendered or "Recommendations" in rendered, (
        "page was truncated at the Float Analysis tab - content from later tabs "
        "is missing, which is what st.stop() inside a tab causes"
    )


def test_float_tab_reports_missing_data():
    """The user should still be told why Float Analysis is empty."""
    admin = seed_schedule_without_activities()
    app = run_dashboard(admin)
    text = " ".join(str(m.value) for m in list(app.warning) + list(app.info))
    assert "activity data" in text.lower() or "no data" in text.lower()
