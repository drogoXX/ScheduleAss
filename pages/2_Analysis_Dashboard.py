"""
Analysis Dashboard Page
Displays comprehensive schedule quality analysis
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from src.services import get_auth, get_database, load_analysis, load_schedule
from src.ui.charts import FLOAT_BUCKET_COLORS
from src.ui.diagnostics import timed
from src.ui.theme import (
    CHART_SCALE_CRITICALITY, CHART_SCALE_DIVERGING, CHART_SEQUENCE, COLORS,
    COLUMN_FORMAT, RATING_COLORS, app_header, apply_chart_theme, fmt_count,
    fmt_days, fmt_index, fmt_pct, fmt_ratio, fmt_score, inject_css, kpi_card,
    section_divider, status_badge, threshold_status,
)
from src.utils.helpers import (
    init_session_state, display_health_score, display_issue_card,
    display_recommendation_card, display_no_data_message, report_error
)

st.set_page_config(page_title="Analysis Dashboard", page_icon="📊", layout="wide")
inject_css("Analysis Dashboard")

# Initialize
init_session_state()
db = get_database()
auth = get_auth(db)

# Check authentication
auth.require_auth()

app_header(
    "📊 Analysis Dashboard",
    "DCMA 14-point assessment, float analysis and WBS breakdown for a selected schedule",
)


def _float_variant(status: str) -> str:
    """Map the analyser's good/warning/* status vocabulary to a badge variant."""
    return {'good': 'success', 'warning': 'warning'}.get(str(status).lower(), 'danger')


def _rating_variant(rating: str) -> str:
    """Map a health-score rating to a badge variant."""
    return {
        'excellent': 'success', 'good': 'success', 'fair': 'warning',
        'poor': 'warning', 'critical': 'danger',
    }.get(str(rating).lower(), 'neutral')

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
    "Choose a schedule to analyze",
    options=list(schedule_options.keys())
)

selected_schedule_id = schedule_options[selected_schedule_label]
with timed("Dashboard: load schedule"):
    schedule = load_schedule(selected_schedule_id)
with timed("Dashboard: load analysis"):
    analysis = load_analysis(selected_schedule_id)

if not analysis:
    display_no_data_message("No analysis results available for this schedule.")
    st.stop()

# Store in session state
st.session_state.current_schedule = schedule
st.session_state.current_analysis = analysis

# Build the activity DataFrame ONCE per script run and share it across all tabs.
# st.tabs() renders every tab body on every rerun, so the previous code rebuilt this
# same frame at 8 separate call sites (~28ms each on a 6,300-activity schedule).
# A plain local is enough here - all tabs execute within this one script run, so no
# caching (and none of st.cache_data's copy-on-return semantics) is involved.
activities = schedule['schedule_data'].get('activities', [])
activities_df = pd.DataFrame(activities) if activities else pd.DataFrame()


