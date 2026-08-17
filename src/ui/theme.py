"""
Streamlit rendering layer of the design system.

Colour tokens, escaping and number formatting live in :mod:`src.ui.palette`,
which is deliberately Streamlit-free so the analysis and report layers can share
them. This module adds the parts that need Streamlit: the stylesheet, the
branded header, status badges and KPI cards.

Everything interpolated into markup here goes through :func:`esc`. These
renderers receive CSV-derived content (activity names, WBS labels), so escaping
is mandatory — see ``tests/test_ui_safety.py``.
"""

from typing import Any, Optional

import streamlit as st

from src.ui.palette import (  # noqa: F401  (re-exported for convenience)
    BODY_FONT_NAME,
    BODY_FONT_STACK,
    COLORS,
    COLUMN_FORMAT,
    MISSING,
    RATING_COLORS,
    SEVERITY_COLORS,
    STATUS_COLORS,
    esc,
    fmt_count,
    fmt_days,
    fmt_delta_count,
    fmt_delta_index,
    fmt_delta_pct,
    fmt_delta_score,
    fmt_index,
    fmt_pct,
    fmt_ratio,
    fmt_score,
    rating_color,
    status_color,
    threshold_status,
)

from src.ui.diagnostics import install_crash_logging, log_page_run
from src.ui.charts import (  # noqa: F401  (re-exported for convenience)
    CHART_SCALE_CRITICALITY,
    CHART_SCALE_DIVERGING,
    CHART_SEQUENCE,
    apply_chart_theme,
    register_chart_template,
)

#: Badge / accent variants understood by :func:`status_badge` and :func:`kpi_card`.
_VARIANTS = ("success", "warning", "danger", "info", "neutral")

_VARIANT_COLORS = {
    "success": COLORS["success"],
    "warning": COLORS["warning"],
    "danger": COLORS["danger"],
    "info": COLORS["info"],
    "neutral": COLORS["text_muted"],
}

_VARIANT_ICONS = {
    "success": "✓",
    "warning": "⚠",
    "danger": "✗",
    "info": "ℹ",
    "neutral": "•",
}


