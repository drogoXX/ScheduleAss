"""
Settings Page
Application settings and user preferences
"""

import streamlit as st

from src.services import get_auth, get_database
from src.auth.security import validate_password_strength
from src.config import settings
from src.utils.helpers import init_session_state, display_success_message

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")

# Initialize
init_session_state()
db = get_database()
auth = get_auth(db)

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

            user_schedules = [s for s in db.get_all_schedules()
                              if s.get('uploaded_by') == user['id']]
            st.metric("Schedules Uploaded", len(user_schedules))

            user_projects = [p for p in db.get_all_projects()
                             if p.get('created_by') == user['id']]
            st.metric("Projects Created", len(user_projects))

    st.markdown("---")
    st.markdown("### Change Password")

    with st.form("change_password_form"):
        current_password = st.text_input("Current password", type="password")
        new_password = st.text_input("New password", type="password")
        confirm_password = st.text_input("Confirm new password", type="password")
        st.caption(
            f"Minimum {settings.MIN_PASSWORD_LENGTH} characters, including an "
            f"uppercase letter, a lowercase letter and a digit."
        )

        if st.form_submit_button("Update password"):
            if new_password != confirm_password:
                st.error("❌ The new passwords do not match.")
            else:
                ok, message = auth.change_password(current_password, new_password)
                if ok:
                    st.success(f"✅ {message}")
                else:
                    st.error(f"❌ {message}")

# Tab 2: Projects
with tab2:
    st.markdown("## Project Management")

    projects = db.get_all_projects()

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
                    confirm_key = f"confirm_del_{project['id']}"
                    st.checkbox(
                        f"I understand this permanently deletes "
                        f"{len(project_schedules)} schedule(s) and their analyses",
                        key=confirm_key,
                    )
                    if st.button("🗑️ Delete Project", key=f"del_{project['id']}",
                                 disabled=not st.session_state.get(confirm_key)):
                        db.delete_project(project['id'], user['id'])
                        display_success_message(
                            f"Project '{project['project_name']}' deleted."
                        )
                        st.rerun()
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
    - ✅ Real-time schedule quality analysis
    - ✅ Professional report generation (DOCX & Excel)
    - ✅ Schedule version comparison
    - ✅ Multi-user access with role-based permissions

    ### Technology Stack

    - **Frontend:** Streamlit 1.28+
    - **Backend:** Python 3.11+
    - **Database:** SQLite (durable, file-backed)
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

    **Schedule Health Score**

    The 0-100 health score is a weighted average of the DCMA checks above. Each
    check scores 100 at or better than its DCMA target and falls linearly to 0
    at a defined bound; checks without data are excluded and the remaining
    weights renormalised. The full weighting is shown on the Analysis Dashboard
    under "How this score is calculated".

    Thresholds follow the DCMA 14-Point Assessment. The weights are this
    application's assessment of relative severity, not a DCMA-defined figure.

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

        st.markdown("**Stored Records:**")
        st.write(f"- Users: {len(db.get_all_users())}")
        st.write(f"- Projects: {len(db.get_all_projects())}")
        st.write(f"- Schedules: {db.count_schedules()}")
        st.write(f"- Analyses: {db.count_analyses()}")
        st.write(f"- Environment: {settings.ENV}")

    # Admin-only actions
    if auth.is_admin():
        st.markdown("---")
        st.markdown("### Admin Actions")

        if st.button("🔄 Clear All Caches", type="secondary"):
            st.cache_data.clear()
            st.cache_resource.clear()
            display_success_message("Caches cleared successfully!")
            st.rerun()

        st.caption(
            "Clearing caches only discards in-memory cached objects. "
            "All projects, schedules and analyses are stored in the database "
            "and are unaffected."
        )

        st.markdown("---")
        st.markdown("### Audit Log")

        audit_entries = db.get_audit_log(limit=200)
        if audit_entries:
            st.dataframe(
                [
                    {
                        "Timestamp": entry["timestamp"],
                        "User": entry["user_id"],
                        "Action": entry["action_type"],
                        "Resource": entry["resource_id"],
                    }
                    for entry in audit_entries
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No audit entries recorded yet.")

        st.markdown("---")
        st.markdown("### User Management")

        existing_users = db.get_all_users()
        st.dataframe(
            [
                {
                    "Username": u["username"],
                    "Email": u["email"],
                    "Role": u["role"],
                    "Active": u["is_active"],
                    "Created": u["created"],
                }
                for u in existing_users
            ],
            use_container_width=True,
            hide_index=True,
        )

        with st.form("create_user_form"):
            st.markdown("**Create a new user**")
            new_username = st.text_input("Username")
            new_email = st.text_input("Email")
            new_role = st.selectbox("Role", ["viewer", "admin"])
            new_user_password = st.text_input("Password", type="password")

            if st.form_submit_button("Create user"):
                problems = validate_password_strength(new_user_password)
                if not new_username.strip():
                    st.error("❌ Username is required.")
                elif problems:
                    st.error("❌ " + " ".join(problems))
                else:
                    try:
                        created = db.create_user(
                            email=new_email,
                            username=new_username,
                            password=new_user_password,
                            role=new_role,
                        )
                        db.log_action(user['id'], 'create_user', created['id'],
                                      {'username': created['username']})
                        display_success_message(
                            f"User '{created['username']}' created."
                        )
                        st.rerun()
                    except ValueError as exc:
                        st.error(f"❌ {exc}")
