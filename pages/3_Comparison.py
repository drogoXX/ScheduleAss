"""
Comparison Page
Compare multiple schedule versions side-by-side
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.services import get_auth, get_database, load_analysis, load_schedule
from src.ui.diagnostics import timed
from src.ui.theme import (
    CHART_SEQUENCE, COLORS, app_header, apply_chart_theme, fmt_count,
    fmt_delta_count, fmt_delta_index, fmt_delta_pct, fmt_delta_score, fmt_index,
    fmt_pct, fmt_score, inject_css,
)
from src.utils.helpers import init_session_state, display_no_data_message

st.set_page_config(page_title="Comparison", page_icon="📊", layout="wide")
inject_css("Comparison")

# Initialize
init_session_state()
db = get_database()
auth = get_auth(db)

# Check authentication
auth.require_auth()

app_header(
    "📊 Schedule Comparison",
    "Compare two schedule versions side-by-side to track improvements",
)

# User info in sidebar
with st.sidebar:
    st.divider()
    user = auth.get_current_user()
    if user:
        st.markdown(f"**User:** {user['username']}")
        st.markdown(f"**Role:** {user['role'].capitalize()}")
    st.divider()

# Get schedules
schedules = db.get_all_schedules()

if len(schedules) < 2:
    # Comparison needs two versions by definition. Say so in a way that reads as
    # an intended state with a next step, not as a page that failed to load.
    st.info(
        f"**Comparison needs two schedules.** "
        f"You currently have {len(schedules)}."
    )
    st.markdown(
        "This page compares two versions of a schedule side by side — health score, "
        "DCMA results and metric-by-metric movement — so you can see what changed "
        "between revisions."
    )
    if schedules:
        st.markdown("**Already uploaded:**")
        for item in schedules:
            st.markdown(f"- {item['file_name']} (v{item['version_number']})")
        st.markdown(
            "Upload a later revision of the same schedule on the **Upload Schedule** "
            "page, then return here."
        )
    else:
        st.markdown("Upload a schedule on the **Upload Schedule** page to begin.")
    st.caption("📤 Use **Upload Schedule** in the sidebar to add another version.")
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

# Get schedule and analysis data. Timed: this page loads two full schedules,
# twice the largest read on any other page, and is the prime suspect if the
# page appears to hang.
with timed("Comparison: load schedule 1"):
    schedule1 = load_schedule(schedule1_id)
with timed("Comparison: load schedule 2"):
    schedule2 = load_schedule(schedule2_id)

with timed("Comparison: load analyses"):
    analysis1 = load_analysis(schedule1_id)
    analysis2 = load_analysis(schedule2_id)

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
        "Schedule 1 (Baseline)",
        fmt_score(score1),
        help=schedule1_label
    )

with col2:
    score2 = analysis2['health_score']
    delta = score2 - score1
    st.metric(
        "Schedule 2 (Current)",
        fmt_score(score2),
        delta=fmt_delta_score(delta),
        delta_color="normal",
        help=schedule2_label
    )

with col3:
    improvement_pct = ((score2 - score1) / score1 * 100) if score1 > 0 else 0
    # "Better"/"Worse" as a delta would colour by its own sign; the change is
    # already carried by the value, so it goes in the caption instead.
    st.metric(
        "Change vs Baseline",
        fmt_delta_pct(improvement_pct),
    )
    st.caption(
        "Better" if improvement_pct > 0
        else "Worse" if improvement_pct < 0 else "Unchanged"
    )

# Visual comparison
fig = go.Figure(data=[
    go.Bar(
        name='Schedule 1',
        x=['Health Score'],
        y=[score1],
        marker_color=CHART_SEQUENCE[0]
    ),
    go.Bar(
        name='Schedule 2',
        x=['Health Score'],
        y=[score2],
        marker_color=CHART_SEQUENCE[1]
    )
])

st.plotly_chart(
    apply_chart_theme(
        fig, title="Health Score Comparison",
        yaxis_title="Score (0-100)", yaxis_format="score",
        barmode='group', yaxis_range=[0, 100],
    ),
    use_container_width=True,
)

st.divider()

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
        numeric = float(val)
    except (TypeError, ValueError):
        # Non-numeric cells (e.g. 'N/A') are simply left unstyled.
        return ''

    # Every metric in this table is one where lower is better, so a negative
    # change is an improvement.
    if numeric < 0:
        return f'background-color: {COLORS["success"]}; color: {COLORS["white"]}'
    if numeric > 0:
        return f'background-color: {COLORS["danger"]}; color: {COLORS["white"]}'
    return ''

styled_df = df_comparison.style.map(
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

# delta_color="inverse": more issues is worse, so a positive delta must read
# red. The Streamlit default would colour any increase green.
with col1:
    st.metric("Schedule 1 Issues", fmt_count(len(issues1)))

with col2:
    issues_delta = len(issues2) - len(issues1)
    st.metric("Schedule 2 Issues", fmt_count(len(issues2)),
              delta=fmt_delta_count(issues_delta), delta_color="inverse")

with col3:
    high1 = len([i for i in issues1 if i['severity'] == 'high'])
    high2 = len([i for i in issues2 if i['severity'] == 'high'])
    high_delta = high2 - high1
    st.metric("High Priority Issues", fmt_count(high2),
              delta=fmt_delta_count(high_delta), delta_color="inverse")

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
        marker_color=CHART_SEQUENCE[0]
    ),
    go.Bar(
        name='Schedule 2',
        x=['High', 'Medium', 'Low'],
        y=[severity_data['Schedule 2']['High'],
           severity_data['Schedule 2']['Medium'],
           severity_data['Schedule 2']['Low']],
        marker_color=CHART_SEQUENCE[1]
    )
])

st.plotly_chart(
    apply_chart_theme(
        fig, title="Issues by Severity",
        xaxis_title="Severity", yaxis_title="Issues",
        yaxis_format="count", barmode='group',
    ),
    use_container_width=True,
)

st.divider()

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
        # CPLI/BEI: higher is better, so the default delta colouring is right.
        st.metric(
            "CPLI (Schedule 2)",
            fmt_index(cpli2),
            delta=fmt_delta_index(cpli_delta),
            help="Critical Path Length Index. Target: ≥ 0.95"
        )

    with col2:
        bei1 = perf1.get('bei', {}).get('value', 0)
        bei2 = perf2.get('bei', {}).get('value', 0)
        bei_delta = bei2 - bei1
        st.metric(
            "BEI (Schedule 2)",
            fmt_index(bei2),
            delta=fmt_delta_index(bei_delta),
            help="Baseline Execution Index. Target: ≥ 0.95"
        )

    with col3:
        recs1 = len(analysis1.get('recommendations', []))
        recs2 = len(analysis2.get('recommendations', []))
        recs_delta = recs2 - recs1
        # More outstanding recommendations is worse.
        st.metric(
            "Recommendations",
            fmt_count(recs2),
            delta=fmt_delta_count(recs_delta),
            delta_color="inverse"
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

    - Health Score improved by {fmt_pct(improvement_pct)}
    - Issues changed from {len(issues1)} to {len(issues2)} ({fmt_delta_count(issues_delta)})
    - High priority issues changed from {high1} to {high2} ({fmt_delta_count(high_delta)})

    Continue monitoring these metrics and addressing remaining issues.
    """)
elif improvement_pct < 0:
    st.warning(f"""
    ⚠️ **Schedule 2 shows regression from Schedule 1**

    - Health Score decreased by {fmt_pct(abs(improvement_pct))}
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
