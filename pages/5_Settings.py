"""
Settings Page
Application settings and user preferences
"""

import streamlit as st
from src.database.db_manager import DatabaseManager
from src.auth.auth_manager import AuthManager
from src.utils.helpers import init_session_state, display_success_message

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")

# Initialize
init_session_state()
db = DatabaseManager()
auth = AuthManager(db)

# Check authentication
auth.require_auth()

st.title("⚙️ Settings")

# User info in sidebar
with st.sidebar:
    st.markdown("---")
    user = auth.get_current_user()
    if user:
        st.markdown(f"**User:** {user['username']}")
        st.markdown(f"**Role:** {user['role'].capitalize()}")
    st.markdown("---")

# Tabs for different settings
tab1, tab2, tab3 = st.tabs(["👤 User Profile", "📁 Projects", "ℹ️ About"])

# Tab 1: User Profile
with tab1:
    st.markdown("## User Profile")

    if user:
        col1, col2 = st.columns([1, 2])

        with col1:
            st.markdown("### Current User")
            st.info(f"""
            **Username:** {user['username']}
            **Email:** {user['email']}
            **Role:** {user['role'].capitalize()}
            **User ID:** {user['id']}
            """)

        with col2:
            st.markdown("### Account Information")

            # Get full user data
            full_user = db.get_user_by_id(user['id'])

            if full_user:
                st.write(f"**Created:** {full_user.get('created', 'N/A')}")
                st.write(f"**Last Updated:** {full_user.get('updated', 'N/A')}")

            st.markdown("---")

            # Activity summary
            st.markdown("### My Activity")

            # Get user's uploads
            user_schedules = [s for s in st.session_state.schedules
                            if s.get('uploaded_by') == user['id']]

            st.metric("Schedules Uploaded", len(user_schedules))

            # Get user's projects
            user_projects = [p for p in st.session_state.projects
                           if p.get('created_by') == user['id']]

            st.metric("Projects Created", len(user_projects))

# Tab 2: Projects
with tab2:
    st.markdown("## Project Management")

    projects = st.session_state.projects

    if projects:
        st.markdown(f"### All Projects ({len(projects)})")

        for project in projects:
            with st.expander(f"📁 {project['project_name']} ({project['project_code']})"):
                col1, col2 = st.columns([2, 1])

                with col1:
                    st.write(f"**Description:** {project.get('description', 'N/A')}")
                    st.write(f"**Created:** {project.get('created', 'N/A')}")

                    # Get project creator
                    creator = db.get_user_by_id(project.get('created_by', ''))
                    creator_name = creator['username'] if creator else 'Unknown'
                    st.write(f"**Created By:** {creator_name}")

                with col2:
                    # Get schedules for this project
                    project_schedules = db.get_schedules_by_project(project['id'])
                    st.metric("Schedules", len(project_schedules))

                # List schedules
                if project_schedules:
                    st.markdown("**Schedules:**")
                    for sched in project_schedules:
                        st.write(f"  • v{sched['version_number']}: {sched['file_name']} "
                               f"({sched['upload_date'][:10]})")

                # Delete option (admin only)
                if auth.is_admin():
                    st.markdown("---")
                    if st.button(f"🗑️ Delete Project", key=f"del_{project['id']}"):
                        st.warning("⚠️ Delete functionality coming soon")
    else:
        st.info("No projects created yet")

# Tab 3: About
with tab3:
    st.markdown("## About Schedule Quality Analyzer")

    st.markdown("""
    ### Application Information

    **Version:** 1.0.0
    **Release Date:** November 2, 2025

    ### Description

    The Schedule Quality Analyzer is a web-based application designed to automate the assessment
    and analysis of EPC project schedules against industry best practices.

    ### Key Features

    - ✅ Automated DCMA 14-Point Schedule Assessment
    - ✅ GAO Schedule Assessment Guide compliance
    - ✅ Real-time schedule quality analysis
    - ✅ Professional report generation (DOCX & Excel)
    - ✅ Schedule version comparison
    - ✅ Multi-user access with role-based permissions

    ### Technology Stack

    - **Frontend:** Streamlit 1.28+
    - **Backend:** Python 3.11+
    - **Database:** Session-based (upgradeable to Pocketbase)
    - **Data Processing:** Pandas, NumPy
    - **Visualization:** Plotly, Altair
    - **Reports:** python-docx, openpyxl

    ### Methodology

    **DCMA 14-Point Assessment**

    The Defense Contract Management Agency (DCMA) 14-Point Assessment is an industry-standard
    framework for evaluating schedule quality. It examines:

    1. Logic completeness
    2. Lead/lag relationships
    3. Relationship types
    4. Hard constraints
    5. High float
    6. Negative float
    7. Resource loading
    8. Critical path length
    9. Activity durations
    10. Schedule updates
    11. Baseline maintenance
    12. And more...

    **GAO Schedule Assessment Guide**

    The Government Accountability Office (GAO) Schedule Assessment Guide provides
    best practices for:

    - Schedule planning
    - Baseline development
    - Progress tracking
    - Risk analysis
    - Resource allocation

    ### Support

    For technical support or questions:
    - Contact your system administrator
    - Review the documentation in each page
    - Check the Help sections (❓ expandable panels)

    ### License

    Copyright © 2025 Schedule Quality Analyzer
    All rights reserved.

    ### Acknowledgments

    Built with:
    - Streamlit - Modern web framework for Python
    - Plotly - Interactive visualization library
    - python-docx - Document generation
    - openpyxl - Excel file handling
    """)

    st.markdown("---")

    # System information
    with st.expander("🔧 System Information"):
        import sys
        import platform

        st.write(f"**Python Version:** {sys.version}")
        st.write(f"**Platform:** {platform.platform()}")
        st.write(f"**Streamlit Version:** {st.__version__}")

        # Session state info
        st.markdown("**Session Statistics:**")
        st.write(f"- Users: {len(st.session_state.users)}")
        st.write(f"- Projects: {len(st.session_state.projects)}")
        st.write(f"- Schedules: {len(st.session_state.schedules)}")
        st.write(f"- Analyses: {len(st.session_state.analysis_results)}")
        st.write(f"- Audit Logs: {len(st.session_state.audit_log)}")

    # Clear cache option (admin only)
    if auth.is_admin():
        st.markdown("---")
        st.markdown("### Admin Actions")

        if st.button("🔄 Clear All Caches", type="secondary"):
            st.cache_data.clear()
            st.cache_resource.clear()
            display_success_message("Caches cleared successfully!")
            st.rerun()

        st.warning("⚠️ Clearing caches will reset application state but preserve data in session.")
