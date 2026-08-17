"""
Upload Schedule Page
Allows admins to upload and parse P6 schedule CSV files
"""

import streamlit as st
from src.services import get_auth, get_database, invalidate_schedule_caches
from src.parsers.schedule_parser import ScheduleParser
from src.analysis.dcma_analyzer import DCMAAnalyzer
from src.analysis.metrics_calculator import MetricsCalculator
from src.analysis.recommendations import RecommendationsEngine
from src.config import settings
from src.core.ingest.formats import SourceFormat, describe_format, detect_format
from src.logging_config import get_logger
from src.ui.theme import app_header, fmt_count, fmt_score, inject_css
from src.utils.helpers import (
    display_success_message, display_error_message,
    display_warning_message, init_session_state, report_error
)

logger = get_logger("upload")

st.set_page_config(page_title="Upload Schedule", page_icon="📤", layout="wide")
inject_css("Upload Schedule")

# Initialize
init_session_state()
db = get_database()
auth = get_auth(db)

# Check authentication and permissions
auth.require_auth()
auth.require_admin()

app_header("📤 Upload Schedule", "Upload and analyze P6 schedule CSV files")

# User info in sidebar
with st.sidebar:
    st.divider()
    user = auth.get_current_user()
    if user:
        st.markdown(f"**User:** {user['username']}")
        st.markdown(f"**Role:** {user['role'].capitalize()}")
    st.divider()

# Project selection/creation
st.subheader("1. Select or Create Project")

col1, col2 = st.columns([2, 1])

with col1:
    # Get existing projects
    projects = db.get_all_projects()
    project_options = {f"{p['project_name']} ({p['project_code']})": p['id'] for p in projects}

    # A project created below sets these before rerunning, so the new project is
    # selected on the next run. Without this the radio keeps its previous value
    # ("Create new project") across the rerun, the "Use existing project" branch
    # never executes, selected_project_id stays None, and the analyse button is
    # left permanently disabled with the project the user just created sitting
    # unselected. Widget state is keyed so it can be steered from session_state.
    just_created = st.session_state.pop("newly_created_project", None)
    if just_created and just_created in project_options:
        st.session_state["project_mode"] = "Use existing project"
        st.session_state["project_choice"] = just_created

    if project_options:
        use_existing = st.radio(
            "Choose an option:",
            ["Use existing project", "Create new project"],
            horizontal=True,
            key="project_mode",
        )
    else:
        use_existing = "Create new project"
        st.info("No existing projects. Create a new project below.")

    selected_project_id = None

    if use_existing == "Use existing project" and project_options:
        selected_project = st.selectbox(
            "Select Project",
            options=list(project_options.keys()),
            key="project_choice",
        )
        selected_project_id = project_options[selected_project]
    else:
        # Create new project form
        with st.form("new_project_form"):
            st.markdown("#### Create New Project")
            project_name = st.text_input("Project Name *", placeholder="e.g., ABC Refinery Expansion")
            project_code = st.text_input("Project Code *", placeholder="e.g., ABC-2025-001")
            project_desc = st.text_area("Description", placeholder="Brief project description")

            create_project = st.form_submit_button("Create Project", use_container_width=True)

            if create_project:
                if project_name and project_code:
                    # Check if code already exists
                    try:
                        new_project = db.create_project(
                            project_name=project_name,
                            project_code=project_code,
                            description=project_desc,
                            created_by=user['id']
                        )
                    except ValueError as exc:
                        # The database enforces uniqueness, so a concurrent
                        # create cannot slip past a pre-check.
                        display_error_message(str(exc))
                    else:
                        # Hand the new project to the next run, which selects it.
                        # Assigning selected_project_id here would be pointless -
                        # st.rerun() discards this run's local state immediately.
                        st.session_state["newly_created_project"] = (
                            f"{new_project['project_name']} ({new_project['project_code']})"
                        )
                        display_success_message(f"Project '{project_name}' created successfully!")
                        st.rerun()
                else:
                    display_warning_message("Please fill in required fields (Project Name and Code)")

st.markdown("---")

# File upload
st.subheader("2. Upload Schedule File")

uploaded_file = st.file_uploader(
    "Choose a schedule CSV file",
    type=['csv'],
    help="Upload a Primavera P6 or Microsoft Project schedule export in CSV format. "
         "The format is detected automatically from the file's columns."
)

