"""
Reports Page
Generate and download professional reports (DOCX and Excel)
"""

import streamlit as st
from datetime import datetime
from src.services import get_auth, get_database, load_analysis, load_schedule
from src.reports.docx_generator import DOCXGenerator
from src.reports.excel_generator import ExcelGenerator
from src.ui.diagnostics import timed
from src.ui.theme import (
    app_header, fmt_count, fmt_score, inject_css, section_divider,
)
from src.utils.helpers import (
    init_session_state, display_no_data_message,
    display_success_message, display_error_message, report_error
)

st.set_page_config(page_title="Reports", page_icon="📄", layout="wide")
inject_css("Reports")

# Initialize
init_session_state()
db = get_database()
auth = get_auth(db)

# Check authentication
auth.require_auth()

app_header(
    "📄 Reports",
    "Generate and download professional schedule analysis reports",
)

# User info in sidebar
with st.sidebar:
    st.divider()
    user = auth.get_current_user()
    if user:
        st.markdown(f"**User:** {user['username']}")
        st.markdown(f"**Role:** {user['role'].capitalize()}")
    st.divider()

# Schedule selection
st.markdown("### Select Schedule")

schedules = db.get_all_schedules()
if not schedules:
    display_no_data_message("No schedules uploaded yet. Please upload a schedule first.")
    st.stop()

# Create schedule selector
schedule_options = {}
for schedule in schedules:
    project = db.get_project_by_id(schedule['project_id'])
    project_name = project['project_name'] if project else "Unknown Project"
    label = f"{project_name} - v{schedule['version_number']} ({schedule['file_name']})"
    schedule_options[label] = schedule['id']

selected_schedule_label = st.selectbox(
    "Choose a schedule for report generation:",
    options=list(schedule_options.keys())
)

selected_schedule_id = schedule_options[selected_schedule_label]

try:
    # Timed: this is the largest read in the app (the full schedule JSON) and
    # the prime suspect if this page ever appears to hang.
    # Do not stringify `analysis` for display here - it is ~3M characters and this
    # block re-runs on every widget interaction (~35ms + 3MB allocated each time).
    with timed("Reports: load schedule"):
        schedule = load_schedule(selected_schedule_id)
    with timed("Reports: load analysis"):
        analysis = load_analysis(selected_schedule_id)
except Exception as e:
    report_error("Could not load the selected schedule.", e, logger_name="reports")
    st.stop()

if not analysis:
    display_no_data_message("No analysis results available for this schedule.")
    st.stop()

# Get project info
project = db.get_project_by_id(schedule['project_id'])
project_name = project['project_name'] if project else "Unknown Project"

st.markdown("---")

