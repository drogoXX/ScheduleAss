"""
Utility helper functions
"""

import html
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from src.config import settings
from src.logging_config import get_logger, new_error_reference
from src.ui.theme import COLORS, SEVERITY_COLORS, rating_color, status_badge

logger = get_logger("ui")


def esc(value: Any, default: str = "") -> str:
    """
    Escape a value for interpolation into markup rendered with
    ``unsafe_allow_html=True``.

    Analysis content is derived from uploaded CSV files (activity names, WBS
    labels, resource names), so it is untrusted input. Without escaping, a
    crafted activity name could inject arbitrary HTML into another user's page.
    """
    if value is None:
        return html.escape(default)
    return html.escape(str(value))


def report_error(user_message: str, exc: BaseException | None = None,
                 *, logger_name: str = "ui") -> str:
    """
    Log an exception in full and show the user a safe message with a reference.

    Stack traces are only rendered in the UI outside production, so internal
    paths and library versions are not exposed to end users.
    """
    reference = new_error_reference()
    get_logger(logger_name).error(
        "[%s] %s", reference, user_message,
        exc_info=exc if exc is not None else False,
    )

    st.error(f"❌ {user_message}\n\nError reference: `{reference}`")

    if exc is not None and (settings.DEBUG or not settings.is_production):
        with st.expander("Technical details (non-production only)"):
            st.exception(exc)

    return reference


def display_metric_card(title: str, value: Any, delta: str = None, help_text: str = None):
    """Display a metric card"""
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.metric(label=title, value=value, delta=delta, help=help_text)


def display_health_score(score: float, rating: str):
    """Display health score with color coding"""
    color = rating_color(rating)

    try:
        score_text = f"{float(score):.1f}"
    except (TypeError, ValueError):
        score_text = "N/A"

    st.markdown(
        f"""
        <div class="health-card" style="background-color: {color};">
            <p class="health-value">{esc(score_text)}</p>
            <p class="health-rating">{esc(rating)}</p>
            <p class="health-caption">Schedule Health Score</p>
        </div>
        """,
        unsafe_allow_html=True
    )


#: Check-result vocabulary -> badge variant in src/ui/theme.py.
_STATUS_VARIANTS = {
    'pass': 'success',
    'good': 'success',
    'warning': 'warning',
    'fail': 'danger',
    'unknown': 'neutral',
}

#: Severity / priority vocabulary -> badge variant.
_SEVERITY_VARIANTS = {
    'critical': 'danger',
    'high': 'danger',
    'medium': 'warning',
    'low': 'success',
}


def display_status_badge(status: str):
    """Display status badge with color"""
    variant = _STATUS_VARIANTS.get(str(status).lower(), 'neutral')
    return status_badge(str(status).upper(), variant)


def format_large_number(num: int) -> str:
    """Format large numbers with commas"""
    return f"{num:,}"


def get_priority_color(priority: str) -> str:
    """
    Get colour for a priority level.

    Only ever returns a value from the fixed map, so the result is safe to
    interpolate into a style attribute.
    """
    return SEVERITY_COLORS.get(str(priority).lower(), COLORS['text_muted'])


def create_download_button(file_data: bytes, file_name: str, button_text: str, mime_type: str):
    """Create a styled download button"""
    st.download_button(
        label=button_text,
        data=file_data,
        file_name=file_name,
        mime=mime_type,
        use_container_width=True
    )


def display_issue_card(issue: Dict):
    """Display an issue as a card. All content is CSV-derived, so it is escaped."""
    severity = str(issue.get('severity', 'unknown'))
    priority_color = get_priority_color(severity)

    st.markdown(
        f"""
        <div class="issue-card" style="border-left-color: {priority_color};">
            <div class="card-head">
                <p class="card-title" style="color: {priority_color};">{esc(issue.get('title'))}</p>
                {status_badge(severity.upper(), _SEVERITY_VARIANTS.get(severity.lower(), 'neutral'))}
            </div>
            <p class="card-body">{esc(issue.get('description'))}</p>
            <p class="card-muted"><em><strong>Recommendation:</strong>
                {esc(issue.get('recommendation'))}</em></p>
            <p class="card-muted">Affected activities: {esc(issue.get('count', 0))}</p>
        </div>
        """,
        unsafe_allow_html=True
    )


def display_recommendation_card(rec: Dict, index: int):
    """Display a recommendation as a card. Content is escaped (CSV-derived)."""
    priority = str(rec.get('priority', 'low'))

    st.markdown(
        f"""
        <div class="rec-card">
            <div class="card-head">
                <p class="card-title" style="color: {COLORS['text']};">
                    {esc(index)}. {esc(rec.get('title'))}
                </p>
                {status_badge(priority.upper(), _SEVERITY_VARIANTS.get(priority.lower(), 'neutral'))}
            </div>
            <p class="card-body"><strong>Category:</strong> {esc(rec.get('category'))}</p>
            <p class="card-body"><strong>Description:</strong> {esc(rec.get('description'))}</p>
            <p class="card-body" style="color: {COLORS['primary']};">
                <strong>Recommendation:</strong> {esc(rec.get('recommendation'))}
            </p>
            <div class="card-footer">
                <span style="margin-right: 15px;"><strong>Impact:</strong> {esc(rec.get('impact'))}</span>
                <span><strong>Effort:</strong> {esc(rec.get('effort'))}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def init_session_state():
    """Initialize session state variables"""
    if 'current_schedule' not in st.session_state:
        st.session_state.current_schedule = None
    if 'current_analysis' not in st.session_state:
        st.session_state.current_analysis = None


def check_user_permission(required_role: str = 'admin') -> bool:
    """Check if current user has required permission"""
    if 'user' not in st.session_state or not st.session_state.user:
        return False

    user_role = st.session_state.user.get('role', 'viewer')

    if required_role == 'admin':
        return user_role == 'admin'
    else:
        return True  # Viewer or admin can access


def display_no_data_message(message: str = "No data available"):
    """Display a message when no data is available"""
    st.info(f"ℹ️ {message}")


def display_error_message(message: str):
    """Display an error message"""
    st.error(f"❌ {message}")


def display_success_message(message: str):
    """Display a success message"""
    st.success(f"✅ {message}")


def display_warning_message(message: str):
    """Display a warning message"""
    st.warning(f"⚠️ {message}")