if uploaded_file is not None:
    if uploaded_file.size > settings.max_upload_bytes:
        display_error_message(
            f"File is {uploaded_file.size / 1024 / 1024:.1f} MB, which exceeds "
            f"the {settings.MAX_UPLOAD_MB} MB limit."
        )
        uploaded_file = None
    else:
        st.success(
            f"✅ File uploaded: {uploaded_file.name} "
            f"({uploaded_file.size / 1024:.1f} KB)"
        )

        # Tell the user which tool we think produced the file, before they commit
        # to a run - a misdetected format is much cheaper to catch here.
        detected = detect_format(uploaded_file.getvalue(), uploaded_file.name)
        if detected is SourceFormat.UNKNOWN:
            display_warning_message(
                "Could not recognise this as a P6 or Microsoft Project export. "
                "Analysis will be attempted as P6 and may fail. Check that the export "
                "includes the activity, date, float and relationship columns."
            )
        else:
            st.info(f"Detected format: **{describe_format(detected)}**")
            if detected is SourceFormat.MSPROJECT_CSV:
                st.caption(
                    "Microsoft Project exports carry no activity status or resource data, "
                    "so some DCMA checks cannot be assessed. Summary (rollup) rows are "
                    "identified and excluded from the assessment."
                )

        # Preview file
        with st.expander("📄 Preview File (first 10 rows)"):
            try:
                import io

                import pandas as pd

                preview_df = pd.read_csv(
                    io.BytesIO(uploaded_file.getvalue()),
                    nrows=10,
                    encoding_errors="replace",
                )
                st.dataframe(preview_df, use_container_width=True)
            except Exception as e:
                logger.warning("Preview failed for %r: %s", uploaded_file.name, e)
                display_error_message(
                    "Could not preview this file. It may still analyse "
                    "correctly - try running the analysis."
                )

st.markdown("---")

# Analyze button
st.subheader("3. Upload and Analyze")

# Say what is missing. A disabled button with no explanation reads as a broken
# app: the user cannot tell whether they missed a step or the upload failed.
blockers = []
if selected_project_id is None:
    blockers.append("select or create a project in step 1")
if uploaded_file is None:
    blockers.append("choose a schedule file in step 2")

if blockers:
    st.info(f"To run the analysis, {' and '.join(blockers)}.")

col1, col2, col3 = st.columns([1, 1, 1])

with col2:
    analyze_button = st.button(
        "🚀 Upload and Analyze",
        use_container_width=True,
        disabled=bool(blockers),
        type="primary",
        help=None if not blockers else f"Still needed: {'; '.join(blockers)}.",
    )

