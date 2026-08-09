"""
Utility helper functions
"""

import html
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from src.config import settings
from src.logging_config import get_logger, new_error_reference

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
    color_map = {
        'Excellent': '#28a745',  # Green
        'Good': '#007bff',       # Blue
        'Fair': '#ffc107',       # Yellow
        'Poor': '#fd7e14',       # Orange
        'Critical': '#dc3545'    # Red
    }

    color = color_map.get(rating, '#6c757d')

    try:
        score_text = f"{float(score):.1f}"
    except (TypeError, ValueError):
        score_text = "N/A"

    st.markdown(
        f"""
        <div style="text-align: center; padding: 20px; background-color: {color};
                    border-radius: 10px; color: white;">
            <h1 style="margin: 0; font-size: 3em;">{esc(score_text)}</h1>
            <h3 style="margin: 0;">{esc(rating)}</h3>
            <p style="margin: 5px 0 0 0;">Schedule Health Score</p>
        </div>
        """,
        unsafe_allow_html=True
    )


def display_status_badge(status: str):
    """Display status badge with color"""
    color_map = {
        'pass': 'green',
        'warning': 'orange',
        'fail': 'red',
        'unknown': 'gray'
    }

    color = color_map.get(str(status).lower(), 'gray')

    return f'<span style="background-color: {color}; color: white; padding: 3px 10px; \
              border-radius: 5px; font-weight: bold;">{esc(str(status).upper())}</span>'


def format_large_number(num: int) -> str:
    """Format large numbers with commas"""
    return f"{num:,}"


def get_priority_color(priority: str) -> str:
    """
    Get colour for a priority level.

    Only ever returns a value from the fixed map, so the result is safe to
    interpolate into a style attribute.
    """
    color_map = {
        'high': '#dc3545',
        'critical': '#dc3545',
        'medium': '#ffc107',
        'low': '#28a745'
    }
    return color_map.get(str(priority).lower(), '#6c757d')


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
        <div style="border-left: 4px solid {priority_color}; padding: 10px;
                    margin: 10px 0; background-color: #f8f9fa; border-radius: 5px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h4 style="margin: 0; color: {priority_color};">{esc(issue.get('title'))}</h4>
                <span style="background-color: {priority_color}; color: white;
                             padding: 3px 10px; border-radius: 5px; font-size: 0.8em;">
                    {esc(severity.upper())}
                </span>
            </div>
            <p style="margin: 10px 0 5px 0; color: #495057;">{esc(issue.get('description'))}</p>
            <p style="margin: 5px 0; color: #6c757d; font-style: italic;">
                <strong>Recommendation:</strong> {esc(issue.get('recommendation'))}
            </p>
            <p style="margin: 5px 0 0 0; color: #6c757d; font-size: 0.9em;">
                Affected activities: {esc(issue.get('count', 0))}
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )


def display_recommendation_card(rec: Dict, index: int):
    """Display a recommendation as a card. Content is escaped (CSV-derived)."""
    priority = str(rec.get('priority', 'low'))
    priority_color = get_priority_color(priority)

    st.markdown(
        f"""
        <div style="border: 1px solid #dee2e6; padding: 15px; margin: 10px 0;
                    border-radius: 5px; background-color: white;">
            <div style="display: flex; justify-content: space-between; align-items: start;">
                <h4 style="margin: 0; color: #212529;">
                    {esc(index)}. {esc(rec.get('title'))}
                </h4>
                <span style="background-color: {priority_color}; color: white;
                             padding: 3px 10px; border-radius: 5px; font-size: 0.8em;">
                    {esc(priority.upper())}
                </span>
            </div>
            <p style="margin: 10px 0;"><strong>Category:</strong> {esc(rec.get('category'))}</p>
            <p style="margin: 5px 0;"><strong>Description:</strong> {esc(rec.get('description'))}</p>
            <p style="margin: 5px 0; color: #007bff;">
                <strong>Recommendation:</strong> {esc(rec.get('recommendation'))}
            </p>
            <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #dee2e6;">
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
