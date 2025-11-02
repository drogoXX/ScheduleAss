"""
Analysis Dashboard Page
Displays comprehensive schedule quality analysis
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from src.database.db_manager import DatabaseManager
from src.auth.auth_manager import AuthManager
from src.utils.helpers import (
    init_session_state, display_health_score, display_issue_card,
    display_recommendation_card, display_no_data_message
)

st.set_page_config(page_title="Analysis Dashboard", page_icon="📊", layout="wide")

# Initialize
init_session_state()
db = DatabaseManager()
auth = AuthManager(db)

# Check authentication
auth.require_auth()

st.title("📊 Analysis Dashboard")

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
    "Choose a schedule to analyze",
    options=list(schedule_options.keys())
)

selected_schedule_id = schedule_options[selected_schedule_label]
schedule = db.get_schedule_by_id(selected_schedule_id)
analysis = db.get_analysis_by_schedule(selected_schedule_id)

if not analysis:
    display_no_data_message("No analysis results available for this schedule.")
    st.stop()

# Store in session state
st.session_state.current_schedule = schedule
st.session_state.current_analysis = analysis

st.markdown("---")

# Create tabs for different views
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 Overview",
    "🔍 Detailed Metrics",
    "⚠️ Issues",
    "💡 Recommendations",
    "📋 Activities"
])

# Tab 1: Overview
with tab1:
    st.markdown("## Schedule Overview")

    # Health Score
    col1, col2 = st.columns([1, 2])

    with col1:
        health_score = analysis['health_score']
        # Get full metrics
        perf_metrics = analysis.get('performance_metrics', {})
        if perf_metrics:
            health_data = perf_metrics.get('health_score', {})
            rating = health_data.get('rating', 'Unknown')
        else:
            rating = 'Unknown'

        display_health_score(health_score, rating)

    with col2:
        # Key metrics
        metrics = analysis['metrics']

        col2_1, col2_2 = st.columns(2)

        with col2_1:
            # CPLI
            if 'performance_metrics' in analysis:
                cpli = analysis['performance_metrics'].get('cpli', {})
                cpli_value = cpli.get('value', 0)
                cpli_status = cpli.get('status', 'unknown')
                st.metric(
                    "CPLI",
                    f"{cpli_value:.3f}",
                    delta="Target: ≥0.95",
                    help="Critical Path Length Index"
                )

                # BEI
                bei = analysis['performance_metrics'].get('bei', {})
                bei_value = bei.get('value', 0)
                st.metric(
                    "BEI",
                    f"{bei_value:.3f}",
                    delta="Target: ≥0.95",
                    help="Baseline Execution Index"
                )

        with col2_2:
            # Total activities
            total_activities = schedule['schedule_data']['total_activities']
            st.metric("Total Activities", total_activities)

            # Issues count
            issues_count = len(analysis['issues'])
            st.metric("Issues Identified", issues_count)

    st.markdown("---")

    # Quick stats
    st.markdown("### Key Statistics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        neg_lags = metrics.get('negative_lags', {}).get('count', 0)
        st.metric("Negative Lags", neg_lags, help="Target: 0")

    with col2:
        pos_lags_pct = metrics.get('positive_lags', {}).get('percentage', 0)
        st.metric("Positive Lags %", f"{pos_lags_pct:.1f}%", help="Target: ≤5%")

    with col3:
        constraints_pct = metrics.get('hard_constraints', {}).get('percentage', 0)
        st.metric("Hard Constraints %", f"{constraints_pct:.1f}%", help="Target: ≤10%")

    with col4:
        missing_logic = metrics.get('missing_logic', {}).get('count', 0)
        st.metric("Missing Logic", missing_logic, help="Target: 0")

    st.markdown("---")

    # Activity status distribution
    st.markdown("### Activity Status Distribution")

    status_data = metrics.get('activity_status', {}).get('distribution', {})
    if status_data:
        fig = px.pie(
            values=list(status_data.values()),
            names=list(status_data.keys()),
            title="Activity Status Breakdown",
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No status data available")

# Tab 2: Detailed Metrics
with tab2:
    st.markdown("## Detailed Metrics Analysis")

    # Logic Quality
    st.markdown("### Logic Quality Metrics")

    col1, col2 = st.columns(2)

    with col1:
        # Negative lags chart
        neg_lags_count = metrics.get('negative_lags', {}).get('count', 0)
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=neg_lags_count,
            title={'text': "Negative Lags"},
            gauge={
                'axis': {'range': [0, 50]},
                'bar': {'color': "red" if neg_lags_count > 0 else "green"},
                'steps': [
                    {'range': [0, 0], 'color': "lightgreen"},
                    {'range': [0, 50], 'color': "lightcoral"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 0
                }
            }
        ))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Positive lags chart
        pos_lags_pct = metrics.get('positive_lags', {}).get('percentage', 0)
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=pos_lags_pct,
            title={'text': "Positive Lags (%)"},
            delta={'reference': 5},
            gauge={
                'axis': {'range': [0, 20]},
                'bar': {'color': "green" if pos_lags_pct <= 5 else "orange"},
                'steps': [
                    {'range': [0, 5], 'color': "lightgreen"},
                    {'range': [5, 20], 'color': "lightyellow"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 5
                }
            }
        ))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Duration Analysis
    st.markdown("### Duration Analysis")

    col1, col2 = st.columns(2)

    with col1:
        avg_duration = metrics.get('average_duration', {}).get('mean', 0)
        median_duration = metrics.get('average_duration', {}).get('median', 0)

        st.metric("Average Duration", f"{avg_duration:.1f} days")
        st.metric("Median Duration", f"{median_duration:.1f} days")

        long_durations = metrics.get('long_durations', {})
        st.metric("Activities >20 days", long_durations.get('count_over_20_days', 0))
        st.metric("Activities >5 months", long_durations.get('count_over_5_months', 0))

    with col2:
        # Duration distribution (if data available)
        activities = schedule['schedule_data'].get('activities', [])
        if activities:
            df = pd.DataFrame(activities)
            if 'At Completion Duration' in df.columns:
                durations = df['At Completion Duration'].dropna()
                fig = px.histogram(
                    durations,
                    nbins=30,
                    title="Activity Duration Distribution",
                    labels={'value': 'Duration (days)', 'count': 'Frequency'}
                )
                fig.add_vline(x=20, line_dash="dash", line_color="orange",
                             annotation_text="20 days")
                fig.add_vline(x=150, line_dash="dash", line_color="red",
                             annotation_text="5 months")
                st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Relationship Types
    st.markdown("### Relationship Types Distribution")

    rel_types = metrics.get('relationship_types', {})
    if rel_types.get('total', 0) > 0:
        percentages = rel_types.get('percentages', {})
        fig = px.bar(
            x=list(percentages.keys()),
            y=list(percentages.values()),
            title="Relationship Type Breakdown",
            labels={'x': 'Relationship Type', 'y': 'Percentage (%)'},
            color=list(percentages.keys()),
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No relationship data available")

# Tab 3: Issues
with tab3:
    st.markdown("## Identified Issues")

    issues = analysis['issues']

    if not issues:
        st.success("🎉 No issues identified! Your schedule is in excellent shape.")
    else:
        # Filter by severity
        severity_filter = st.multiselect(
            "Filter by severity:",
            options=['high', 'medium', 'low'],
            default=['high', 'medium', 'low']
        )

        filtered_issues = [i for i in issues if i['severity'] in severity_filter]

        st.markdown(f"**Showing {len(filtered_issues)} of {len(issues)} issues**")

        # Group by severity
        high = [i for i in filtered_issues if i['severity'] == 'high']
        medium = [i for i in filtered_issues if i['severity'] == 'medium']
        low = [i for i in filtered_issues if i['severity'] == 'low']

        # Display high priority issues
        if high:
            st.markdown("### 🔴 High Priority Issues")
            for issue in high:
                display_issue_card(issue)

        # Display medium priority issues
        if medium:
            st.markdown("### 🟡 Medium Priority Issues")
            for issue in medium:
                display_issue_card(issue)

        # Display low priority issues
        if low:
            st.markdown("### 🟢 Low Priority Issues")
            for issue in low:
                display_issue_card(issue)

# Tab 4: Recommendations
with tab4:
    st.markdown("## Recommendations")

    recommendations = analysis.get('recommendations', [])

    if not recommendations:
        st.success("🎉 No recommendations at this time. Your schedule is well-optimized!")
    else:
        # Summary
        rec_summary = {
            'high': len([r for r in recommendations if r['priority'] == 'high']),
            'medium': len([r for r in recommendations if r['priority'] == 'medium']),
            'low': len([r for r in recommendations if r['priority'] == 'low'])
        }

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("High Priority", rec_summary['high'])
        with col2:
            st.metric("Medium Priority", rec_summary['medium'])
        with col3:
            st.metric("Low Priority", rec_summary['low'])

        st.markdown("---")

        # Filter
        priority_filter = st.multiselect(
            "Filter by priority:",
            options=['high', 'medium', 'low'],
            default=['high', 'medium', 'low']
        )

        filtered_recs = [r for r in recommendations if r['priority'] in priority_filter]

        st.markdown(f"**Showing {len(filtered_recs)} of {len(recommendations)} recommendations**")

        # Display recommendations
        for i, rec in enumerate(filtered_recs, 1):
            display_recommendation_card(rec, i)

# Tab 5: Activities
with tab5:
    st.markdown("## Activity Details")

    activities = schedule['schedule_data'].get('activities', [])

    if not activities:
        display_no_data_message("No activity data available")
    else:
        df = pd.DataFrame(activities)

        # Select key columns for display
        display_columns = ['Activity ID', 'Activity Name', 'Activity Status']

        # Add optional columns if they exist
        optional_cols = ['Start', 'Finish', 'Total Float', 'At Completion Duration',
                        'WBS Code', 'Primary Constraint']
        for col in optional_cols:
            if col in df.columns:
                display_columns.append(col)

        # Filters
        col1, col2 = st.columns(2)

        with col1:
            # Status filter
            if 'Activity Status' in df.columns:
                status_options = ['All'] + list(df['Activity Status'].unique())
                selected_status = st.selectbox("Filter by Status:", status_options)
            else:
                selected_status = 'All'

        with col2:
            # Search
            search_term = st.text_input("Search (Activity ID or Name):", "")

        # Apply filters
        filtered_df = df.copy()

        if selected_status != 'All':
            filtered_df = filtered_df[filtered_df['Activity Status'] == selected_status]

        if search_term:
            mask = (
                filtered_df['Activity ID'].str.contains(search_term, case=False, na=False) |
                filtered_df['Activity Name'].str.contains(search_term, case=False, na=False)
            )
            filtered_df = filtered_df[mask]

        # Display count
        st.markdown(f"**Showing {len(filtered_df)} of {len(df)} activities**")

        # Display dataframe
        st.dataframe(
            filtered_df[display_columns],
            use_container_width=True,
            height=400
        )

        # Download option
        csv = filtered_df[display_columns].to_csv(index=False)
        st.download_button(
            label="📥 Download Filtered Activities (CSV)",
            data=csv,
            file_name=f"activities_{schedule['file_name']}.csv",
            mime="text/csv",
            use_container_width=True
        )
