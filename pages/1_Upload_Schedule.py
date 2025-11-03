"""
Upload Schedule Page
Allows admins to upload and parse P6 schedule CSV files
"""

import streamlit as st
from src.database.db_manager import DatabaseManager
from src.auth.auth_manager import AuthManager
from src.parsers.schedule_parser import ScheduleParser
from src.analysis.dcma_analyzer import DCMAAnalyzer
from src.analysis.metrics_calculator import MetricsCalculator
from src.analysis.recommendations import RecommendationsEngine
from src.utils.helpers import (
    display_success_message, display_error_message,
    display_warning_message, init_session_state
)

st.set_page_config(page_title="Upload Schedule", page_icon="📤", layout="wide")

# Initialize
init_session_state()
db = DatabaseManager()
auth = AuthManager(db)

# Check authentication and permissions
auth.require_auth()
auth.require_admin()

st.title("📤 Upload Schedule")
st.markdown("Upload and analyze P6 schedule CSV files")

# User info in sidebar
with st.sidebar:
    st.markdown("---")
    user = auth.get_current_user()
    if user:
        st.markdown(f"**User:** {user['username']}")
        st.markdown(f"**Role:** {user['role'].capitalize()}")
    st.markdown("---")

st.markdown("---")

# Project selection/creation
st.subheader("1. Select or Create Project")

col1, col2 = st.columns([2, 1])

with col1:
    # Get existing projects
    projects = db.get_all_projects()
    project_options = {f"{p['project_name']} ({p['project_code']})": p['id'] for p in projects}

    if project_options:
        use_existing = st.radio(
            "Choose an option:",
            ["Use existing project", "Create new project"],
            horizontal=True
        )
    else:
        use_existing = "Create new project"
        st.info("No existing projects. Create a new project below.")

    selected_project_id = None

    if use_existing == "Use existing project" and project_options:
        selected_project = st.selectbox(
            "Select Project",
            options=list(project_options.keys())
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
                    existing = db.get_project_by_code(project_code)
                    if existing:
                        display_error_message(f"Project code '{project_code}' already exists")
                    else:
                        new_project = db.create_project(
                            project_name=project_name,
                            project_code=project_code,
                            description=project_desc,
                            created_by=user['id']
                        )
                        selected_project_id = new_project['id']
                        display_success_message(f"Project '{project_name}' created successfully!")
                        st.rerun()
                else:
                    display_warning_message("Please fill in required fields (Project Name and Code)")

st.markdown("---")

# File upload
st.subheader("2. Upload Schedule File")

uploaded_file = st.file_uploader(
    "Choose a P6 CSV file",
    type=['csv'],
    help="Upload a Primavera P6 schedule export in CSV format"
)

if uploaded_file is not None:
    st.success(f"✅ File uploaded: {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")

    # Preview file
    with st.expander("📄 Preview File (first 10 rows)"):
        try:
            import pandas as pd
            import io
            preview_df = pd.read_csv(io.BytesIO(uploaded_file.getvalue()), nrows=10)
            st.dataframe(preview_df, use_container_width=True)
        except Exception as e:
            display_error_message(f"Could not preview file: {str(e)}")

st.markdown("---")

# Analyze button
st.subheader("3. Upload and Analyze")

col1, col2, col3 = st.columns([1, 1, 1])

with col2:
    analyze_button = st.button(
        "🚀 Upload and Analyze",
        use_container_width=True,
        disabled=(uploaded_file is None or selected_project_id is None),
        type="primary"
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

            analysis = db.save_analysis_result(
                schedule_id=schedule['id'],
                metrics=dcma_results['metrics'],
                issues=dcma_results['issues'],
                recommendations=recommendations,
                health_score=performance_metrics['health_score']['score']
            )

            # Add performance metrics and DCMA 14-point summary to analysis
            analysis['performance_metrics'] = performance_metrics
            analysis['dcma_metrics'] = dcma_results['metrics']
            analysis['dcma_14_point'] = dcma_14_summary

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
                f"Health Score: {performance_metrics['health_score']['score']:.1f}/100"
            )

            # Display summary
            st.markdown("---")
            st.subheader("📊 Analysis Summary")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    "Health Score",
                    f"{performance_metrics['health_score']['score']:.1f}/100",
                    delta=performance_metrics['health_score']['rating']
                )

            with col2:
                st.metric(
                    "Total Activities",
                    schedule_data['total_activities']
                )

            with col3:
                st.metric(
                    "Issues Found",
                    len(dcma_results['issues'])
                )

            with col4:
                st.metric(
                    "Recommendations",
                    len(recommendations)
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
            display_error_message(f"An error occurred during analysis: {str(e)}")
            st.exception(e)

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
