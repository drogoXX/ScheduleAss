"""
Schedule Quality Analyzer - Main Application
EPC Schedule Assessment & Analysis Application
"""

import streamlit as st

from src.config import settings
from src.logging_config import get_logger
from src.services import get_auth, get_database
from src.utils.helpers import init_session_state

logger = get_logger("app")

# Page configuration
st.set_page_config(
    page_title="Schedule Quality Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Shared database instance; AuthManager is per-session (it uses session_state).
db = get_database()
auth = get_auth(db)

# Initialize session state
init_session_state()


def show_login_page():
    """Display login page"""
    st.title("🔐 Schedule Quality Analyzer")
    st.subheader("EPC Schedule Assessment & Analysis")

    # Center the login form
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("---")
        st.markdown("### Login")

        with st.form("login_form"):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            submit = st.form_submit_button("Login", use_container_width=True)

            if submit:
                if username and password:
                    if auth.login(username, password):
                        st.success("✅ Login successful!")
                        st.rerun()
                    else:
                        # Deliberately generic: does not reveal whether the
                        # username exists or the account is locked.
                        st.error(
                            "❌ Invalid username or password. "
                            "Repeated failures temporarily lock the account."
                        )
                else:
                    st.warning("⚠️ Please enter both username and password")

        st.markdown("---")

        # About section
        with st.expander("ℹ️ About"):
            st.markdown("""
            ### Schedule Quality Analyzer

            Automate EPC schedule assessment using the industry-standard
            **DCMA 14-Point Schedule Assessment**.

            **Key Features:**
            - Automated schedule quality analysis
            - Real-time risk identification
            - Professional reports (DOCX & Excel)
            - Comparison analytics
            - Multi-user access with role-based permissions

            **Roles:**
            - **Admin**: Full access (upload, analyze, edit, delete)
            - **Viewer**: Read-only access (view dashboards and reports)
            """)


def show_home_page():
    """Display home page for authenticated users"""
    st.title("📊 Schedule Quality Analyzer")

    # User info in sidebar
    with st.sidebar:
        st.markdown("---")
        user = auth.get_current_user()
        if user:
            st.markdown(f"**User:** {user['username']}")
            st.markdown(f"**Role:** {user['role'].capitalize()}")

            if st.button("🚪 Logout", use_container_width=True):
                auth.logout()
                st.rerun()

        st.markdown("---")

    # Welcome message
    user = auth.get_current_user()
    st.markdown(f"### Welcome, {user['username']}! 👋")

    # Quick stats
    st.markdown("---")
    st.markdown("### Quick Overview")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Projects", len(db.get_all_projects()))

    with col2:
        st.metric("Schedules", db.count_schedules())

    with col3:
        st.metric("Analyses", db.count_analyses())

    with col4:
        st.metric("Users", len(db.get_all_users()))

    st.markdown("---")

    # Navigation guide
    st.markdown("### Getting Started")

    if auth.is_admin():
        st.info("""
        **As an Admin, you can:**
        1. **Upload Schedule** - Upload P6 schedule CSV files for analysis
        2. **Analysis Dashboard** - View comprehensive schedule quality metrics
        3. **Comparison** - Compare multiple schedule versions
        4. **Reports** - Generate and download professional reports
        5. **Settings** - Manage projects and preferences
        """)
    else:
        st.info("""
        **As a Viewer, you can:**
        1. **Analysis Dashboard** - View schedule quality metrics and insights
        2. **Comparison** - Compare schedule versions side-by-side
        3. **Reports** - Download generated reports

        *Note: Upload and edit functions require Admin privileges.*
        """)

    # Recent activity
    st.markdown("---")
    st.markdown("### Recent Projects")

    projects = db.get_all_projects()

    if projects:
        for project in projects[-5:]:  # Show last 5 projects
            with st.expander(f"📁 {project['project_name']} ({project['project_code']})"):
                st.markdown(f"**Description:** {project.get('description', 'N/A')}")
                st.markdown(f"**Created:** {project.get('created', 'N/A')}")

                # Get schedules for this project
                project_schedules = db.get_schedules_by_project(project['id'])
                st.markdown(f"**Schedules:** {len(project_schedules)}")
    else:
        st.info("No projects yet. Upload a schedule to get started!")

    # Help section
    st.markdown("---")
    with st.expander("❓ Help & Documentation"):
        st.markdown("""
        ### How to Use

        **1. Upload a Schedule**
        - Navigate to "Upload Schedule" page
        - Drag and drop your P6 CSV export file
        - Select or create a project
        - Click "Upload and Analyze"

        **2. View Analysis**
        - Go to "Analysis Dashboard"
        - Select a schedule from the dropdown
        - Explore metrics, issues, and recommendations

        **3. Generate Reports**
        - Visit "Reports" page
        - Select a schedule
        - Download DOCX (executive summary) or Excel (detailed analysis)

        **4. Compare Schedules**
        - Use "Comparison" page
        - Select two schedule versions
        - View side-by-side metrics and improvements

        ### Supported File Format

        P6 CSV export with columns:
        - Activity ID, Activity Name, Activity Status
        - Start, Finish, Total Float, Duration
        - Predecessors, Successors, WBS Code
        - Constraints, Activity Type, Resources

        ### Contact & Support

        For issues or questions, please contact your administrator.
        """)


def main():
    """Main application logic"""
    if not settings.is_production:
        st.sidebar.info(f"Environment: {settings.ENV}")

    if not auth.is_authenticated():
        show_login_page()
    else:
        show_home_page()


if __name__ == "__main__":
    main()
