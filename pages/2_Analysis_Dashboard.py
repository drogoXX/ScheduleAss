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
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📈 Overview",
    "🔍 Detailed Metrics",
    "⏱️ Float Analysis",
    "🏗️ WBS Analysis",
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
        # Show total constrained activities
        constraints_data = metrics.get('constraints', {})
        total_constrained_pct = constraints_data.get('total_percentage', 0)
        st.metric("Activities with Constraints", f"{total_constrained_pct:.1f}%",
                 help="All constraint types (should be minimized and justified)")

    with col4:
        missing_logic = metrics.get('missing_logic', {}).get('count', 0)
        st.metric("Missing Logic", missing_logic, help="Target: 0")

    st.markdown("---")

    # Data Quality Warnings
    schedule_warnings = schedule['schedule_data'].get('warnings', [])
    if schedule_warnings:
        st.markdown("### ⚠️ Data Quality Warnings")
        st.warning(f"Found {len(schedule_warnings)} warning(s) during schedule parsing:")
        for warning in schedule_warnings:
            st.markdown(f"- {warning}")
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
        avg_duration_data = metrics.get('average_duration', {})
        avg_duration = avg_duration_data.get('mean', 0)
        median_duration = avg_duration_data.get('median', 0)
        total_analyzed = avg_duration_data.get('total_activities_analyzed', 0)
        milestones_excluded = avg_duration_data.get('milestones_excluded', 0)
        source_column = avg_duration_data.get('source_column', 'Unknown')

        st.metric("Average Duration", f"{avg_duration:.1f} days",
                 help=f"Based on 'At Completion Duration' from P6")
        st.metric("Median Duration", f"{median_duration:.1f} days")

        # Show analysis details
        if total_analyzed > 0:
            st.info(f"ℹ️ Analyzed {total_analyzed} activities (excluded {milestones_excluded} milestones)")

        # Show error if column not found
        if 'error' in avg_duration_data:
            st.error(f"⚠️ {avg_duration_data['error']}")

        long_durations = metrics.get('long_durations', {})
        st.metric("Activities >20 days", long_durations.get('count_over_20_days', 0),
                 help="Excluding milestones")
        st.metric("Activities >5 months", long_durations.get('count_over_5_months', 0),
                 help="Excluding milestones")

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
        st.warning("⚠️ No relationship data available")
        st.markdown("""
        **Possible causes:**
        - CSV file is missing 'Predecessor Details' or 'Predecessors' column
        - All activities have empty predecessor fields
        - Check upload warnings for more information

        **How to fix:**
        - Re-export your schedule from P6 with relationship columns included
        - Ensure 'Predecessor Details' column contains relationship information in format: `ActivityID: Type Lag`
        - Example: `A100: FF 10, A200: FS, A300: SS -5`
        """)

    st.markdown("---")

    # Constraints Analysis
    st.markdown("### Constraints Analysis")

    constraints_data = metrics.get('constraints', {})
    if constraints_data:
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            total_count = constraints_data.get('total_count', 0)
            total_pct = constraints_data.get('total_percentage', 0)
            st.metric("Total Constrained", f"{total_count}", f"{total_pct:.1f}%")

        by_category = constraints_data.get('by_category', {})

        with col2:
            hard_data = by_category.get('Hard', {})
            hard_count = hard_data.get('count', 0)
            hard_pct = hard_data.get('percentage', 0)
            st.metric("Hard Constraints", f"{hard_count}", f"{hard_pct:.1f}%",
                     help="Must/On dates - Minimize and justify")

        with col3:
            flex_data = by_category.get('Flexible', {})
            flex_count = flex_data.get('count', 0)
            flex_pct = flex_data.get('percentage', 0)
            st.metric("Flexible Constraints", f"{flex_count}", f"{flex_pct:.1f}%",
                     help="On or Before/After - Use sparingly")

        with col4:
            sched_data = by_category.get('Schedule-Driven', {})
            sched_count = sched_data.get('count', 0)
            sched_pct = sched_data.get('percentage', 0)
            st.metric("Schedule-Driven", f"{sched_count}", f"{sched_pct:.1f}%",
                     help="ALAP/ASAP - Generally acceptable")

        st.markdown("---")

        # Breakdown by constraint type
        st.markdown("#### Constraint Type Breakdown")

        col1, col2 = st.columns(2)

        with col1:
            # Pie chart showing distribution
            if total_count > 0:
                categories = []
                counts = []
                for cat_name, cat_data in by_category.items():
                    if cat_data.get('count', 0) > 0:
                        categories.append(cat_name)
                        counts.append(cat_data.get('count', 0))

                if categories:
                    fig = px.pie(
                        values=counts,
                        names=categories,
                        title="Constraints by Category",
                        color_discrete_sequence=px.colors.qualitative.Set2
                    )
                    st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Guidance and recommendations
            st.markdown("**Guidance:**")
            st.info(constraints_data.get('guidance', 'Constraints should be minimized and duly justified'))

            st.markdown("**Constraint Categories:**")
            st.markdown("""
            - **Hard** (Must/On): Specific date required - Use only when contractually mandated
            - **Flexible** (Or Before/After): Date boundary - Should be justified
            - **Schedule-Driven** (ALAP/ASAP): Logic-driven - Generally acceptable but review if excessive
            """)

        # Detailed breakdown table
        st.markdown("#### Activities with Constraints by Type")

        # Create tabs for each constraint type
        constraint_tabs = st.tabs(["Hard", "Flexible", "Schedule-Driven", "All"])

        with constraint_tabs[0]:  # Hard
            hard_activities = hard_data.get('activities', [])
            if hard_activities:
                st.warning(f"⚠️ {len(hard_activities)} activities have hard date constraints")
                df_hard = pd.DataFrame(hard_activities)
                st.dataframe(
                    df_hard[['activity_id', 'activity_name', 'constraint_type']],
                    use_container_width=True,
                    height=300
                )
            else:
                st.success("✅ No hard constraints - Excellent!")

        with constraint_tabs[1]:  # Flexible
            flex_activities = flex_data.get('activities', [])
            if flex_activities:
                st.info(f"ℹ️ {len(flex_activities)} activities have flexible date constraints")
                df_flex = pd.DataFrame(flex_activities)
                st.dataframe(
                    df_flex[['activity_id', 'activity_name', 'constraint_type']],
                    use_container_width=True,
                    height=300
                )
            else:
                st.success("✅ No flexible constraints")

        with constraint_tabs[2]:  # Schedule-Driven
            sched_activities = sched_data.get('activities', [])
            if sched_activities:
                st.info(f"ℹ️ {len(sched_activities)} activities have schedule-driven constraints")
                df_sched = pd.DataFrame(sched_activities)
                st.dataframe(
                    df_sched[['activity_id', 'activity_name', 'constraint_type']],
                    use_container_width=True,
                    height=300
                )
            else:
                st.info("No schedule-driven constraints")

        with constraint_tabs[3]:  # All
            all_constrained = constraints_data.get('all_activities', [])
            if all_constrained:
                df_all = pd.DataFrame(all_constrained)
                st.dataframe(
                    df_all[['activity_id', 'activity_name', 'constraint_type', 'category']],
                    use_container_width=True,
                    height=300
                )

                # Download option
                csv = df_all[['activity_id', 'activity_name', 'constraint_type', 'category']].to_csv(index=False)
                st.download_button(
                    label="📥 Download Constrained Activities (CSV)",
                    data=csv,
                    file_name=f"constrained_activities_{schedule['file_name']}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.success("✅ No constrained activities!")
    else:
        st.info("No constraint data available")

# ============================================================================
# HELPER FUNCTIONS FOR FLOAT ANALYSIS - Calculate chart data on-demand
# ============================================================================

def calculate_float_distribution(activities):
    """Calculate float distribution for histogram and donut chart"""
    try:
        if not activities:
            return {}

        df = pd.DataFrame(activities)
        if 'Total Float' not in df.columns:
            return {}

        float_series = df['Total Float'].dropna()

        if len(float_series) == 0:
            return {}

        distribution = {
            'negative': int((float_series < 0).sum()),
            'critical': int((float_series == 0).sum()),
            'near_critical': int(((float_series > 0) & (float_series <= 10)).sum()),
            'low_risk': int(((float_series > 10) & (float_series <= 30)).sum()),
            'comfortable': int((float_series > 30).sum())
        }

        return distribution
    except Exception as e:
        # Return empty dict on any error to prevent tab crash
        return {}

def calculate_float_by_wbs(activities):
    """Calculate float by WBS code for box plot"""
    try:
        if not activities:
            return {}

        df = pd.DataFrame(activities)

        # Check if required columns exist
        if 'Total Float' not in df.columns:
            return {}

        if 'WBS Code' not in df.columns:
            return {}

        # Filter out rows with NaN in WBS Code or Total Float
        valid_df = df.dropna(subset=['WBS Code', 'Total Float'])

        if len(valid_df) == 0:
            return {}

        # Group by WBS and get float values (excluding NaN)
        wbs_groups = valid_df.groupby('WBS Code')['Total Float'].apply(list).to_dict()

        # Get top 10 WBS codes by activity count
        wbs_counts = valid_df['WBS Code'].value_counts().head(10)

        if len(wbs_counts) == 0:
            return {}

        # Return float values for top 10 WBS codes
        float_by_wbs = {
            str(wbs): [float(f) for f in wbs_groups.get(wbs, [])]
            for wbs in wbs_counts.index
        }

        return float_by_wbs
    except Exception as e:
        # Return empty dict on any error to prevent tab crash
        return {}

def get_negative_float_activities(activities):
    """Get list of activities with negative float (sorted by most negative)"""
    try:
        if not activities:
            return []

        df = pd.DataFrame(activities)
        if 'Total Float' not in df.columns:
            return []

        # Filter negative float
        negative_df = df[df['Total Float'] < 0].copy()

        if len(negative_df) == 0:
            return []

        # Sort by most negative first
        negative_df = negative_df.sort_values('Total Float')

        # Return top 20
        result = []
        for _, row in negative_df.head(20).iterrows():
            result.append({
                'activity_id': row.get('Activity ID', 'N/A'),
                'activity_name': row.get('Activity Name', 'N/A'),
                'total_float': float(row['Total Float']),
                'status': row.get('Activity Status', 'N/A')
            })

        return result
    except Exception as e:
        # Return empty list on any error to prevent tab crash
        return []

# ============================================================================
# Tab 3: Float Analysis
# ============================================================================

with tab3:
    try:
        st.markdown("## Comprehensive Total Float Analysis")

        # Defensive data validation
        if 'schedule_data' not in schedule or schedule['schedule_data'] is None:
            st.warning("⚠️ Schedule data not available")
            st.info("Please upload a schedule first to view Float Analysis.")
            st.stop()

        float_data = metrics.get('comprehensive_float', {})

        # Calculate chart data on-demand from activities (not stored in metrics)
        activities = schedule['schedule_data'].get('activities', [])

        # Validate activities data
        if not activities or not isinstance(activities, list):
            st.warning("⚠️ No activity data available for Float Analysis")
            st.info("The schedule data may be incomplete. Please re-upload the schedule.")
            st.stop()

        # Safely calculate chart data with error handling
        try:
            distribution = calculate_float_distribution(activities)
        except Exception as e:
            st.error(f"Error calculating float distribution: {str(e)}")
            distribution = {}

        try:
            float_by_wbs = calculate_float_by_wbs(activities)
        except Exception as e:
            st.error(f"Error calculating float by WBS: {str(e)}")
            float_by_wbs = {}

        try:
            negative_activities = get_negative_float_activities(activities)
        except Exception as e:
            st.error(f"Error getting negative float activities: {str(e)}")
            negative_activities = []

        if not float_data or 'error' in float_data:
            if 'error' in float_data:
                st.error(f"⚠️ {float_data['error']}")
            else:
                st.warning("⚠️ Float analysis data not available")
                st.info("This analysis may have been created with an older version. Please re-analyze the schedule to generate float analysis metrics.")
            st.info("Total Float column is required for float analysis. Please ensure your CSV export includes the 'Total Float(d)' column.")
        elif 'total_activities' not in float_data:
            st.warning("⚠️ Incomplete float analysis data")
            st.info("Float analysis metrics are incomplete. Please re-analyze the schedule.")
        else:
            # Summary KPI Cards at the top
            st.markdown("### 📊 Key Performance Indicators")

            col1, col2, col3, col4 = st.columns(4)

            # KPI 1: Critical Path
            critical_data = float_data.get('critical', {})
            critical_count = critical_data.get('count', 0)
            critical_pct = critical_data.get('percentage', 0)
            critical_status = critical_data.get('status', 'unknown')

            with col1:
                if critical_status == 'good':
                    status_icon = "✓"
                    status_color = "green"
                elif critical_status == 'warning':
                    status_icon = "⚠"
                    status_color = "orange"
                else:
                    status_icon = "✗"
                    status_color = "red"

                st.markdown(f"""
                <div style="padding: 10px; border-left: 4px solid {status_color}; background-color: #f0f2f6; border-radius: 5px;">
                    <h4 style="margin: 0; color: {status_color};">{status_icon} Critical Path</h4>
                    <h2 style="margin: 5px 0;">{critical_count}</h2>
                    <p style="margin: 0; font-size: 14px;">{critical_pct:.1f}% of activities</p>
                    <p style="margin: 0; font-size: 12px; color: gray;">Target: 5-15%</p>
                </div>
                """, unsafe_allow_html=True)

            # KPI 2: Near-Critical
            near_critical_data = float_data.get('near_critical', {})
            near_critical_count = near_critical_data.get('count', 0)
            near_critical_pct = near_critical_data.get('percentage', 0)

            with col2:
                st.markdown(f"""
                <div style="padding: 10px; border-left: 4px solid orange; background-color: #f0f2f6; border-radius: 5px;">
                    <h4 style="margin: 0; color: orange;">⚠ Near-Critical</h4>
                    <h2 style="margin: 5px 0;">{near_critical_count}</h2>
                    <p style="margin: 0; font-size: 14px;">{near_critical_pct:.1f}% of activities</p>
                    <p style="margin: 0; font-size: 12px; color: gray;">Float: 1-10 days</p>
                </div>
                """, unsafe_allow_html=True)

            # KPI 3: Negative Float
            negative_data = float_data.get('negative_float', {})
            negative_count = negative_data.get('count', 0)
            negative_pct = negative_data.get('percentage', 0)
            negative_status = negative_data.get('status', 'unknown')

            with col3:
                if negative_status == 'good':
                    status_icon = "✓"
                    status_color = "green"
                else:
                    status_icon = "✗"
                    status_color = "red"

                st.markdown(f"""
                <div style="padding: 10px; border-left: 4px solid {status_color}; background-color: #f0f2f6; border-radius: 5px;">
                    <h4 style="margin: 0; color: {status_color};">{status_icon} Behind Schedule</h4>
                    <h2 style="margin: 5px 0;">{negative_count}</h2>
                    <p style="margin: 0; font-size: 14px;">{negative_pct:.1f}% of activities</p>
                    <p style="margin: 0; font-size: 12px; color: gray;">Target: 0</p>
                </div>
                """, unsafe_allow_html=True)

            # KPI 4: Float Ratio
            ratio_data = float_data.get('float_ratio', {})
            ratio_value = ratio_data.get('ratio', 0)
            ratio_status = ratio_data.get('status', 'unknown')

            with col4:
                if ratio_status == 'good':
                    status_icon = "✓"
                    status_color = "green"
                elif ratio_status == 'warning':
                    status_icon = "⚠"
                    status_color = "orange"
                else:
                    status_icon = "✗"
                    status_color = "red"

                st.markdown(f"""
                <div style="padding: 10px; border-left: 4px solid {status_color}; background-color: #f0f2f6; border-radius: 5px;">
                    <h4 style="margin: 0; color: {status_color};">{status_icon} Float Ratio</h4>
                    <h2 style="margin: 5px 0;">{ratio_value:.2f}</h2>
                    <p style="margin: 0; font-size: 14px;">Avg Float / Avg Duration</p>
                    <p style="margin: 0; font-size: 12px; color: gray;">Target: 0.5-1.5</p>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("---")

            # Row 2: Charts
            col1, col2 = st.columns(2)

            with col1:
                # Chart 1: Float Distribution Histogram
                st.markdown("#### Float Distribution Histogram")

                # distribution is calculated at top of tab from activities
                if distribution:
                    # Prepare data for histogram
                    categories = ['Negative\n(<0)', 'Critical\n(0)', 'Near-Critical\n(1-10)', 'Low Risk\n(11-30)', 'Comfortable\n(>30)']
                    counts = [
                        distribution.get('negative', 0),
                        distribution.get('critical', 0),
                        distribution.get('near_critical', 0),
                        distribution.get('low_risk', 0),
                        distribution.get('comfortable', 0)
                    ]
                    colors = ['#e74c3c', '#f39c12', '#f1c40f', '#2ecc71', '#27ae60']

                    fig = go.Figure(data=[
                        go.Bar(
                            x=categories,
                            y=counts,
                            marker_color=colors,
                            text=counts,
                            textposition='auto',
                            hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
                        )
                    ])

                    fig.update_layout(
                        xaxis_title="Float Range (days)",
                        yaxis_title="Number of Activities",
                        showlegend=False,
                        height=400
                    )

                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No distribution data available")

            with col2:
                # Chart 2: Critical Path Analysis Donut Chart
                st.markdown("#### Critical Path Analysis")

                if distribution:
                    labels = ['Critical (0)', 'Near-Critical (1-10)', 'Low Risk (11-30)', 'Comfortable (>30)']
                    values = [
                        distribution.get('critical', 0),
                        distribution.get('near_critical', 0),
                        distribution.get('low_risk', 0),
                        distribution.get('comfortable', 0)
                    ]
                    colors_donut = ['#e74c3c', '#f39c12', '#3498db', '#2ecc71']

                    fig = go.Figure(data=[
                        go.Pie(
                            labels=labels,
                            values=values,
                            hole=0.4,
                            marker=dict(colors=colors_donut),
                            textinfo='label+percent',
                            hovertemplate='<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>'
                        )
                    ])

                    fig.update_layout(
                        showlegend=True,
                        height=400,
                        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.05)
                    )

                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No distribution data available")

            st.markdown("---")

            # Row 3: Additional Metrics and Box Plot
            col1, col2 = st.columns([1, 2])

            with col1:
                # Additional Statistics
                st.markdown("#### Statistical Summary")

                stats = float_data.get('statistics', {})
                mean_float = stats.get('mean', 0)
                median_float = stats.get('median', 0)
                std_float = stats.get('std_dev', 0)

                st.metric("Mean Float", f"{mean_float:.1f} days")
                st.metric("Median Float", f"{median_float:.1f} days")
                st.metric("Std Deviation", f"{std_float:.1f} days")

                # Most negative float
                most_negative = float_data.get('most_negative', 0)
                if most_negative < 0:
                    st.metric("Worst Delay", f"{most_negative:.1f} days",
                             delta=None,
                             help="Most negative float value")

                # Excessive float
                excessive_data = float_data.get('excessive_float', {})
                excessive_count = excessive_data.get('count', 0)
                if excessive_count > 0:
                    excessive_pct = excessive_data.get('percentage', 0)
                    st.metric("Excessive Float", f"{excessive_count}",
                             delta=f"{excessive_pct:.1f}%",
                             help="Activities with float >50% of project duration")

            with col2:
                # Chart 3: Float Box Plot by WBS Code
                st.markdown("#### Float Distribution by WBS Code")

                # float_by_wbs is calculated at top of tab from activities
                if float_by_wbs and len(float_by_wbs) > 0:
                    # Prepare data for box plot
                    wbs_codes = list(float_by_wbs.keys())
                    float_values = list(float_by_wbs.values())

                    fig = go.Figure()

                    for wbs, floats in zip(wbs_codes, float_values):
                        if floats:  # Only add if there are float values
                            fig.add_trace(go.Box(
                                y=floats,
                                name=str(wbs),
                                boxmean='sd',  # Show mean and standard deviation
                                hovertemplate='<b>WBS: %{fullData.name}</b><br>Float: %{y:.1f} days<extra></extra>'
                            ))

                    fig.update_layout(
                        xaxis_title="WBS Code",
                        yaxis_title="Total Float (days)",
                        showlegend=False,
                        height=400,
                        xaxis={'categoryorder': 'total descending'}
                    )

                    # Add horizontal lines for thresholds
                    fig.add_hline(y=0, line_dash="dash", line_color="red",
                                 annotation_text="Critical", annotation_position="right")
                    fig.add_hline(y=10, line_dash="dash", line_color="orange",
                                 annotation_text="Near-Critical", annotation_position="right")

                    st.plotly_chart(fig, use_container_width=True)
                else:
                    # Debug information - why no data?
                    test_df = pd.DataFrame(activities)
                    if 'WBS Code' not in test_df.columns:
                        st.warning("⚠️ WBS Code column not found in schedule data")
                        st.info("Your P6 export may not include the WBS Code column. This is optional but recommended for detailed analysis.")
                    elif test_df['WBS Code'].isna().all():
                        st.warning("⚠️ All WBS Code values are empty")
                        st.info("Activities don't have WBS codes assigned. Please ensure WBS structure is defined in P6.")
                    elif 'Total Float' not in test_df.columns:
                        st.warning("⚠️ Total Float column not found")
                    else:
                        valid_wbs = test_df['WBS Code'].dropna()
                        valid_float = test_df['Total Float'].dropna()
                        st.info(f"ℹ️ Found {len(valid_wbs)} activities with WBS codes and {len(valid_float)} with Total Float values, but unable to create chart")

                        # Additional debug: show sample of WBS codes
                        if len(valid_wbs) > 0:
                            st.write("Sample WBS Codes:", list(valid_wbs.head(5).values))

                        # Check if both columns have valid data in the same rows
                        both_valid = test_df.dropna(subset=['WBS Code', 'Total Float'])
                        st.write(f"Activities with both WBS Code and Total Float: {len(both_valid)}")
                        if len(both_valid) == 0:
                            st.warning("No activities have both WBS Code AND Total Float values. Box plot requires both.")

            st.markdown("---")

            # Row 4: Negative Float Activities Table
            if negative_count > 0:
                st.markdown("#### 🔴 Activities with Negative Float (Behind Schedule)")

                # negative_activities is calculated at top of tab from activities
                if negative_activities:
                    # Limit to top 20
                    top_20 = negative_activities[:20]

                    df_negative = pd.DataFrame(top_20)

                    # Display as sortable table
                    st.dataframe(
                        df_negative,
                        use_container_width=True,
                        height=400,
                        column_config={
                            "activity_id": st.column_config.TextColumn("Activity ID"),
                            "activity_name": st.column_config.TextColumn("Activity Name", width="large"),
                            "total_float": st.column_config.NumberColumn("Total Float (days)", format="%.1f"),
                            "status": st.column_config.TextColumn("Status")
                        }
                    )

                    if len(negative_activities) > 20:
                        st.info(f"ℹ️ Showing top 20 of {len(negative_activities)} activities with negative float. Download full list below.")

                    # Download option
                    csv = df_negative.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Negative Float Activities (CSV)",
                        data=csv,
                        file_name=f"negative_float_activities_{schedule['file_name']}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
            else:
                st.success("✅ No activities with negative float - schedule is on track!")

            # Guidance Section
            st.markdown("---")
            st.markdown("#### 📖 Interpretation Guidance")

            guidance_col1, guidance_col2 = st.columns(2)

            with guidance_col1:
                st.markdown("""
                **Float Analysis Thresholds (DCMA Best Practices):**

                - **Critical Path (0 days):** 5-15% of activities is normal
                    - <5%: May indicate missing logic or over-optimization
                    - >15%: Concerning - schedule may be too tightly constrained

                - **Near-Critical (1-10 days):** Watch closely
                    - These activities can easily become critical
                    - Require active monitoring and mitigation planning

                - **Negative Float:** Always investigate immediately
                    - Indicates activities are behind schedule
                    - Requires corrective action and recovery plan
                """)

            with guidance_col2:
                st.markdown("""
                **Float Ratio (Avg Float / Avg Remaining Duration):**

                - **0.5 - 1.5:** Good - Healthy schedule flexibility
                - **< 0.5:** Poor - Schedule may be too tight
                - **> 1.5:** Poor - May indicate missing logic or unrealistic durations

                **Excessive Float (>50% project duration):**

                - May indicate missing predecessor/successor relationships
                - Could suggest activities not properly integrated into schedule logic
                - Review and add missing dependencies
                """)

    except Exception as e:
        st.error("⚠️ An error occurred in Float Analysis")
        st.error(f"Error details: {str(e)}")
        st.info("Please try refreshing the page or re-uploading the schedule. If the problem persists, contact support.")

        # Show detailed traceback in an expander for debugging
        import traceback
        with st.expander("🔧 Technical Details (for debugging)"):
            st.code(traceback.format_exc())

# ============================================================================
# Tab 4: WBS Analysis
# ============================================================================

with tab4:
    try:
        st.markdown("## WBS (Work Breakdown Structure) Analysis")

        wbs_analysis = metrics.get('wbs_analysis', {})

        if not wbs_analysis.get('available'):
            st.warning("⚠️ WBS analysis not available")
            st.info(wbs_analysis.get('message', 'WBS Code column not found in schedule data'))
        else:
            # Summary cards
            st.markdown("### 📊 WBS Overview")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Total Activities", wbs_analysis['total_activities'])

            with col2:
                st.metric("With WBS Codes", wbs_analysis['activities_with_wbs'])

            with col3:
                avg_depth = wbs_analysis.get('avg_depth', 0)
                st.metric("Avg WBS Depth", f"{avg_depth:.1f}")

            with col4:
                max_depth = wbs_analysis.get('max_depth', 0)
                st.metric("Max WBS Depth", max_depth)

            st.markdown("---")

            # Advanced WBS Hierarchy Visualizations
            st.markdown("### 🎨 WBS Hierarchy Visualization")

            # Prepare hierarchical data for treemap and sunburst
            level1 = wbs_analysis.get('level_1_phases', {})
            level2 = wbs_analysis.get('level_2_areas', {})

            if level1 or level2:
                # Build hierarchical dataframe
                hierarchy_data = []

                # Get activities for building full hierarchy
                activities = schedule['schedule_data'].get('activities', [])
                if activities:
                    df_activities = pd.DataFrame(activities)

                    # Check if we have WBS level columns
                    if 'wbs_level_0' in df_activities.columns and 'wbs_level_1' in df_activities.columns:
                        # Build hierarchy from activities
                        for _, row in df_activities.iterrows():
                            if pd.notna(row.get('wbs_level_0')):
                                level0_name = str(row['wbs_level_0'])
                                level1_name = str(row.get('wbs_level_1', '')) if pd.notna(row.get('wbs_level_1')) else None
                                level2_name = str(row.get('wbs_level_2', '')) if pd.notna(row.get('wbs_level_2')) else None

                                # Get health score for this path
                                health_score = 50  # Default
                                health_color = '#f39c12'  # Default orange

                                # Try to get health score from level1 stats
                                if level1_name and level1_name in level1:
                                    level1_stats = level1[level1_name]
                                    if 'health_score' in level1_stats:
                                        health_score = level1_stats['health_score'].get('score', 50)
                                        health_color = level1_stats['health_score'].get('color', '#f39c12')

                                # Try to get health score from level2 stats (more specific)
                                if level2_name and level2_name in level2:
                                    level2_stats = level2[level2_name]
                                    if 'health_score' in level2_stats:
                                        health_score = level2_stats['health_score'].get('score', 50)
                                        health_color = level2_stats['health_score'].get('color', '#f39c12')

                                hierarchy_data.append({
                                    'Level_0': level0_name,
                                    'Level_1': level1_name if level1_name else 'Unknown',
                                    'Level_2': level2_name if level2_name else 'Unknown',
                                    'Activity_ID': row.get('Activity ID', ''),
                                    'Health_Score': health_score,
                                    'Health_Color': health_color,
                                    'Count': 1
                                })

                    if hierarchy_data:
                        df_hierarchy = pd.DataFrame(hierarchy_data)

                        # Aggregate for visualizations
                        # Group by Level 0, Level 1, Level 2 and sum counts
                        df_agg = df_hierarchy.groupby(['Level_0', 'Level_1', 'Level_2']).agg({
                            'Count': 'sum',
                            'Health_Score': 'mean'
                        }).reset_index()

                        viz_col1, viz_col2 = st.columns(2)

                        with viz_col1:
                            st.markdown("#### 🔲 Treemap View")
                            st.caption("Size = activity count, Color = health score")

                            # Create treemap
                            fig_treemap = px.treemap(
                                df_agg,
                                path=['Level_0', 'Level_1', 'Level_2'],
                                values='Count',
                                color='Health_Score',
                                color_continuous_scale='RdYlGn',
                                color_continuous_midpoint=50,
                                range_color=[0, 100],
                                title="WBS Hierarchy - Treemap",
                                hover_data={'Health_Score': ':.1f', 'Count': True}
                            )
                            fig_treemap.update_layout(
                                height=500,
                                margin=dict(t=50, l=0, r=0, b=0)
                            )
                            fig_treemap.update_traces(
                                textposition='middle center',
                                textfont_size=11
                            )
                            st.plotly_chart(fig_treemap, use_container_width=True)

                        with viz_col2:
                            st.markdown("#### ☀️ Sunburst Chart")
                            st.caption("Hierarchical view from project → phase → area")

                            # Create sunburst
                            fig_sunburst = px.sunburst(
                                df_agg,
                                path=['Level_0', 'Level_1', 'Level_2'],
                                values='Count',
                                color='Health_Score',
                                color_continuous_scale='RdYlGn',
                                color_continuous_midpoint=50,
                                range_color=[0, 100],
                                title="WBS Hierarchy - Sunburst",
                                hover_data={'Health_Score': ':.1f', 'Count': True}
                            )
                            fig_sunburst.update_layout(
                                height=500,
                                margin=dict(t=50, l=0, r=0, b=0)
                            )
                            st.plotly_chart(fig_sunburst, use_container_width=True)

                        # Legend for health scores
                        st.markdown("**Health Score Legend:**")
                        legend_cols = st.columns(5)
                        with legend_cols[0]:
                            st.markdown("🟢 **Excellent** (80-100)")
                        with legend_cols[1]:
                            st.markdown("🟢 **Good** (65-79)")
                        with legend_cols[2]:
                            st.markdown("🟡 **Fair** (50-64)")
                        with legend_cols[3]:
                            st.markdown("🟠 **Poor** (35-49)")
                        with legend_cols[4]:
                            st.markdown("🔴 **Critical** (0-34)")
                    else:
                        st.info("Unable to build hierarchy visualization. Activities may not have complete WBS data.")

            st.markdown("---")

            # WBS Level 1 Analysis
            level1 = wbs_analysis.get('level_1_phases', {})
            if level1:
                st.markdown("### 📋 WBS Level 1 (Phases) Analysis")

                # Prepare data for visualization
                phases = []
                for wbs_code, stats in level1.items():
                    health_data = stats.get('health_score', {})
                    phases.append({
                        'Phase': f"Phase {wbs_code}",
                        'Activities': stats['activity_count'],
                        'Percentage': stats['percentage'],
                        'Avg Float': stats.get('avg_float', 0),
                        'Critical': stats.get('critical_count', 0),
                        'Negative Float': stats.get('negative_float_count', 0),
                        'Health Score': health_data.get('score', 0),
                        'Rating': health_data.get('rating', 'Unknown')
                    })

                df_phases = pd.DataFrame(phases)

                # Display health score cards for each phase
                st.markdown("#### Phase Health Scores")
                health_cols = st.columns(min(len(phases), 5))  # Max 5 columns
                for idx, phase_data in enumerate(phases[:5]):  # Show top 5
                    with health_cols[idx]:
                        score = phase_data['Health Score']
                        rating = phase_data['Rating']
                        # Determine color based on score
                        if score >= 80:
                            color = "🟢"
                        elif score >= 65:
                            color = "🟢"
                        elif score >= 50:
                            color = "🟡"
                        elif score >= 35:
                            color = "🟠"
                        else:
                            color = "🔴"
                        st.metric(
                            phase_data['Phase'],
                            f"{score:.0f}/100",
                            delta=rating,
                            delta_color="off"
                        )
                        st.caption(f"{color} {rating}")

                st.markdown("---")

                # Bar chart - Activities by Phase
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("#### Activities by Phase")
                    fig = px.bar(
                        df_phases,
                        x='Phase',
                        y='Activities',
                        text='Activities',
                        color='Avg Float',
                        color_continuous_scale='RdYlGn',
                        title="Activity Distribution by WBS Phase"
                    )
                    fig.update_traces(textposition='outside')
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)

                with col2:
                    st.markdown("#### Critical Activities by Phase")
                    fig = px.bar(
                        df_phases,
                        x='Phase',
                        y='Critical',
                        text='Critical',
                        color='Critical',
                        color_continuous_scale='Reds',
                        title="Critical Activities by WBS Phase"
                    )
                    fig.update_traces(textposition='outside')
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)

                # Detailed table
                st.markdown("#### Detailed Phase Statistics")
                st.dataframe(
                    df_phases,
                    use_container_width=True,
                    column_config={
                        "Phase": st.column_config.TextColumn("Phase"),
                        "Activities": st.column_config.NumberColumn("Activities", format="%d"),
                        "Percentage": st.column_config.NumberColumn("% of Total", format="%.1f%%"),
                        "Avg Float": st.column_config.NumberColumn("Avg Float (days)", format="%.1f"),
                        "Critical": st.column_config.NumberColumn("Critical Count", format="%d"),
                        "Negative Float": st.column_config.NumberColumn("Behind Schedule", format="%d"),
                        "Health Score": st.column_config.NumberColumn("Health Score", format="%.0f"),
                        "Rating": st.column_config.TextColumn("Rating")
                    },
                    hide_index=True
                )

            st.markdown("---")

            # WBS Level 2 Analysis
            level2 = wbs_analysis.get('level_2_areas', {})
            if level2:
                st.markdown("### 🗺️ WBS Level 2 (Areas) Analysis")

                # Prepare data
                areas = []
                for wbs_code, stats in level2.items():
                    health_data = stats.get('health_score', {})
                    areas.append({
                        'Area': f"Area {wbs_code}",
                        'Activities': stats['activity_count'],
                        'Percentage': stats['percentage'],
                        'Avg Float': stats.get('avg_float', 0),
                        'Critical': stats.get('critical_count', 0),
                        '% Critical': round(stats.get('critical_count', 0) / stats['activity_count'] * 100, 1) if stats['activity_count'] > 0 else 0,
                        'Health Score': health_data.get('score', 0),
                        'Rating': health_data.get('rating', 'Unknown')
                    })

                df_areas = pd.DataFrame(areas)

                # Display health score cards for each area
                st.markdown("#### Area Health Scores")
                # Sort by health score to show critical areas first
                areas_sorted_by_health = sorted(areas, key=lambda x: x['Health Score'])
                health_cols = st.columns(min(len(areas), 5))  # Max 5 columns
                for idx, area_data in enumerate(areas_sorted_by_health[:5]):  # Show worst 5
                    with health_cols[idx]:
                        score = area_data['Health Score']
                        rating = area_data['Rating']
                        # Determine color based on score
                        if score >= 80:
                            color = "🟢"
                        elif score >= 65:
                            color = "🟢"
                        elif score >= 50:
                            color = "🟡"
                        elif score >= 35:
                            color = "🟠"
                        else:
                            color = "🔴"
                        st.metric(
                            area_data['Area'],
                            f"{score:.0f}/100",
                            delta=rating,
                            delta_color="off"
                        )
                        st.caption(f"{color} {rating}")

                st.markdown("---")

                # Heatmap-style visualization
                st.markdown("#### Area Health Overview")

                # Sort by % Critical (descending) to show problem areas first
                df_areas_sorted = df_areas.sort_values('% Critical', ascending=False)

                fig = px.bar(
                    df_areas_sorted,
                    x='Area',
                    y='Activities',
                    color='% Critical',
                    color_continuous_scale='RdYlGn_r',  # Reverse: Red=high, Green=low
                    title="WBS Areas - Colored by % Critical Activities",
                    hover_data=['Avg Float', 'Critical', '% Critical']
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)

                # Detailed table
                st.markdown("#### Detailed Area Statistics")
                st.dataframe(
                    df_areas_sorted,
                    use_container_width=True,
                    column_config={
                        "Area": st.column_config.TextColumn("Area"),
                        "Activities": st.column_config.NumberColumn("Activities", format="%d"),
                        "Percentage": st.column_config.NumberColumn("% of Total", format="%.1f%%"),
                        "Avg Float": st.column_config.NumberColumn("Avg Float (days)", format="%.1f"),
                        "Critical": st.column_config.NumberColumn("Critical Count", format="%d"),
                        "% Critical": st.column_config.NumberColumn("% Critical", format="%.1f%%"),
                        "Health Score": st.column_config.NumberColumn("Health Score", format="%.0f"),
                        "Rating": st.column_config.TextColumn("Rating")
                    },
                    hide_index=True
                )

                # Identify problem areas
                problem_areas = df_areas[df_areas['% Critical'] > 50]
                if len(problem_areas) > 0:
                    st.warning(f"⚠️ {len(problem_areas)} area(s) have >50% critical activities")
                    st.write("**High-Risk Areas:**")
                    for _, area in problem_areas.iterrows():
                        st.write(f"- **{area['Area']}**: {area['% Critical']:.0f}% critical ({area['Critical']}/{area['Activities']} activities)")

            # Guidance
            st.markdown("---")
            st.markdown("### 📖 WBS Analysis Interpretation")

            guidance_col1, guidance_col2 = st.columns(2)

            with guidance_col1:
                st.markdown("""
                **What to Look For:**

                - **High % Critical in Phase/Area**: Indicates schedule risk and lack of flexibility
                - **Low Average Float**: Suggests tight schedule in that area
                - **Uneven Distribution**: May indicate poor work breakdown or sequencing issues
                - **Areas with Negative Float**: Require immediate attention and recovery plan
                """)

            with guidance_col2:
                st.markdown("""
                **Recommended Actions:**

                - **Areas >50% Critical**: Add parallel paths, review dependencies
                - **Low Float Areas**: Add schedule buffer, consider resource loading
                - **Behind Schedule**: Prioritize recovery actions, crash activities
                - **Balanced WBS**: Aim for 5-15% critical across all major areas
                """)

    except Exception as e:
        st.error("⚠️ An error occurred in WBS Analysis")
        st.error(f"Error details: {str(e)}")
        st.info("Please try refreshing the page or re-uploading the schedule. If the problem persists, contact support.")

        # Show detailed traceback in an expander for debugging
        import traceback
        with st.expander("🔧 Technical Details (for debugging)"):
            st.code(traceback.format_exc())

# ============================================================================
# Tab 5: Issues
# ============================================================================

with tab5:
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

# Tab 6: Recommendations
with tab6:
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

# Tab 7: Activities
with tab7:
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