# Wrap everything in try-except to catch rendering errors
try:
    # Report preview
    st.markdown("### Report Preview")

    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("#### Schedule Information")
        st.write(f"**Project:** {project_name}")
        st.write(f"**Version:** {schedule['version_number']}")
        st.write(f"**File:** {schedule['file_name']}")
        st.write(f"**Upload Date:** {schedule['upload_date'][:10]}")
        st.write(f"**Activities:** {fmt_count(schedule['schedule_data']['total_activities'])}")
    
    with col2:
        st.markdown("#### Analysis Summary")
    
        try:
            health_score = analysis.get('health_score', 0)
    
            # Get performance metrics if available
            if 'performance_metrics' in analysis:
                perf_metrics = analysis['performance_metrics']
                health_data = perf_metrics.get('health_score', {})
                rating = health_data.get('rating', 'Unknown')
            else:
                rating = 'Unknown'
    
            st.write(f"**Health Score:** {fmt_score(health_score)}")
            st.write(f"**Rating:** {rating}")
            st.write(f"**Issues Found:** {fmt_count(len(analysis.get('issues', [])))}")
            st.write(f"**Recommendations:** {fmt_count(len(analysis.get('recommendations', [])))}")
        except Exception as e:
            report_error(
                "Could not load the analysis summary. If this analysis was "
                "created by an older version of the application, re-analyse "
                "the schedule.",
                e,
                logger_name="reports",
            )
    
    st.markdown("---")
    
    # Report generation
    st.markdown("### Generate Reports")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📝 Executive Summary (DOCX)")
        st.info("""
        **Contains:**
        - Cover page with health score
        - Table of contents, running header and page numbers
        - Executive summary
        - DCMA 14-Point compliance checklist and charts
        - Key performance metrics (CPLI, BEI)
        - Issues summary table
        - Prioritized recommendations
        - Methodology appendix

        **Best for:** Stakeholder presentations, client reports
        """)

        if st.button("📥 Generate DOCX Report", use_container_width=True, type="primary"):
            with st.spinner("Generating DOCX report..."):
                try:
                    # Prepare analysis results with performance metrics and DCMA 14-point
                    full_analysis = {
                        'dcma_metrics': analysis['metrics'],
                        'performance_metrics': analysis.get('performance_metrics', {}),
                        'dcma_14_point': analysis.get('dcma_14_point', {}),
                        'issues': analysis['issues'],
                        'recommendations': analysis.get('recommendations', [])
                    }

                    # Generate DOCX
                    docx_gen = DOCXGenerator(
                        project_name=project_name,
                        schedule_data=schedule['schedule_data'],
                        analysis_results=full_analysis
                    )

                    filename = f"Schedule_Analysis_{project_name}_v{schedule['version_number']}_{datetime.now().strftime('%Y%m%d')}.docx"

                    # Timed: DOCX generation renders charts through kaleido,
                    # which launches a browser engine and is the slowest step
                    # in the app.
                    with timed("Reports: generate DOCX", warn_after=5.0):
                        docx_bytes = docx_gen.generate()

                    # Cache the bytes in session state. Clicking a download
                    # button triggers a rerun, so a button created inside this
                    # `if st.button(...)` branch would vanish before it could be
                    # used; holding the payload outside the branch keeps it.
                    st.session_state.docx_report = {
                        'data': docx_bytes,
                        'filename': filename,
                        'schedule_id': schedule['id'],
                    }

                    display_success_message("DOCX report generated successfully!")

                    # Log action
                    db.log_action(user['id'], 'export', schedule['id'],
                                 {'report_type': 'docx', 'filename': filename})

                except Exception as e:
                    report_error("Failed to generate the DOCX report.", e,
                                 logger_name="reports")

        # Rendered outside the button branch so it survives the rerun. Scoped to
        # the selected schedule, so switching schedules cannot hand the user a
        # report for a different one.
        docx_report = st.session_state.get('docx_report')
        if docx_report and docx_report['schedule_id'] == schedule['id']:
            st.download_button(
                label="📥 Download DOCX Report",
                data=docx_report['data'],
                file_name=docx_report['filename'],
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True
            )
    
    with col2:
        st.markdown("#### 📊 Detailed Analysis (Excel)")
        st.info("""
        **Contains:**
        - Summary sheet with all key metrics
        - Issues detail sheet
        - Complete activity list
        - Logic relationships breakdown
        - Detailed metrics analysis
        - Recommendations with impact/effort
    
        **Best for:** Detailed analysis, data manipulation
        """)
    
        if st.button("📥 Generate Excel Report", use_container_width=True, type="primary"):
            with st.spinner("Generating Excel report..."):
                try:
                    # Prepare analysis results with DCMA 14-point
                    full_analysis = {
                        'dcma_metrics': analysis['metrics'],
                        'performance_metrics': analysis.get('performance_metrics', {}),
                        'dcma_14_point': analysis.get('dcma_14_point', {}),
                        'issues': analysis['issues'],
                        'recommendations': analysis.get('recommendations', [])
                    }

                    # Generate Excel
                    excel_gen = ExcelGenerator(
                        project_name=project_name,
                        schedule_data=schedule['schedule_data'],
                        analysis_results=full_analysis
                    )
    
                    # Create filename
                    filename = f"Schedule_Analysis_{project_name}_v{schedule['version_number']}_{datetime.now().strftime('%Y%m%d')}.xlsx"

                    # Cached for the same reason as the DOCX payload above.
                    with timed("Reports: generate Excel", warn_after=5.0):
                        excel_bytes = excel_gen.generate()

                    st.session_state.excel_report = {
                        'data': excel_bytes,
                        'filename': filename,
                        'schedule_id': schedule['id'],
                    }

                    display_success_message("Excel report generated successfully!")
    
                    # Log action
                    db.log_action(user['id'], 'export', schedule['id'],
                                 {'report_type': 'excel', 'filename': filename})
    
                except Exception as e:
                    report_error("Failed to generate the Excel report.", e,
                                 logger_name="reports")

        excel_report = st.session_state.get('excel_report')
        if excel_report and excel_report['schedule_id'] == schedule['id']:
            st.download_button(
                label="📥 Download Excel Report",
                data=excel_report['data'],
                file_name=excel_report['filename'],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

    section_divider()
    
    # Batch export (if multiple schedules selected)
    st.markdown("### Batch Export (Multiple Schedules)")
    
    if len(schedules) > 1:
        st.info("💡 Select multiple schedules to export all reports at once")
    
        # Multi-select
        selected_schedules = st.multiselect(
            "Select schedules for batch export:",
            options=list(schedule_options.keys()),
            default=[]
        )
    
        if selected_schedules:
            col1, col2 = st.columns(2)
    
            with col1:
                if st.button("📥 Export All as DOCX", use_container_width=True):
                    st.info("Batch DOCX export coming soon!")
    
            with col2:
                if st.button("📥 Export All as Excel", use_container_width=True):
                    st.info("Batch Excel export coming soon!")
    else:
        st.info("Upload more schedules to enable batch export")
    
    st.markdown("---")
    
    # Report history
    st.markdown("### Export History")
    
    # Get audit log for exports
    audit_logs = db.get_audit_log(user_id=None, action_type='export')
    
    if audit_logs:
        st.markdown(f"**Recent exports ({len(audit_logs)} total)**")
    
        # Display recent exports
        for log in audit_logs[-10:]:  # Last 10 exports
            export_user = db.get_user_by_id(log['user_id'])
            username = export_user['username'] if export_user else 'Unknown'
    
            details = log.get('details', {})
            report_type = details.get('report_type', 'unknown')
            filename = details.get('filename', 'unknown')
    
            with st.expander(f"📄 {filename} - {log['timestamp'][:10]}"):
                st.write(f"**User:** {username}")
                st.write(f"**Type:** {report_type.upper()}")
                st.write(f"**Date:** {log['timestamp']}")
    else:
        st.info("No export history yet")
    
    st.markdown("---")
    
    # Help section
    with st.expander("❓ Report Help"):
        st.markdown("""
        ### Report Types
    
        **Executive Summary (DOCX)**
        - Professional Word document
        - Suitable for management and clients
        - Includes charts, tables, and formatted text
        - Easy to customize and edit
        - Recommended for presentations
    
        **Detailed Analysis (Excel)**
        - Comprehensive Excel workbook
        - Multiple sheets with different data views
        - Suitable for detailed analysis
        - Can be used for further calculations
        - Recommended for technical teams
    
        ### Best Practices
    
        1. **Generate reports after completing analysis**
           - Ensure all metrics are calculated
           - Review issues and recommendations first
    
        2. **Use descriptive project names**
           - Helps organize reports
           - Makes finding reports easier
    
        3. **Export both formats**
           - DOCX for presentations
           - Excel for detailed work
    
        4. **Regular reporting**
           - Generate reports after each schedule update
           - Track improvements over time
           - Maintain audit trail
    
        ### Customization
    
        To customize report templates:
        - Edit `src/reports/docx_generator.py` for DOCX format
        - Edit `src/reports/excel_generator.py` for Excel format
        - Modify sections, add company logos, change colors
    
        ### Troubleshooting
    
        **"Failed to generate report" error:**
        - Ensure analysis is complete
        - Check all required data is present
        - Try refreshing the page and re-selecting schedule
    
        **Download not starting:**
        - Check browser download settings
        - Disable popup blockers
        - Try different browser
        """)
    
except Exception as e:
    report_error(
        "The Reports page could not be displayed for this schedule.",
        e,
        logger_name="reports",
    )

    st.info("""
    **What to try:**
    1. **Re-analyse the schedule** - go to Upload Schedule and run the analysis again
    2. **Refresh the page** - Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac)
    3. **Contact support** - quote the error reference shown above
    """)
