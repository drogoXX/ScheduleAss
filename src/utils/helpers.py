"""
Utility helper functions
"""

import streamlit as st
from typing import Dict, List, Any
import pandas as pd


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

    st.markdown(
        f"""
        <div style="text-align: center; padding: 20px; background-color: {color};
                    border-radius: 10px; color: white;">
            <h1 style="margin: 0; font-size: 3em;">{score:.1f}</h1>
            <h3 style="margin: 0;">{rating}</h3>
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

    color = color_map.get(status.lower(), 'gray')

    return f'<span style="background-color: {color}; color: white; padding: 3px 10px; \
              border-radius: 5px; font-weight: bold;">{status.upper()}</span>'


def format_large_number(num: int) -> str:
    """Format large numbers with commas"""
    return f"{num:,}"


def get_priority_color(priority: str) -> str:
    """Get color for priority level"""
    color_map = {
        'high': '#dc3545',
        'medium': '#ffc107',
        'low': '#28a745'
    }
    return color_map.get(priority.lower(), '#6c757d')


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
    """Display an issue as a card"""
    priority_color = get_priority_color(issue['severity'])

    st.markdown(
        f"""
        <div style="border-left: 4px solid {priority_color}; padding: 10px;
                    margin: 10px 0; background-color: #f8f9fa; border-radius: 5px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h4 style="margin: 0; color: {priority_color};">{issue['title']}</h4>
                <span style="background-color: {priority_color}; color: white;
                             padding: 3px 10px; border-radius: 5px; font-size: 0.8em;">
                    {issue['severity'].upper()}
                </span>
            </div>
            <p style="margin: 10px 0 5px 0; color: #495057;">{issue['description']}</p>
            <p style="margin: 5px 0; color: #6c757d; font-style: italic;">
                <strong>Recommendation:</strong> {issue['recommendation']}
            </p>
            <p style="margin: 5px 0 0 0; color: #6c757d; font-size: 0.9em;">
                Affected activities: {issue.get('count', 0)}
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )


def display_recommendation_card(rec: Dict, index: int):
    """Display a recommendation as a card"""
    priority_color = get_priority_color(rec['priority'])

    st.markdown(
        f"""
        <div style="border: 1px solid #dee2e6; padding: 15px; margin: 10px 0;
                    border-radius: 5px; background-color: white;">
            <div style="display: flex; justify-content: space-between; align-items: start;">
                <h4 style="margin: 0; color: #212529;">
                    {index}. {rec['title']}
                </h4>
                <span style="background-color: {priority_color}; color: white;
                             padding: 3px 10px; border-radius: 5px; font-size: 0.8em;">
                    {rec['priority'].upper()}
                </span>
            </div>
            <p style="margin: 10px 0;"><strong>Category:</strong> {rec['category']}</p>
            <p style="margin: 5px 0;"><strong>Description:</strong> {rec['description']}</p>
            <p style="margin: 5px 0; color: #007bff;">
                <strong>Recommendation:</strong> {rec['recommendation']}
            </p>
            <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #dee2e6;">
                <span style="margin-right: 15px;"><strong>Impact:</strong> {rec['impact']}</span>
                <span><strong>Effort:</strong> {rec['effort']}</span>
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
