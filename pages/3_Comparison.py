"""
Comparison Page
Compare multiple schedule versions side-by-side
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.database.db_manager import DatabaseManager
from src.auth.auth_manager import AuthManager
from src.utils.helpers import init_session_state, display_no_data_message

st.set_page_config(page_title="Comparison", page_icon="📊", layout="wide")

# Initialize
init_session_state()
db = DatabaseManager()
auth = AuthManager(db)

# Check authentication
auth.require_auth()

st.title("📊 Schedule Comparison")
st.markdown("Compare multiple schedule versions to track improvements")

# User info in sidebar
with st.sidebar:
    st.markdown("---")
    user = auth.get_current_user()
    if user:
        st.markdown(f"**User:** {user['username']}")
        st.markdown(f"**Role:** {user['role'].capitalize()}")
    st.markdown("---")

# Get schedules
schedules = st.session_state.schedules

if len(schedules) < 2:
    display_no_data_message("You need at least 2 schedules to compare. Please upload more schedules.")
    st.stop()

# Schedule selection
st.markdown("### Select Schedules to Compare")

col1, col2 = st.columns(2)

# Create schedule options
schedule_options = {}
for schedule in schedules:
    project = db.get_project_by_id(schedule['project_id'])
    project_name = project['project_name'] if project else "Unknown"
    label = f"{project_name} - v{schedule['version_number']} ({schedule['upload_date'][:10]})"
    schedule_options[label] = schedule['id']

with col1:
    st.markdown("#### Schedule 1 (Baseline)")
    schedule1_label = st.selectbox(
        "Select first schedule:",
        options=list(schedule_options.keys()),
        key="schedule1"
    )
    schedule1_id = schedule_options[schedule1_label]

with col2:
    st.markdown("#### Schedule 2 (Current)")
    schedule2_label = st.selectbox(
        "Select second schedule:",
        options=list(schedule_options.keys()),
        key="schedule2"
    )
    schedule2_id = schedule_options[schedule2_label]

if schedule1_id == schedule2_id:
    st.warning("⚠️ Please select two different schedules to compare")
    st.stop()

# Get schedule and analysis data
schedule1 = db.get_schedule_by_id(schedule1_id)
schedule2 = db.get_schedule_by_id(schedule2_id)

analysis1 = db.get_analysis_by_schedule(schedule1_id)
analysis2 = db.get_analysis_by_schedule(schedule2_id)

if not analysis1 or not analysis2:
    display_no_data_message("Analysis results not available for one or both schedules")
    st.stop()

st.markdown("---")

# Health Score Comparison
st.markdown("## Health Score Comparison")

col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    score1 = analysis1['health_score']
    st.metric(
        "Schedule 1",
        f"{score1:.1f}/100",
        help=schedule1_label
    )

with col2:
    score2 = analysis2['health_score']
    delta = score2 - score1
    st.metric(
        "Schedule 2",
        f"{score2:.1f}/100",
        delta=f"{delta:+.1f}",
        delta_color="normal",
        help=schedule2_label
    )

with col3:
    improvement_pct = ((score2 - score1) / score1 * 100) if score1 > 0 else 0
    st.metric(
        "Improvement",
        f"{improvement_pct:+.1f}%",
        delta="Better" if improvement_pct > 0 else "Worse" if improvement_pct < 0 else "Same"
    )

# Visual comparison
fig = go.Figure(data=[
    go.Bar(
        name='Schedule 1',
        x=['Health Score'],
        y=[score1],
        marker_color='lightblue'
    ),
    go.Bar(
        name='Schedule 2',
        x=['Health Score'],
        y=[score2],
        marker_color='darkblue'
    )
])

fig.update_layout(
    title="Health Score Comparison",
    yaxis_title="Score (0-100)",
    barmode='group'
)

st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# Key Metrics Comparison
st.markdown("## Key Metrics Comparison")

# Prepare comparison data
metrics1 = analysis1['metrics']
metrics2 = analysis2['metrics']

comparison_data = []

# Negative Lags
comparison_data.append({
    'Metric': 'Negative Lags',
    'Schedule 1': metrics1.get('negative_lags', {}).get('count', 0),
    'Schedule 2': metrics2.get('negative_lags', {}).get('count', 0),
    'Target': 0,
    'Change': metrics2.get('negative_lags', {}).get('count', 0) - metrics1.get('negative_lags', {}).get('count', 0)
})

# Positive Lags %
comparison_data.append({
    'Metric': 'Positive Lags %',
    'Schedule 1': metrics1.get('positive_lags', {}).get('percentage', 0),
    'Schedule 2': metrics2.get('positive_lags', {}).get('percentage', 0),
    'Target': '≤5%',
    'Change': metrics2.get('positive_lags', {}).get('percentage', 0) - metrics1.get('positive_lags', {}).get('percentage', 0)
})

# Hard Constraints %
comparison_data.append({
    'Metric': 'Hard Constraints %',
    'Schedule 1': metrics1.get('hard_constraints', {}).get('percentage', 0),
    'Schedule 2': metrics2.get('hard_constraints', {}).get('percentage', 0),
    'Target': '≤10%',
    'Change': metrics2.get('hard_constraints', {}).get('percentage', 0) - metrics1.get('hard_constraints', {}).get('percentage', 0)
})

# Missing Logic
comparison_data.append({
    'Metric': 'Missing Logic',
    'Schedule 1': metrics1.get('missing_logic', {}).get('count', 0),
    'Schedule 2': metrics2.get('missing_logic', {}).get('count', 0),
    'Target': 0,
    'Change': metrics2.get('missing_logic', {}).get('count', 0) - metrics1.get('missing_logic', {}).get('count', 0)
})

# Average Duration
comparison_data.append({
    'Metric': 'Average Duration (days)',
    'Schedule 1': round(metrics1.get('average_duration', {}).get('mean', 0), 1),
    'Schedule 2': round(metrics2.get('average_duration', {}).get('mean', 0), 1),
    'Target': '10-20',
    'Change': round(metrics2.get('average_duration', {}).get('mean', 0) - metrics1.get('average_duration', {}).get('mean', 0), 1)
})

# Total Activities
comparison_data.append({
    'Metric': 'Total Activities',
    'Schedule 1': schedule1['schedule_data']['total_activities'],
    'Schedule 2': schedule2['schedule_data']['total_activities'],
    'Target': '-',
    'Change': schedule2['schedule_data']['total_activities'] - schedule1['schedule_data']['total_activities']
})

# Create comparison table
df_comparison = pd.DataFrame(comparison_data)

# Style the dataframe
def highlight_change(val):
    """Highlight improvements in green, regressions in red"""
    try:
        if val < 0:
            return 'background-color: lightgreen'
        elif val > 0:
            return 'background-color: lightcoral'
        else:
            return ''
    except:
        return ''

styled_df = df_comparison.style.applymap(
    highlight_change,
    subset=['Change']
).format({
    'Schedule 1': '{:.1f}',
    'Schedule 2': '{:.1f}',
    'Change': '{:+.1f}'
})

st.dataframe(styled_df, use_container_width=True)

st.markdown("---")

# Issues Comparison
st.markdown("## Issues Comparison")

col1, col2, col3 = st.columns(3)

issues1 = analysis1['issues']
issues2 = analysis2['issues']

with col1:
    st.metric("Schedule 1 Issues", len(issues1))

with col2:
    issues_delta = len(issues2) - len(issues1)
    st.metric("Schedule 2 Issues", len(issues2), delta=f"{issues_delta:+d}")

with col3:
    high1 = len([i for i in issues1 if i['severity'] == 'high'])
    high2 = len([i for i in issues2 if i['severity'] == 'high'])
    high_delta = high2 - high1
    st.metric("High Priority Issues", high2, delta=f"{high_delta:+d}")

# Issues by severity chart
severity_data = {
    'Schedule 1': {
        'High': len([i for i in issues1 if i['severity'] == 'high']),
        'Medium': len([i for i in issues1 if i['severity'] == 'medium']),
        'Low': len([i for i in issues1 if i['severity'] == 'low'])
    },
    'Schedule 2': {
        'High': len([i for i in issues2 if i['severity'] == 'high']),
        'Medium': len([i for i in issues2 if i['severity'] == 'medium']),
        'Low': len([i for i in issues2 if i['severity'] == 'low'])
    }
}

fig = go.Figure(data=[
    go.Bar(
        name='Schedule 1',
        x=['High', 'Medium', 'Low'],
        y=[severity_data['Schedule 1']['High'],
           severity_data['Schedule 1']['Medium'],
           severity_data['Schedule 1']['Low']],
        marker_color='lightblue'
    ),
    go.Bar(
        name='Schedule 2',
        x=['High', 'Medium', 'Low'],
        y=[severity_data['Schedule 2']['High'],
           severity_data['Schedule 2']['Medium'],
           severity_data['Schedule 2']['Low']],
        marker_color='darkblue'
    )
])

fig.update_layout(
    title="Issues by Severity",
    yaxis_title="Count",
    barmode='group'
)

st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# Performance Metrics Comparison (if available)
if 'performance_metrics' in analysis1 and 'performance_metrics' in analysis2:
    st.markdown("## Performance Metrics Comparison")

    perf1 = analysis1['performance_metrics']
    perf2 = analysis2['performance_metrics']

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        cpli1 = perf1.get('cpli', {}).get('value', 0)
        cpli2 = perf2.get('cpli', {}).get('value', 0)
        cpli_delta = cpli2 - cpli1
        st.metric(
            "CPLI (Schedule 2)",
            f"{cpli2:.3f}",
            delta=f"{cpli_delta:+.3f}",
            help="Critical Path Length Index"
        )

    with col2:
        bei1 = perf1.get('bei', {}).get('value', 0)
        bei2 = perf2.get('bei', {}).get('value', 0)
        bei_delta = bei2 - bei1
        st.metric(
            "BEI (Schedule 2)",
            f"{bei2:.3f}",
            delta=f"{bei_delta:+.3f}",
            help="Baseline Execution Index"
        )

    with col3:
        recs1 = len(analysis1.get('recommendations', []))
        recs2 = len(analysis2.get('recommendations', []))
        recs_delta = recs2 - recs1
        st.metric(
            "Recommendations",
            recs2,
            delta=f"{recs_delta:+d}"
        )

    with col4:
        if improvement_pct >= 10:
            st.success("✅ Significant Improvement")
        elif improvement_pct > 0:
            st.info("📈 Minor Improvement")
        elif improvement_pct < 0:
            st.warning("📉 Regression")
        else:
            st.info("➡️ No Change")

st.markdown("---")

# Summary
st.markdown("## Summary")

if improvement_pct > 0:
    st.success(f"""
    🎉 **Schedule 2 shows improvement over Schedule 1!**

    - Health Score improved by {improvement_pct:.1f}%
    - Issues changed from {len(issues1)} to {len(issues2)} ({issues_delta:+d})
    - High priority issues changed from {high1} to {high2} ({high_delta:+d})

    Continue monitoring these metrics and addressing remaining issues.
    """)
elif improvement_pct < 0:
    st.warning(f"""
    ⚠️ **Schedule 2 shows regression from Schedule 1**

    - Health Score decreased by {abs(improvement_pct):.1f}%
    - Review the Analysis Dashboard to identify new issues
    - Focus on high-priority recommendations

    Consider reverting changes that led to degraded quality.
    """)
else:
    st.info("""
    ➡️ **No significant change between schedules**

    - Health scores are similar
    - Review individual metrics for subtle changes
    - Continue improving schedule quality
    """)