if analyze_button:
    if selected_project_id and uploaded_file:
        # Create progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            # Step 1: Parse CSV
            status_text.text("📄 Parsing CSV file...")
            progress_bar.progress(20)

            parser = ScheduleParser()
            file_content = uploaded_file.getvalue()
            schedule_data = parser.parse_csv(file_content, uploaded_file.name)

            if not schedule_data.get('success', False):
                display_error_message("Failed to parse CSV file:")
                for error in schedule_data.get('errors', []):
                    st.error(f"  • {error}")
                st.stop()

            # Show warnings if any
            if schedule_data.get('warnings'):
                for warning in schedule_data['warnings']:
                    display_warning_message(warning)

            progress_bar.progress(40)

            # Step 2: Save to database
            status_text.text("💾 Saving schedule to database...")

            schedule = db.create_schedule(
                project_id=selected_project_id,
                schedule_data=schedule_data,
                file_name=uploaded_file.name,
                uploaded_by=user['id']
            )

            progress_bar.progress(50)

            # Step 3: Run DCMA analysis
            status_text.text("🔍 Running DCMA analysis...")

            analyzer = DCMAAnalyzer(schedule_data)
            dcma_results = analyzer.analyze()

            progress_bar.progress(70)

            # Step 4: Calculate performance metrics
            status_text.text("📊 Calculating performance metrics...")

            metrics_calc = MetricsCalculator(schedule_data, dcma_results['metrics'])
            performance_metrics = metrics_calc.calculate_all_metrics()

            # Generate DCMA 14-Point Summary
            cpli_value = performance_metrics.get('cpli', {}).get('value', 0)
            bei_value = performance_metrics.get('bei', {}).get('value', 0)
            dcma_14_summary = analyzer.get_dcma_14_point_summary(cpli_value, bei_value)

            progress_bar.progress(85)

            # Step 5: Generate recommendations
            status_text.text("💡 Generating recommendations...")

            rec_engine = RecommendationsEngine(
                dcma_results['metrics'],
                performance_metrics,
                dcma_results['issues']
            )
            recommendations = rec_engine.generate_recommendations()

            progress_bar.progress(95)

            # Step 6: Save analysis results
            status_text.text("💾 Saving analysis results...")

            # The derived payloads are persisted alongside the core results.
            # Previously they were only attached to the in-memory dict, so a
            # page refresh degraded the dashboard to "Unknown" ratings.
            analysis = db.save_analysis_result(
                schedule_id=schedule['id'],
                metrics=dcma_results['metrics'],
                issues=dcma_results['issues'],
                recommendations=recommendations,
                health_score=performance_metrics['health_score']['score'],
                extra={
                    'performance_metrics': performance_metrics,
                    'dcma_metrics': dcma_results['metrics'],
                    'dcma_14_point': dcma_14_summary,
                },
            )

            # The cached schedule/analysis readers must not serve results from
            # before this upload.
            invalidate_schedule_caches()

            # Store in session state
            st.session_state.current_schedule = schedule
            st.session_state.current_analysis = analysis
            st.session_state.dcma_14_point = dcma_14_summary

            progress_bar.progress(100)
            status_text.text("✅ Analysis complete!")

            # Display success message
            st.balloons()
            display_success_message(
                f"Schedule uploaded and analyzed successfully! "
                f"Health Score: {fmt_score(performance_metrics['health_score']['score'])}"
            )

            # Display summary
            st.divider()
            st.subheader("📊 Analysis Summary")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                # delta_color="off": the rating is a label, not a change, so it
                # must not be coloured green with an up-arrow.
                st.metric(
                    "Health Score",
                    fmt_score(performance_metrics['health_score']['score']),
                    delta=performance_metrics['health_score']['rating'],
                    delta_color="off"
                )

            with col2:
                st.metric(
                    "Total Activities",
                    fmt_count(schedule_data['total_activities'])
                )

            with col3:
                st.metric(
                    "Issues Found",
                    fmt_count(len(dcma_results['issues']))
                )

            with col4:
                st.metric(
                    "Recommendations",
                    fmt_count(len(recommendations))
                )

            # Next steps
            st.markdown("---")
            st.info("""
            **Next Steps:**
            - View detailed analysis in the **Analysis Dashboard**
            - Compare with other versions in **Comparison**
            - Generate reports in **Reports** page
            """)

        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            report_error(
                "The schedule could not be analysed. The file may be malformed "
                "or contain unexpected values. Please check the file and try "
                "again, or quote the reference below to your administrator.",
                e,
                logger_name="upload",
            )

    else:
        if not selected_project_id:
            display_warning_message("Please select or create a project first")
        if not uploaded_file:
            display_warning_message("Please upload a CSV file")

# Instructions
st.markdown("---")
with st.expander("📖 Upload Instructions"):
    st.markdown("""
    ### How to Upload a Schedule

    **Step 1: Prepare Your P6 Schedule**
    - Export your schedule from Primavera P6 as CSV
    - Ensure the export includes these columns:
      - Activity ID, Activity Name, Activity Status
      - Start, Finish, Total Float
      - Predecessors, Successors
      - WBS Code, Duration, Constraints

    **Step 2: Select or Create Project**
    - Choose an existing project from the dropdown, OR
    - Create a new project by entering name and code

    **Step 3: Upload File**
    - Click "Browse files" or drag and drop your CSV file
    - File size limit: 50 MB
    - Supported format: CSV only

    **Step 4: Analyze**
    - Click "Upload and Analyze" button
    - Wait for the analysis to complete (typically 10-30 seconds)
    - View results in the Analysis Dashboard

    ### Supported CSV Format

    The parser expects standard P6 CSV export format with the following columns:

    **Required:**
    - Activity ID
    - Activity Name
    - Activity Status
    - Start
    - Finish
    - Total Float
    - Duration Type

    **Optional (but recommended):**
    - WBS Code
    - At Completion Duration
    - Free Float
    - Predecessors / Predecessor Details
    - Successors / Successor Details
    - Primary Constraint
    - Activity Type
    - Resource Names

    ### Troubleshooting

    **"Missing required columns" error:**
    - Verify your P6 export settings include all required fields
    - Check column names match expected format

    **"Failed to parse CSV" error:**
    - Ensure file is valid CSV format
    - Check for special characters or formatting issues
    - Try re-exporting from P6

    **Analysis takes too long:**
    - Large schedules (>5000 activities) may take longer
    - Ensure stable internet connection
    - Contact admin if issues persist
    """)