class _TabHasNoData(Exception):
    """Raised inside a tab to end that tab only.

    Never use st.stop() inside a `with tab:` block: it raises StopException,
    which subclasses BaseException, escapes `except Exception`, and terminates
    the whole script - silently dropping every tab below it.
    """

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
        health_data = perf_metrics.get('health_score', {}) if perf_metrics else {}
        rating = health_data.get('rating', 'Unknown')

        display_health_score(health_score, rating)

        # Any ceiling or data-sufficiency gate that limited the score must be
        # stated, otherwise the number looks arbitrary.
        for cap in health_data.get('caps', []):
            st.warning(f"⚠️ {cap}")

        # The score is a weighted average of DCMA checks; show the workings so
        # it can be defended line by line rather than taken on trust.
        components = health_data.get('components', [])
        if components:
            with st.expander("🔬 How this score is calculated"):
                st.caption(
                    "Weighted average of DCMA 14-Point checks. Each check is "
                    "scored 100 at or better than its DCMA target, falling "
                    "linearly to 0 at the bound shown. Checks with no data are "
                    "marked n/a and excluded, and the remaining weights are "
                    "renormalised."
                )
                st.dataframe(
                    [
                        {
                            "DCMA": component.get('dcma_point') or '-',
                            "Check": component['label'],
                            "Measured": (
                                "n/a" if component['value'] is None
                                else f"{component['value']}{component['unit']}"
                            ),
                            "Target": component['target'],
                            "Weight": component['weight'],
                            "Score": (
                                "n/a" if component['score'] is None
                                else fmt_score(component['score'])
                            ),
                        }
                        for component in components
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
                st.caption(
                    "Thresholds follow the DCMA 14-Point Assessment. The "
                    "weights are this application's assessment of relative "
                    "severity, not a DCMA-defined figure."
                )

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
                # The target belongs in help/badge, not in delta: a delta string
                # renders as a green up-arrow and reads as an improvement that
                # was never measured.
                st.metric(
                    "CPLI",
                    fmt_index(cpli_value),
                    help="Critical Path Length Index. Target: ≥ 0.95"
                )
                st.markdown(
                    status_badge(
                        "Target ≥ 0.95",
                        threshold_status(cpli_value, 0.95, lower_is_better=False),
                    ),
                    unsafe_allow_html=True,
                )

                # BEI
                bei = analysis['performance_metrics'].get('bei', {})
                bei_value = bei.get('value', 0)
                st.metric(
                    "BEI",
                    fmt_index(bei_value),
                    help="Baseline Execution Index. Target: ≥ 0.95"
                )
                st.markdown(
                    status_badge(
                        "Target ≥ 0.95",
                        threshold_status(bei_value, 0.95, lower_is_better=False),
                    ),
                    unsafe_allow_html=True,
                )

        with col2_2:
            # Total activities
            total_activities = schedule['schedule_data']['total_activities']
            st.metric("Total Activities", fmt_count(total_activities))

            # Issues count
            issues_count = len(analysis['issues'])
            st.metric("Issues Identified", fmt_count(issues_count))

    section_divider()

    # Quick stats
    st.markdown("### Key Statistics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        neg_lags = metrics.get('negative_lags', {}).get('count', 0)
        st.metric("Negative Lags", fmt_count(neg_lags), help="Target: 0")

    with col2:
        pos_lags_pct = metrics.get('positive_lags', {}).get('percentage', 0)
        st.metric("Positive Lags %", fmt_pct(pos_lags_pct), help="Target: ≤5%")

    with col3:
        # Show total constrained activities
        constraints_data = metrics.get('constraints', {})
        total_constrained_pct = constraints_data.get('total_percentage', 0)
        st.metric("Activities with Constraints", fmt_pct(total_constrained_pct),
                 help="All constraint types (should be minimized and justified)")

    with col4:
        missing_logic = metrics.get('missing_logic', {}).get('count', 0)
        st.metric("Missing Logic", fmt_count(missing_logic),
                 help="Target: 0 - Total unique activities with missing logic")

    section_divider()

    # Missing Logic Breakdown
    if missing_logic > 0:
        st.markdown("### Missing Logic Breakdown")
        missing_logic_data = metrics.get('missing_logic', {})

        col_ml1, col_ml2, col_ml3, col_ml4 = st.columns(4)

        with col_ml1:
            total_count = missing_logic_data.get('count', 0)
            st.metric("Total Missing Logic", fmt_count(total_count),
                     help="Total unique activities with missing predecessor and/or successor")

        with col_ml2:
            pred_only = missing_logic_data.get('missing_predecessor_only_count', 0)
            st.metric("Missing Predecessor Only", fmt_count(pred_only),
                     help="Activities missing only predecessors")

        with col_ml3:
            succ_only = missing_logic_data.get('missing_successor_only_count', 0)
            st.metric("Missing Successor Only", fmt_count(succ_only),
                     help="Activities missing only successors")

        with col_ml4:
            both_count = missing_logic_data.get('missing_both_count', 0)
            st.metric("Missing Both", fmt_count(both_count),
                     help="Activities missing both predecessors and successors")

        # Add validation note
        dcma_missing_pred = metrics.get('dcma_missing_predecessors', {}).get('count', 0)
        dcma_missing_succ = metrics.get('dcma_missing_successors', {}).get('count', 0)

        st.caption(f"📊 **DCMA Counts:** Missing Predecessors: {dcma_missing_pred} | Missing Successors: {dcma_missing_succ} | Note: Activities missing both are counted in each category.")

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
            color_discrete_sequence=CHART_SEQUENCE
        )
        fig.update_traces(textinfo='label+percent')
        st.plotly_chart(apply_chart_theme(fig), use_container_width=True)
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
                'bar': {'color': COLORS['danger'] if neg_lags_count > 0
                        else COLORS['success']},
                'steps': [
                    {'range': [0, 0], 'color': COLORS['surface']},
                    {'range': [0, 50], 'color': COLORS['surface']}
                ],
                'bordercolor': COLORS['border'],
                'threshold': {
                    'line': {'color': COLORS['danger'], 'width': 4},
                    'thickness': 0.75,
                    'value': 0
                }
            }
        ))
        st.plotly_chart(apply_chart_theme(fig, height=300), use_container_width=True)

    with col2:
        # Positive lags chart
        pos_lags_pct = metrics.get('positive_lags', {}).get('percentage', 0)
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=pos_lags_pct,
            title={'text': "Positive Lags (%)"},
            delta={'reference': 5},
            number={'suffix': "%"},
            gauge={
                'axis': {'range': [0, 20], 'ticksuffix': "%"},
                'bar': {'color': COLORS['success'] if pos_lags_pct <= 5
                        else COLORS['warning']},
                'steps': [
                    {'range': [0, 5], 'color': COLORS['surface']},
                    {'range': [5, 20], 'color': COLORS['surface_alt']}
                ],
                'bordercolor': COLORS['border'],
                'threshold': {
                    'line': {'color': COLORS['danger'], 'width': 4},
                    'thickness': 0.75,
                    'value': 5
                }
            }
        ))
        st.plotly_chart(apply_chart_theme(fig, height=300), use_container_width=True)

    section_divider()

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

        st.metric("Average Duration", fmt_days(avg_duration),
                 help=f"Based on 'At Completion Duration' from P6")
        st.metric("Median Duration", fmt_days(median_duration))

        # Show analysis details
        if total_analyzed > 0:
            st.info(
                f"ℹ️ Analyzed {fmt_count(total_analyzed)} activities "
                f"(excluded {fmt_count(milestones_excluded)} milestones)"
            )

        # Show error if column not found
        if 'error' in avg_duration_data:
            st.error(f"⚠️ {avg_duration_data['error']}")

        long_durations = metrics.get('long_durations', {})
        st.metric("Activities >20 days",
                 fmt_count(long_durations.get('count_over_20_days', 0)),
                 help="Excluding milestones")
        st.metric("Activities >5 months",
                 fmt_count(long_durations.get('count_over_5_months', 0)),
                 help="Excluding milestones")

    with col2:
        # Duration distribution (if data available)
        if activities:
            df = activities_df
            if 'At Completion Duration' in df.columns:
                durations = df['At Completion Duration'].dropna()
                fig = px.histogram(
                    durations,
                    nbins=30,
                    title="Activity Duration Distribution",
                    labels={'value': 'Duration (days)', 'count': 'Frequency'},
                    color_discrete_sequence=[COLORS['primary']]
                )
                fig.add_vline(x=20, line_dash="dash",
                             line_color=COLORS['warning'],
                             annotation_text="20 days")
                fig.add_vline(x=150, line_dash="dash",
                             line_color=COLORS['danger'],
                             annotation_text="5 months")
                st.plotly_chart(
                    apply_chart_theme(
                        fig, showlegend=False,
                        xaxis_title="Duration (days)", yaxis_title="Activities",
                        xaxis_format="count", yaxis_format="count",
                    ),
                    use_container_width=True,
                )

    section_divider()

    # Relationship Types
    st.markdown("### Relationship Types Distribution")

    rel_types = metrics.get('relationship_types', {})
    if rel_types.get('total', 0) > 0:
        percentages = rel_types.get('percentages', {})
        # Single-colour bars: colouring by relationship type only produced a
        # legend that repeated the x-axis tick labels.
        fig = px.bar(
            x=list(percentages.keys()),
            y=list(percentages.values()),
            title="Relationship Type Breakdown",
            labels={'x': 'Relationship Type', 'y': 'Percentage (%)'},
            color_discrete_sequence=[COLORS['primary']]
        )
        st.plotly_chart(
            apply_chart_theme(
                fig, showlegend=False,
                xaxis_title="Relationship Type", yaxis_title="Share of relationships",
                yaxis_format="pct",
            ),
            use_container_width=True,
        )
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

        # The share of activities is a secondary figure, not a change over time.
        # Passing it as `delta` coloured it green or red at random; it belongs
        # in a caption underneath.
        with col1:
            total_count = constraints_data.get('total_count', 0)
            total_pct = constraints_data.get('total_percentage', 0)
            st.metric("Total Constrained", fmt_count(total_count))
            st.caption(f"{fmt_pct(total_pct)} of activities")

        by_category = constraints_data.get('by_category', {})

        with col2:
            hard_data = by_category.get('Hard', {})
            hard_count = hard_data.get('count', 0)
            hard_pct = hard_data.get('percentage', 0)
            st.metric("Hard Constraints", fmt_count(hard_count),
                     help="Must/On dates - Minimize and justify")
            st.caption(f"{fmt_pct(hard_pct)} of activities")

        with col3:
            flex_data = by_category.get('Flexible', {})
            flex_count = flex_data.get('count', 0)
            flex_pct = flex_data.get('percentage', 0)
            st.metric("Flexible Constraints", fmt_count(flex_count),
                     help="On or Before/After - Use sparingly")
            st.caption(f"{fmt_pct(flex_pct)} of activities")

        with col4:
            sched_data = by_category.get('Schedule-Driven', {})
            sched_count = sched_data.get('count', 0)
            sched_pct = sched_data.get('percentage', 0)
            st.metric("Schedule-Driven", fmt_count(sched_count),
                     help="ALAP/ASAP - Generally acceptable")
            st.caption(f"{fmt_pct(sched_pct)} of activities")

        section_divider()

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
                        color_discrete_sequence=CHART_SEQUENCE
                    )
                    fig.update_traces(textinfo='label+percent')
                    st.plotly_chart(apply_chart_theme(fig), use_container_width=True)

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

