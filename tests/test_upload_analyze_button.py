"""Regression tests for the 'Upload and Analyze' button enablement.

The bug: creating a project left the radio on "Create new project" across the
st.rerun(), so the "Use existing project" branch never ran, selected_project_id
stayed None, and the button was permanently disabled - with the project the user
had just created sitting unselected, and no explanation on screen.
"""

from datetime import datetime, timezone

from streamlit.testing.v1 import AppTest

TIMEOUT = 60
UPLOAD_PAGE = "pages/1_Upload_Schedule.py"


def authed():
    app = AppTest.from_file(UPLOAD_PAGE, default_timeout=TIMEOUT)
    app.session_state["authenticated"] = True
    app.session_state["user"] = {
        "id": "user_001", "username": "admin", "email": "admin@example.com", "role": "admin",
    }
    app.session_state["last_activity"] = datetime.now(timezone.utc).isoformat()
    return app


def analyze_button(app):
    for button in app.button:
        if "Analyze" in button.label:
            return button
    raise AssertionError("Upload and Analyze button not rendered")


def create_project(app, name, code):
    """Fill and submit the create-project form."""
    app.text_input[0].set_value(name)
    app.text_input[1].set_value(code)
    submit = [b for b in app.button if "Create Project" in b.label][0]
    return submit.click().run()


class TestProjectSelectionAfterCreate:
    def test_first_project_is_selected_automatically(self):
        app = authed().run()
        create_project(app, "Project A", "A-1")

        assert app.radio[0].value == "Use existing project"
        assert app.selectbox[0].value == "Project A (A-1)"

    def test_second_project_is_selected_automatically(self):
        """The regression: creating a project while one already exists."""
        app = authed().run()
        create_project(app, "Project A", "A-1")

        # User switches to add another project - this is what stuck before.
        app.radio[0].set_value("Create new project").run()
        create_project(app, "VRATO ZEVO", "VRATO-001")

        assert app.radio[0].value == "Use existing project", (
            "radio stayed on 'Create new project' after the rerun, so the new "
            "project was never selected"
        )
        assert app.selectbox[0].value == "VRATO ZEVO (VRATO-001)", (
            "the newly created project should be pre-selected"
        )

    def test_user_can_still_switch_to_create_mode(self):
        """The auto-select must not trap the user on the existing-project branch."""
        app = authed().run()
        create_project(app, "Project A", "A-1")

        app.radio[0].set_value("Create new project").run()
        assert app.radio[0].value == "Create new project"
        assert not app.selectbox


class TestDisabledButtonExplained:
    def test_no_project_and_no_file_explains_both(self):
        app = authed().run()
        assert analyze_button(app).disabled is True
        text = " ".join(str(m.value) for m in app.info)
        assert "project" in text.lower()
        assert "file" in text.lower()

    def test_with_project_but_no_file_asks_only_for_the_file(self):
        app = authed().run()
        create_project(app, "Project A", "A-1")

        assert analyze_button(app).disabled is True
        text = " ".join(str(m.value) for m in app.info)
        assert "file" in text.lower()
        assert "select or create a project" not in text.lower(), (
            "should not ask for a project once one is selected"
        )

    def test_button_help_names_what_is_missing(self):
        app = authed().run()
        assert "Still needed" in (analyze_button(app).help or "")