def _variant(name: Any) -> str:
    v = str(name).lower()
    return v if v in _VARIANTS else "neutral"


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
def inject_css(page: str = "") -> None:
    """
    Inject the app stylesheet.

    Call once per entry point, immediately after ``st.set_page_config(...)``.
    Streamlit runs every file under ``pages/`` as its own script, so each page
    must call this itself — there is no shared wrapper to hook.

    Because this is the one call every page already makes first, it is also
    where runtime diagnostics are installed (see :mod:`src.ui.diagnostics`):
    unhandled page exceptions and session churn are otherwise never recorded.
    Both are observe-only and cannot change what the user sees.
    """
    install_crash_logging()
    if page:
        log_page_run(page)

    st.markdown(
        f"""
        <style>
        html, body, [class*="st-"] {{
            font-family: {BODY_FONT_STACK};
        }}

        h1, h2, h3 {{
            color: {COLORS['primary']};
            font-weight: 700;
            letter-spacing: -0.01em;
        }}
        h4, h5 {{
            color: {COLORS['text']};
            font-weight: 600;
        }}

        /* Built-in st.metric cards */
        div[data-testid="stMetric"] {{
            background-color: {COLORS['surface']};
            border: 1px solid {COLORS['border']};
            border-left: 4px solid {COLORS['primary']};
            border-radius: 8px;
            padding: 12px 16px;
        }}
        div[data-testid="stMetricLabel"] p {{
            color: {COLORS['text_muted']};
            font-weight: 600;
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}
        div[data-testid="stMetricValue"] {{
            color: {COLORS['text']};
            font-weight: 700;
        }}

        /* Tabs */
        button[data-baseweb="tab"] {{
            font-weight: 600;
        }}
        button[data-baseweb="tab"][aria-selected="true"] {{
            color: {COLORS['primary']} !important;
        }}

        button[kind="secondary"] {{
            border-color: {COLORS['primary']} !important;
            color: {COLORS['primary']} !important;
        }}

        /* Status badges */
        .status-badge {{
            display: inline-block;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.03em;
            color: {COLORS['white']};
            white-space: nowrap;
        }}
        .status-success {{ background-color: {COLORS['success']}; }}
        .status-warning {{ background-color: {COLORS['warning']}; }}
        .status-danger  {{ background-color: {COLORS['danger']}; }}
        .status-info    {{ background-color: {COLORS['info']}; }}
        .status-neutral {{ background-color: {COLORS['text_muted']}; }}

        /* KPI card, for KPIs st.metric cannot express */
        .kpi-card {{
            padding: 12px 14px;
            border: 1px solid {COLORS['border']};
            border-left: 4px solid {COLORS['primary']};
            background-color: {COLORS['surface']};
            border-radius: 8px;
            height: 100%;
        }}
        .kpi-card .kpi-label {{
            margin: 0;
            font-size: 0.82rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}
        .kpi-card .kpi-value {{
            margin: 6px 0 2px 0;
            font-size: 1.9rem;
            font-weight: 700;
            color: {COLORS['text']};
            line-height: 1.1;
        }}
        .kpi-card .kpi-sub {{
            margin: 0;
            font-size: 0.85rem;
            color: {COLORS['text']};
        }}
        .kpi-card .kpi-target {{
            margin: 2px 0 0 0;
            font-size: 0.78rem;
            color: {COLORS['text_muted']};
        }}

        /* Health score hero card */
        .health-card {{
            text-align: center;
            padding: 20px;
            border-radius: 10px;
            color: {COLORS['white']};
        }}
        .health-card .health-value {{
            margin: 0;
            font-size: 3em;
            font-weight: 700;
            line-height: 1;
        }}
        .health-card .health-rating {{
            margin: 4px 0 0 0;
            font-size: 1.3em;
            font-weight: 600;
        }}
        .health-card .health-caption {{
            margin: 6px 0 0 0;
            font-size: 0.85rem;
            opacity: 0.9;
        }}

        /* Issue / recommendation cards */
        .issue-card {{
            padding: 12px 14px;
            margin: 10px 0;
            background-color: {COLORS['surface']};
            border: 1px solid {COLORS['border']};
            border-left: 4px solid {COLORS['primary']};
            border-radius: 8px;
        }}
        .rec-card {{
            padding: 14px 16px;
            margin: 10px 0;
            background-color: {COLORS['white']};
            border: 1px solid {COLORS['border']};
            border-radius: 8px;
        }}
        .card-head {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
        }}
        .card-title {{
            margin: 0;
            font-size: 1.02rem;
            font-weight: 700;
        }}
        .card-body {{
            margin: 8px 0 4px 0;
            color: {COLORS['text']};
        }}
        .card-muted {{
            margin: 4px 0;
            color: {COLORS['text_muted']};
            font-size: 0.9rem;
        }}
        .card-footer {{
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid {COLORS['border']};
            font-size: 0.9rem;
            color: {COLORS['text_muted']};
        }}

        .section-divider {{
            border: none;
            border-top: 2px solid {COLORS['primary']};
            margin: 1.2rem 0;
            opacity: 1;
        }}

        /* Page title + subtitle pair rendered by app_header() */
        h1 {{
            margin-bottom: 0;
            padding-bottom: 0;
        }}
        .app-subtitle {{
            color: {COLORS['text_muted']};
            margin-top: 2px;
            font-size: 1.02rem;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------
def status_badge(label: str, status: str = "neutral") -> str:
    """
    Return badge markup. ``status`` is one of
    ``success | warning | danger | info | neutral``.

    Returns a string so callers can embed it in a larger markdown block; render
    with ``st.markdown(..., unsafe_allow_html=True)``.
    """
    return f'<span class="status-badge status-{_variant(status)}">{esc(label)}</span>'


def app_header(title: str, subtitle: str = "", logo_path: Optional[str] = None) -> None:
    """Branded page header: optional logo, title, one-line context, accent rule."""
    if logo_path:
        col1, col2 = st.columns([1, 6])
        with col1:
            st.image(logo_path, width=120)
        with col2:
            _render_title(title, subtitle)
    else:
        _render_title(title, subtitle)
    section_divider()


def _render_title(title: str, subtitle: str) -> None:
    # st.title, not raw markup: it emits a real heading element that assistive
    # tech and Streamlit's AppTest harness can both see. The stylesheet above
    # colours h1, so this needs no inline styling.
    st.title(title)
    if subtitle:
        st.markdown(
            f'<p class="app-subtitle">{esc(subtitle)}</p>', unsafe_allow_html=True
        )


def section_divider() -> None:
    """Accent-coloured rule between logical sections."""
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)


def kpi_card(label: str, value: str, subtitle: str = "", target: str = "",
             status: str = "neutral") -> None:
    """
    Render a KPI card for cases ``st.metric`` cannot express — a status-coloured
    accent plus both a subtitle and a target line.

    ``status`` drives the left border, the label colour and the leading icon.
    """
    variant = _variant(status)
    accent = _VARIANT_COLORS[variant]
    icon = _VARIANT_ICONS[variant]

    sub_html = f'<p class="kpi-sub">{esc(subtitle)}</p>' if subtitle else ""
    target_html = f'<p class="kpi-target">{esc(target)}</p>' if target else ""

    st.markdown(
        f"""
        <div class="kpi-card" style="border-left-color: {accent};">
            <p class="kpi-label" style="color: {accent};">{icon} {esc(label)}</p>
            <p class="kpi-value">{esc(value)}</p>
            {sub_html}
            {target_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
