"""
Reports Page
Generate and download professional reports (DOCX and Excel)
"""

import streamlit as st
from datetime import datetime
from src.database.db_manager import DatabaseManager
from src.auth.auth_manager import AuthManager
from src.reports.docx_generator import DOCXGenerator
from src.reports.excel_generator import ExcelGenerator
from src.utils.helpers import (
    init_session_state, display_no_data_message,
    display_success_message, display_error_message
)

st.set_page_config(page_title="Reports", page_icon="📄", layout="wide")

# Initialize
init_session_state()
db = DatabaseManager()
auth = AuthManager(db)

# Check authentication
auth.require_auth()

st.title("📄 Reports")
st.markdown("Generate and download professional schedule analysis reports")

# User info in sidebar
with st.sidebar:
    st.markdown("---")
    user = auth.get_current_user()
    if user:
        st.markdown(f"**User:** {user['username']}")
        st.markdown(f"**Role:** {user['role'].capitalize()}")
    st.markdown("---")

# Schedule selection
st.markdown("### Select Schedule")

schedules = st.session_state.schedules
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
    schedule = db.get_schedule_by_id(selected_schedule_id)
    analysis = db.get_analysis_by_schedule(selected_schedule_id)

    # Debug logging
    if analysis:
        st.sidebar.success(f"✅ Analysis loaded: {len(str(analysis))} chars")
    else:
        st.sidebar.warning("⚠️ No analysis found")

except Exception as e:
    st.error(f"❌ CRITICAL ERROR loading data:")
    st.code(str(e))
    import traceback
    st.code(traceback.format_exc())
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
        st.write(f"**Activities:** {schedule['schedule_data']['total_activities']}")
    
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
    
            st.write(f"**Health Score:** {health_score:.1f}/100")
            st.write(f"**Rating:** {rating}")
            st.write(f"**Issues Found:** {len(analysis.get('issues', []))}")
            st.write(f"**Recommendations:** {len(analysis.get('recommendations', []))}")
        except Exception as e:
            st.error(f"Error loading analysis summary: {str(e)}")
            st.info("This may occur if the analysis was created with an older version of the application. Please re-analyze the schedule.")
    
    st.markdown("---")
    
    # Report generation
    st.markdown("### Generate Reports")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📝 Executive Summary (DOCX)")
        st.info("""
        **Contains:**
        - Cover page with health score
        - Executive summary
        - DCMA 14-Point compliance checklist
        - Key performance metrics (CPLI, BEI)
        - Issues summary table
        - Prioritized recommendations
        - Methodology appendix
    
        **Best for:** Stakeholder presentations, client reports
        """)
    
        if st.button("📥 Generate DOCX Report", use_container_width=True, type="primary"):
            with st.spinner("Generating DOCX report..."):
                try:
                    # Prepare analysis results with performance metrics
                    full_analysis = {
                        'dcma_metrics': analysis['metrics'],
                        'performance_metrics': analysis.get('performance_metrics', {}),
                        'issues': analysis['issues'],
                        'recommendations': analysis.get('recommendations', [])
                    }
    
                    # Generate DOCX
                    docx_gen = DOCXGenerator(
                        project_name=project_name,
                        schedule_data=schedule['schedule_data'],
                        analysis_results=full_analysis
                    )
    
                    docx_bytes = docx_gen.generate()
    
                    # Create filename
                    filename = f"Schedule_Analysis_{project_name}_v{schedule['version_number']}_{datetime.now().strftime('%Y%m%d')}.docx"
    
                    # Download button
                    st.download_button(
                        label="📥 Download DOCX Report",
                        data=docx_bytes,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True
                    )
    
                    display_success_message("DOCX report generated successfully!")
    
                    # Log action
                    db._log_action(user['id'], 'export', schedule['id'],
                                 {'report_type': 'docx', 'filename': filename})
    
                except Exception as e:
                    display_error_message(f"Failed to generate DOCX report: {str(e)}")
                    st.exception(e)
    
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
                    # Prepare analysis results
                    full_analysis = {
                        'dcma_metrics': analysis['metrics'],
                        'performance_metrics': analysis.get('performance_metrics', {}),
                        'issues': analysis['issues'],
                        'recommendations': analysis.get('recommendations', [])
                    }
    
                    # Generate Excel
                    excel_gen = ExcelGenerator(
                        project_name=project_name,
                        schedule_data=schedule['schedule_data'],
                        analysis_results=full_analysis
                    )
    
                    excel_bytes = excel_gen.generate()
    
                    # Create filename
                    filename = f"Schedule_Analysis_{project_name}_v{schedule['version_number']}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    
                    # Download button
                    st.download_button(
                        label="📥 Download Excel Report",
                        data=excel_bytes,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
    
                    display_success_message("Excel report generated successfully!")
    
                    # Log action
                    db._log_action(user['id'], 'export', schedule['id'],
                                 {'report_type': 'excel', 'filename': filename})
    
                except Exception as e:
                    display_error_message(f"Failed to generate Excel report: {str(e)}")
                    st.exception(e)
    
    st.markdown("---")
    
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
    st.error("## ❌ CRITICAL ERROR - Page Rendering Failed")
    st.error(f"**Error Type:** {type(e).__name__}")
    st.error(f"**Error Message:** {str(e)}")

    st.markdown("### 🔍 Debug Information")
    st.write("**Analysis Data Check:**")
    st.write(f"- Analysis exists: {analysis is not None}")
    if analysis:
        st.write(f"- Analysis keys: {list(analysis.keys())}")
        st.write(f"- Metrics keys: {list(analysis.get('metrics', {}).keys())}")
        if 'comprehensive_float' in analysis.get('metrics', {}):
            cf = analysis['metrics']['comprehensive_float']
            st.write(f"- comprehensive_float keys: {list(cf.keys())}")

            # Check for problematic data types
            import numpy as np
            def check_types(obj, path=''):
                issues = []
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        issues.extend(check_types(v, f'{path}.{k}'))
                elif isinstance(obj, list) and len(obj) > 0:
                    issues.extend(check_types(obj[0], f'{path}[0]'))
                elif isinstance(obj, (np.integer, np.floating)):
                    issues.append(f'{path}: {type(obj).__name__}')
                return issues

            type_issues = check_types(cf, 'comprehensive_float')
            if type_issues:
                st.warning(f"⚠️ Found {len(type_issues)} numpy types (may cause serialization issues)")
                for issue in type_issues[:10]:
                    st.code(issue)

    st.markdown("### 📋 Full Traceback")
    import traceback
    st.code(traceback.format_exc())

    st.markdown("### 💡 Possible Solutions")
    st.info("""
    1. **Re-analyze the schedule** - Go to Upload Schedule and click "Analyze Schedule" again
    2. **Clear browser cache** - Refresh with Ctrl+Shift+R or Cmd+Shift+R
    3. **Try a different browser** - Sometimes browser state causes issues
    4. **Contact support** - Share the error details above
    """)
