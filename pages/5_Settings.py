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
# Administration is a separate tab rather than a section buried in "About",
# and is only created for admins.
tab_labels = ["👤 User Profile", "📁 Projects", "ℹ️ About"]
if auth.is_admin():
    tab_labels.append("🔐 Administration")

tabs = st.tabs(tab_labels)
tab1, tab2, tab3 = tabs[0], tabs[1], tabs[2]
admin_tab = tabs[3] if auth.is_admin() else None

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

# ---------------------------------------------------------------------------
# Tab 4: Administration (admins only)
# ---------------------------------------------------------------------------
if admin_tab is not None:
    with admin_tab:
        st.markdown("## Administration")

        # ---- User management ----------------------------------------------
        st.markdown("### Users")

        existing_users = db.get_all_users()
        st.dataframe(
            [
                {
                    "Username": u["username"],
                    "Email": u["email"],
                    "Role": u["role"].capitalize(),
                    "Status": "Active" if u["is_active"] else "Disabled",
                    "Created": u["created"][:10],
                }
                for u in existing_users
            ],
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("Create a new user", expanded=len(existing_users) < 2):
            with st.form("create_user_form"):
                new_username = st.text_input(
                    "Username *", placeholder="e.g. m.rossi")
                new_email = st.text_input(
                    "Email", placeholder="e.g. m.rossi@example.com")
                new_role = st.selectbox(
                    "Role *", ["viewer", "admin"],
                    help="Viewers get read-only access. Admins can upload, "
                         "delete and manage users.",
                )
                new_user_password = st.text_input("Password *", type="password")
                st.caption(
                    f"Minimum {settings.MIN_PASSWORD_LENGTH} characters, "
                    f"including an uppercase letter, a lowercase letter and a "
                    f"digit. Send it over a secure channel and ask the user to "
                    f"change it on first sign-in."
                )

                if st.form_submit_button("Create user", type="primary"):
                    problems = validate_password_strength(new_user_password)
                    if not new_username.strip():
                        st.error("Username is required.")
                    elif problems:
                        st.error(" ".join(problems))
                    else:
                        try:
                            created = db.create_user(
                                email=new_email,
                                username=new_username,
                                password=new_user_password,
                                role=new_role,
                            )
                            db.log_action(
                                user["id"], "create_user", created["id"],
                                {"username": created["username"],
                                 "role": created["role"]},
                            )
                            display_success_message(
                                f"User '{created['username']}' created as "
                                f"{created['role']}."
                            )
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))

        with st.expander("Manage an existing user"):
            other_users = [u for u in existing_users if u["id"] != user["id"]]
            active_admins = [u for u in existing_users
                             if u["role"] == "admin" and u["is_active"]]

            if not other_users:
                st.info(
                    "You are the only account. Create another user above to "
                    "manage it here."
                )
            else:
                labels = {}
                for candidate in other_users:
                    suffix = "" if candidate["is_active"] else " - disabled"
                    labels[f"{candidate['username']} "
                           f"({candidate['role']}){suffix}"] = candidate

                chosen = labels[st.selectbox("User", list(labels.keys()))]

                st.markdown("**Reset password**")
                with st.form("reset_password_form"):
                    reset_password = st.text_input(
                        f"New password for {chosen['username']}",
                        type="password",
                    )
                    if st.form_submit_button("Reset password"):
                        problems = validate_password_strength(reset_password)
                        if problems:
                            st.error(" ".join(problems))
                        else:
                            db.set_password(chosen["id"], reset_password)
                            db.log_action(
                                user["id"], "reset_password", chosen["id"],
                                {"username": chosen["username"]},
                            )
                            display_success_message(
                                f"Password reset for '{chosen['username']}'. "
                                f"Any lockout has been cleared."
                            )

                st.markdown("---")
                st.markdown("**Access**")

                # Disabling the last active admin would lock everyone out of
                # user management, and there is no password-reset flow to
                # recover from that.
                is_last_admin = (
                    chosen["role"] == "admin"
                    and chosen["is_active"]
                    and len(active_admins) <= 1
                )

                if chosen["is_active"]:
                    if is_last_admin:
                        st.warning(
                            "This is the only active admin account and cannot "
                            "be disabled."
                        )
                    if st.button(f"Disable {chosen['username']}",
                                 disabled=is_last_admin):
                        db.set_user_active(chosen["id"], False)
                        db.log_action(
                            user["id"], "disable_user", chosen["id"],
                            {"username": chosen["username"]},
                        )
                        display_success_message(
                            f"'{chosen['username']}' can no longer sign in."
                        )
                        st.rerun()
                    st.caption(
                        "Disabling keeps the account and its audit history but "
                        "blocks sign-in. Prefer this to deletion when someone "
                        "leaves the project."
                    )
                else:
                    if st.button(f"Re-enable {chosen['username']}"):
                        db.set_user_active(chosen["id"], True)
                        db.log_action(
                            user["id"], "enable_user", chosen["id"],
                            {"username": chosen["username"]},
                        )
                        display_success_message(
                            f"'{chosen['username']}' can sign in again."
                        )
                        st.rerun()

        # ---- Audit log ------------------------------------------------------
        st.markdown("---")
        st.markdown("### Audit Log")

        audit_entries = db.get_audit_log(limit=200)
        if audit_entries:
            usernames = {u["id"]: u["username"] for u in existing_users}
            st.dataframe(
                [
                    {
                        "Timestamp": entry["timestamp"][:19].replace("T", " "),
                        "User": usernames.get(entry["user_id"],
                                              entry["user_id"] or "-"),
                        "Action": entry["action_type"].replace("_", " ").title(),
                        "Resource": entry["resource_id"],
                    }
                    for entry in audit_entries
                ],
                use_container_width=True,
                hide_index=True,
            )
            st.caption(f"Showing the {len(audit_entries)} most recent entries.")
        else:
            st.info("No audit entries recorded yet.")

        # ---- Maintenance -----------------------------------------------------
        st.markdown("---")
        st.markdown("### Maintenance")

        if st.button("Clear all caches", type="secondary"):
            st.cache_data.clear()
            st.cache_resource.clear()
            display_success_message("Caches cleared successfully.")
            st.rerun()

        st.caption(
            "Clearing caches only discards in-memory cached objects. All "
            "projects, schedules and analyses are stored in the database and "
            "are unaffected."
        )