def calculate_float_distribution(df):
    """Calculate float distribution for histogram and donut chart

    Takes the prebuilt activity DataFrame (see activities_df above) rather than the
    raw activities list, so the frame is not reconstructed on every rerun.
    """
    try:
        if df is None or df.empty:
            return {}

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

def calculate_float_by_wbs(df):
    """Calculate float by WBS code for box plot

    Takes the prebuilt activity DataFrame (see activities_df above).
    """
    try:
        if df is None or df.empty:
            return {}

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

        # Ensure at least one WBS code has non-empty float values
        has_data = any(len(floats) > 0 for floats in float_by_wbs.values())
        if not has_data:
            return {}

        return float_by_wbs
    except Exception as e:
        # Return empty dict on any error to prevent tab crash
        return {}

def get_negative_float_activities(df):
    """Get list of activities with negative float (sorted by most negative)

    Takes the prebuilt activity DataFrame (see activities_df above).
    """
    try:
        if df is None or df.empty:
            return []

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

        # Defensive data validation.
        #
        # These raise rather than calling st.stop(). st.stop() raises
        # StopException, which subclasses BaseException, so it escapes the
        # `except Exception` below and halts the ENTIRE script - taking tabs 4-7
        # (WBS, Issues, Recommendations, Activities) down with it and leaving the
        # page looking broken. A tab with no data must end that tab only.
        if 'schedule_data' not in schedule or schedule['schedule_data'] is None:
            st.warning("⚠️ Schedule data not available")
            st.info("Please upload a schedule first to view Float Analysis.")
            raise _TabHasNoData

        float_data = metrics.get('comprehensive_float', {})

        # `activities` / `activities_df` are built once near the top of this page.

        # Validate activities data
        if not activities or not isinstance(activities, list):
            st.warning("⚠️ No activity data available for Float Analysis")
            st.info("The schedule data may be incomplete. Please re-upload the schedule.")
            raise _TabHasNoData

        # Safely calculate chart data with error handling
        try:
            distribution = calculate_float_distribution(activities_df)
        except Exception as e:
            report_error("Float distribution could not be calculated.", e, logger_name="dashboard")
            distribution = {}

        try:
            float_by_wbs = calculate_float_by_wbs(activities_df)
        except Exception as e:
            report_error("Float by WBS could not be calculated.", e, logger_name="dashboard")
            float_by_wbs = {}

        try:
            negative_activities = get_negative_float_activities(activities_df)
        except Exception as e:
            report_error("Negative float activities could not be listed.", e, logger_name="dashboard")
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
                kpi_card(
                    "Critical Path",
                    fmt_count(critical_count),
                    subtitle=f"{fmt_pct(critical_pct)} of activities",
                    target="Target: 5-15%",
                    status=_float_variant(critical_status),
                )

            # KPI 2: Near-Critical
            near_critical_data = float_data.get('near_critical', {})
            near_critical_count = near_critical_data.get('count', 0)
            near_critical_pct = near_critical_data.get('percentage', 0)

            with col2:
                kpi_card(
                    "Near-Critical",
                    fmt_count(near_critical_count),
                    subtitle=f"{fmt_pct(near_critical_pct)} of activities",
                    target="Float: 1-10 days",
                    status="warning",
                )

            # KPI 3: Negative Float
            negative_data = float_data.get('negative_float', {})
            negative_count = negative_data.get('count', 0)
            negative_pct = negative_data.get('percentage', 0)
            negative_status = negative_data.get('status', 'unknown')

            with col3:
                kpi_card(
                    "Behind Schedule",
                    fmt_count(negative_count),
                    subtitle=f"{fmt_pct(negative_pct)} of activities",
                    target="Target: 0",
                    status="success" if negative_status == 'good' else "danger",
                )

            # KPI 4: Float Ratio
            ratio_data = float_data.get('float_ratio', {})
            ratio_value = ratio_data.get('ratio', 0)
            ratio_status = ratio_data.get('status', 'unknown')

            with col4:
                kpi_card(
                    "Float Ratio",
                    fmt_ratio(ratio_value),
                    subtitle="Avg Float / Avg Duration",
                    target="Target: 0.5-1.5",
                    status=_float_variant(ratio_status),
                )

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
                    fig = go.Figure(data=[
                        go.Bar(
                            x=categories,
                            y=counts,
                            marker_color=FLOAT_BUCKET_COLORS,
                            text=[fmt_count(c) for c in counts],
                            textposition='auto',
                            hovertemplate='<b>%{x}</b><br>Count: %{y:,}<extra></extra>'
                        )
                    ])

                    st.plotly_chart(
                        apply_chart_theme(
                            fig, showlegend=False,
                            xaxis_title="Float Range (days)",
                            yaxis_title="Number of Activities",
                            yaxis_format="count",
                        ),
                        use_container_width=True,
                    )
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
                    # Same buckets as the histogram beside it, minus 'Negative',
                    # so the shared colours must line up: skip the first entry.
                    fig = go.Figure(data=[
                        go.Pie(
                            labels=labels,
                            values=values,
                            hole=0.4,
                            marker=dict(colors=FLOAT_BUCKET_COLORS[1:]),
                            textinfo='label+percent',
                            hovertemplate='<b>%{label}</b><br>Count: %{value:,}<br>Percentage: %{percent}<extra></extra>'
                        )
                    ])

                    st.plotly_chart(
                        apply_chart_theme(fig, showlegend=True),
                        use_container_width=True,
                    )
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

                st.metric("Mean Float", fmt_days(mean_float))
                st.metric("Median Float", fmt_days(median_float))
                st.metric("Std Deviation", fmt_days(std_float))

                # Most negative float
                most_negative = float_data.get('most_negative', 0)
                if most_negative < 0:
                    st.metric("Worst Delay", fmt_days(most_negative),
                             help="Most negative float value")

                # Excessive float
                excessive_data = float_data.get('excessive_float', {})
                excessive_count = excessive_data.get('count', 0)
                if excessive_count > 0:
                    excessive_pct = excessive_data.get('percentage', 0)
                    st.metric("Excessive Float", fmt_count(excessive_count),
                             help="Activities with float >50% of project duration")
                    st.caption(f"{fmt_pct(excessive_pct)} of activities")

            with col2:
                # Chart 3: Float Box Plot by WBS Code
                st.markdown("#### Float Distribution by WBS Code")

                # float_by_wbs is calculated at top of tab from activities
                if float_by_wbs and len(float_by_wbs) > 0:
                    # One box per WBS code becomes unreadable on a real
                    # schedule, so show only the busiest codes and say so.
                    MAX_WBS_BOXES = 15
                    populated = [
                        (wbs, floats) for wbs, floats in float_by_wbs.items() if floats
                    ]
                    populated.sort(key=lambda item: len(item[1]), reverse=True)
                    shown = populated[:MAX_WBS_BOXES]
                    hidden_count = len(populated) - len(shown)

                    fig = go.Figure()
                    for wbs, floats in shown:
                        fig.add_trace(go.Box(
                            y=floats,
                            name=str(wbs),
                            marker_color=COLORS['primary'],
                            line_color=COLORS['primary'],
                            boxmean='sd',  # Show mean and standard deviation
                            hovertemplate='<b>WBS: %{fullData.name}</b><br>Float: %{y:.1f} days<extra></extra>'
                        ))

                    # Only display chart if traces were actually added
                    if shown:
                        apply_chart_theme(
                            fig, showlegend=False,
                            xaxis_title="WBS Code",
                            yaxis_title="Total Float (days)",
                            yaxis_format="days",
                            xaxis={'categoryorder': 'total descending'},
                        )

                        # Add horizontal lines for thresholds
                        fig.add_hline(y=0, line_dash="dash",
                                     line_color=COLORS['danger'],
                                     annotation_text="Critical", annotation_position="right")
                        fig.add_hline(y=10, line_dash="dash",
                                     line_color=COLORS['warning'],
                                     annotation_text="Near-Critical", annotation_position="right")

                        st.plotly_chart(fig, use_container_width=True)
                        if hidden_count > 0:
                            st.caption(
                                f"Showing the {len(shown)} WBS codes with the most "
                                f"activities; {fmt_count(hidden_count)} further "
                                f"code(s) not plotted."
                            )
                    else:
                        # No traces were added - show debug info
                        st.info("⚠️ WBS codes found but no valid float data to display")
                        test_df = activities_df
                        st.write(f"Debug: Found {len(float_by_wbs)} WBS codes, but all have empty float value lists")
                        both_valid = test_df.dropna(subset=['WBS Code', 'Total Float'])
                        st.write(f"Activities with both WBS Code and Total Float: {len(both_valid)}")
                else:
                    # Debug information - why no data?
                    test_df = activities_df
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
                            "total_float": st.column_config.NumberColumn("Total Float (days)", format=COLUMN_FORMAT["days"]),
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

    except _TabHasNoData:
        # Already explained to the user above; the remaining tabs still render.
        pass
    except Exception as e:
        report_error(
            "Float Analysis could not be displayed for this schedule. "
            "Try re-uploading the schedule; if the problem persists, quote the "
            "reference below to your administrator.",
            e,
            logger_name="dashboard",
        )

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
                st.metric("Total Activities",
                          fmt_count(wbs_analysis['total_activities']))

            with col2:
                st.metric("With WBS Codes",
                          fmt_count(wbs_analysis['activities_with_wbs']))

            with col3:
                avg_depth = wbs_analysis.get('avg_depth', 0)
                st.metric("Avg WBS Depth", fmt_days(avg_depth, unit=False))

            with col4:
                max_depth = wbs_analysis.get('max_depth', 0)
                st.metric("Max WBS Depth", fmt_count(max_depth))

            section_divider()

            # Advanced WBS Hierarchy Visualizations
            st.markdown("### 🎨 WBS Hierarchy Visualization")

            # Prepare hierarchical data for treemap and sunburst
            level1 = wbs_analysis.get('level_1_phases', {})
            level2 = wbs_analysis.get('level_2_areas', {})

            if level1 or level2:
                # Build hierarchical dataframe
                hierarchy_data = []

                if activities:
                    df_activities = activities_df

                    # Check if we have WBS level columns
                    if 'wbs_level_0' in df_activities.columns and 'wbs_level_1' in df_activities.columns:
                        # Build hierarchy from activities.
                        # Iterate over plain column arrays rather than .iterrows(): this runs
                        # on every rerun (st.tabs renders all tab bodies), and building one
                        # Series per row cost ~183ms on a 6,300-activity schedule.
                        def _col(name, default=''):
                            if name in df_activities.columns:
                                return df_activities[name].to_numpy()
                            return np.full(len(df_activities), default, dtype=object)

                        _l0 = _col('wbs_level_0')
                        _l1 = _col('wbs_level_1')
                        _l2 = _col('wbs_level_2')
                        _ids = _col('Activity ID')

                        for l0_val, l1_val, l2_val, act_id in zip(_l0, _l1, _l2, _ids):
                            if pd.notna(l0_val):
                                level0_name = str(l0_val)
                                level1_name = str(l1_val) if pd.notna(l1_val) else None
                                level2_name = str(l2_val) if pd.notna(l2_val) else None

                                # Get health score for this path
                                health_score = 50  # Default
                                health_color = RATING_COLORS['Fair']

                                # Try to get health score from level1 stats
                                if level1_name and level1_name in level1:
                                    level1_stats = level1[level1_name]
                                    if 'health_score' in level1_stats:
                                        health_score = level1_stats['health_score'].get('score', 50)
                                        health_color = level1_stats['health_score'].get('color', RATING_COLORS['Fair'])

                                # Try to get health score from level2 stats (more specific)
                                if level2_name and level2_name in level2:
                                    level2_stats = level2[level2_name]
                                    if 'health_score' in level2_stats:
                                        health_score = level2_stats['health_score'].get('score', 50)
                                        health_color = level2_stats['health_score'].get('color', RATING_COLORS['Fair'])

                                hierarchy_data.append({
                                    'Level_0': level0_name,
                                    'Level_1': level1_name if level1_name else 'Unknown',
                                    'Level_2': level2_name if level2_name else 'Unknown',
                                    'Activity_ID': act_id,
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

                        st.markdown("#### 🔲 WBS Hierarchy")
                        st.caption(
                            "Size = activity count, colour = health score. "
                            "Click a block to drill into it."
                        )

                        # A sunburst of this same aggregate used to sit beside
                        # the treemap; it plotted identical data, so the denser
                        # of the two is kept and the duplicate removed.
                        fig_treemap = px.treemap(
                            df_agg,
                            path=['Level_0', 'Level_1', 'Level_2'],
                            values='Count',
                            color='Health_Score',
                            color_continuous_scale=CHART_SCALE_DIVERGING,
                            color_continuous_midpoint=50,
                            range_color=[0, 100],
                            hover_data={'Health_Score': ':.1f', 'Count': True}
                        )
                        fig_treemap.update_traces(
                            textposition='middle center',
                            textfont_size=12
                        )
                        st.plotly_chart(
                            apply_chart_theme(
                                fig_treemap, height=520,
                                margin=dict(t=16, l=0, r=0, b=0),
                                coloraxis_colorbar=dict(title="Health"),
                            ),
                            use_container_width=True,
                        )

                        # Legend for health scores
                        st.markdown("**Health Score Legend:**")
                        legend_bands = [
                            ("Excellent", "80-100"), ("Good", "65-79"),
                            ("Fair", "50-64"), ("Poor", "35-49"),
                            ("Critical", "0-34"),
                        ]
                        legend_cols = st.columns(len(legend_bands))
                        for col, (band, band_range) in zip(legend_cols, legend_bands):
                            with col:
                                st.markdown(
                                    f'<span class="status-badge" style="background-color:'
                                    f'{RATING_COLORS[band]};">{band}</span> '
                                    f'<span style="color:{COLORS["text_muted"]};">'
                                    f'{band_range}</span>',
                                    unsafe_allow_html=True,
                                )
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
                        st.metric(phase_data['Phase'], fmt_score(score))
                        st.markdown(
                            status_badge(rating, _rating_variant(rating)),
                            unsafe_allow_html=True,
                        )

                section_divider()

                # Bar chart - Activities by Phase
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("#### Activities by Phase")
                    # More float is better, so the diverging scale runs
                    # danger -> success.
                    fig = px.bar(
                        df_phases,
                        x='Phase',
                        y='Activities',
                        text='Activities',
                        color='Avg Float',
                        color_continuous_scale=CHART_SCALE_DIVERGING,
                        title="Activity Distribution by WBS Phase"
                    )
                    fig.update_traces(textposition='outside')
                    st.plotly_chart(
                        apply_chart_theme(
                            fig, yaxis_title="Activities", yaxis_format="count",
                            coloraxis_colorbar=dict(title="Avg float"),
                        ),
                        use_container_width=True,
                    )

                with col2:
                    st.markdown("#### Critical Activities by Phase")
                    # More critical activities is worse, so this scale is the
                    # criticality one: success -> danger.
                    fig = px.bar(
                        df_phases,
                        x='Phase',
                        y='Critical',
                        text='Critical',
                        color='Critical',
                        color_continuous_scale=CHART_SCALE_CRITICALITY,
                        title="Critical Activities by WBS Phase"
                    )
                    fig.update_traces(textposition='outside')
                    st.plotly_chart(
                        apply_chart_theme(
                            fig, yaxis_title="Critical activities",
                            yaxis_format="count",
                            coloraxis_colorbar=dict(title="Critical"),
                        ),
                        use_container_width=True,
                    )

                # Detailed table
                st.markdown("#### Detailed Phase Statistics")
                st.dataframe(
                    df_phases,
                    use_container_width=True,
                    column_config={
                        "Phase": st.column_config.TextColumn("Phase"),
                        "Activities": st.column_config.NumberColumn("Activities", format=COLUMN_FORMAT["count"]),
                        "Percentage": st.column_config.NumberColumn("% of Total", format=COLUMN_FORMAT["pct"]),
                        "Avg Float": st.column_config.NumberColumn("Avg Float (days)", format=COLUMN_FORMAT["days"]),
                        "Critical": st.column_config.NumberColumn("Critical Count", format=COLUMN_FORMAT["count"]),
                        "Negative Float": st.column_config.NumberColumn("Behind Schedule", format=COLUMN_FORMAT["count"]),
                        "Health Score": st.column_config.NumberColumn("Health Score", format=COLUMN_FORMAT["score"]),
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
                        st.metric(area_data['Area'], fmt_score(score))
                        st.markdown(
                            status_badge(rating, _rating_variant(rating)),
                            unsafe_allow_html=True,
                        )

                section_divider()

                # Heatmap-style visualization
                st.markdown("#### Area Health Overview")

                # Sort by % Critical (descending) to show problem areas first
                df_areas_sorted = df_areas.sort_values('% Critical', ascending=False)

                # High % critical is bad, hence the criticality scale.
                fig = px.bar(
                    df_areas_sorted,
                    x='Area',
                    y='Activities',
                    color='% Critical',
                    color_continuous_scale=CHART_SCALE_CRITICALITY,
                    title="WBS Areas - Colored by % Critical Activities",
                    hover_data=['Avg Float', 'Critical', '% Critical']
                )
                st.plotly_chart(
                    apply_chart_theme(
                        fig, yaxis_title="Activities", yaxis_format="count",
                        coloraxis_colorbar=dict(title="% critical"),
                    ),
                    use_container_width=True,
                )

                # Detailed table
                st.markdown("#### Detailed Area Statistics")
                st.dataframe(
                    df_areas_sorted,
                    use_container_width=True,
                    column_config={
                        "Area": st.column_config.TextColumn("Area"),
                        "Activities": st.column_config.NumberColumn("Activities", format=COLUMN_FORMAT["count"]),
                        "Percentage": st.column_config.NumberColumn("% of Total", format=COLUMN_FORMAT["pct"]),
                        "Avg Float": st.column_config.NumberColumn("Avg Float (days)", format=COLUMN_FORMAT["days"]),
                        "Critical": st.column_config.NumberColumn("Critical Count", format=COLUMN_FORMAT["count"]),
                        "% Critical": st.column_config.NumberColumn("% Critical", format=COLUMN_FORMAT["pct"]),
                        "Health Score": st.column_config.NumberColumn("Health Score", format=COLUMN_FORMAT["score"]),
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
                        st.markdown(
                            f"- **{area['Area']}**: {fmt_pct(area['% Critical'])} "
                            f"critical ({fmt_count(area['Critical'])}/"
                            f"{fmt_count(area['Activities'])} activities)"
                        )

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
        report_error(
            "WBS Analysis could not be displayed for this schedule. "
            "Try re-uploading the schedule; if the problem persists, quote the "
            "reference below to your administrator.",
            e,
            logger_name="dashboard",
        )

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
            st.metric("High Priority", fmt_count(rec_summary['high']))
        with col2:
            st.metric("Medium Priority", fmt_count(rec_summary['medium']))
        with col3:
            st.metric("Low Priority", fmt_count(rec_summary['low']))

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

    if not activities:
        display_no_data_message("No activity data available")
    else:
        df = activities_df

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
