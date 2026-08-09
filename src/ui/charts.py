"""
Plotly chart chrome.

One template and one colour sequence for every chart in the app, so charts read
as a single system rather than as sixteen independent defaults. The same
functions are used when rendering charts into the DOCX report
(``src/reports/docx_charts.py``), which is what stops the report from diverging
from the screen.

No Streamlit import here — the report generators use this module headlessly.
"""

from typing import Any, Optional

import plotly.graph_objects as go
import plotly.io as pio

from src.ui.palette import BODY_FONT_STACK, COLORS

TEMPLATE_NAME = "sqa"

#: Fixed categorical order. Replaces the qualitative Set3/Set2/Pastel sequences
#: and the ad-hoc lightblue/darkblue pairs that were previously in use.
#:
#: The two blues lead deliberately. Most categorical charts here compare exactly
#: two series (baseline vs current), and a dark/mid blue pair separates by
#: lightness as well as hue, so it survives greyscale printing and the common
#: colour-vision deficiencies. The yellow accent is third: it carries the brand
#: but is too low-contrast on white to be a large fill for a primary series.
CHART_SEQUENCE = [
    COLORS["primary"],
    COLORS["info"],
    COLORS["accent"],
    COLORS["success"],
    COLORS["warning"],
    COLORS["danger"],
    COLORS["text_muted"],
    COLORS["primary_dark"],
]

#: Bad -> good. Use where a high value is desirable (health score, float).
CHART_SCALE_DIVERGING = [
    [0.0, COLORS["danger"]],
    [0.5, COLORS["accent"]],
    [1.0, COLORS["success"]],
]

#: Good -> bad. Use where a high value is undesirable (% critical, issue count).
CHART_SCALE_CRITICALITY = [
    [0.0, COLORS["success"]],
    [0.5, COLORS["accent"]],
    [1.0, COLORS["danger"]],
]

#: Float-bucket colours, worst to best. Shared by the in-app histogram and the
#: report so the same bucket is never two different colours.
FLOAT_BUCKET_COLORS = [
    COLORS["danger"],    # Negative
    COLORS["warning"],   # Critical (0)
    COLORS["accent"],    # Near-critical
    COLORS["info"],      # Low risk
    COLORS["success"],   # Comfortable
]

DEFAULT_HEIGHT = 400

# Axis tick formats (d3-format). Applied via apply_chart_theme(xaxis_format=...).
TICK_FORMAT = {
    "count": ",d",
    "days": ",.1f",
    "pct": ".1f",
    "score": ".0f",
    "index": ".3f",
}


def register_chart_template() -> None:
    """
    Register and activate the shared Plotly template.

    Idempotent, so it is safe to call from every page on every rerun.
    """
    if TEMPLATE_NAME in pio.templates:
        pio.templates.default = TEMPLATE_NAME
        return

    template = go.layout.Template()
    template.layout = go.Layout(
        font=dict(family=BODY_FONT_STACK, size=12, color=COLORS["text"]),
        title=dict(
            font=dict(family=BODY_FONT_STACK, size=15, color=COLORS["primary"]),
            x=0,
            xanchor="left",
        ),
        colorway=CHART_SEQUENCE,
        plot_bgcolor=COLORS["white"],
        paper_bgcolor=COLORS["white"],
        height=DEFAULT_HEIGHT,
        margin=dict(t=48, r=16, b=48, l=56),
        hoverlabel=dict(
            font=dict(family=BODY_FONT_STACK, size=12),
            bgcolor=COLORS["white"],
            bordercolor=COLORS["border"],
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.22,
            xanchor="left",
            x=0,
            title=dict(text=""),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(
            showgrid=False,                      # vertical grid is noise
            showline=True,
            linecolor=COLORS["border"],
            ticks="outside",
            tickcolor=COLORS["border"],
            separatethousands=True,
            title=dict(font=dict(size=12, color=COLORS["text_muted"])),
            automargin=True,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=COLORS["border"],
            gridwidth=1,
            zeroline=True,
            zerolinecolor=COLORS["border"],
            showline=False,
            separatethousands=True,
            title=dict(font=dict(size=12, color=COLORS["text_muted"])),
            automargin=True,
        ),
        colorscale=dict(sequential=CHART_SCALE_DIVERGING),
    )
    pio.templates[TEMPLATE_NAME] = template
    pio.templates.default = TEMPLATE_NAME


def apply_chart_theme(fig: go.Figure, *, height: Optional[int] = None,
                      showlegend: Optional[bool] = None,
                      xaxis_format: Optional[str] = None,
                      yaxis_format: Optional[str] = None,
                      xaxis_title: Optional[str] = None,
                      yaxis_title: Optional[str] = None,
                      **layout: Any) -> go.Figure:
    """
    Apply the shared chrome to a figure and return it.

    ``xaxis_format`` / ``yaxis_format`` accept either a :data:`TICK_FORMAT` key
    (``"count"``, ``"days"``, ``"pct"``, ``"score"``, ``"index"``) or a raw
    d3-format string. Percent axes get a ``%`` suffix rather than d3's ``%``
    type, because the underlying values are already scaled 0-100.
    """
    register_chart_template()

    updates: dict = {"template": TEMPLATE_NAME}
    if height is not None:
        updates["height"] = height
    if showlegend is not None:
        updates["showlegend"] = showlegend
    updates.update(layout)
    fig.update_layout(**updates)

    if xaxis_title is not None:
        fig.update_xaxes(title_text=xaxis_title)
    if yaxis_title is not None:
        fig.update_yaxes(title_text=yaxis_title)

    if xaxis_format:
        fig.update_xaxes(**_axis_format(xaxis_format))
    if yaxis_format:
        fig.update_yaxes(**_axis_format(yaxis_format))

    return fig


def _axis_format(spec: str) -> dict:
    if spec == "pct":
        return {"tickformat": TICK_FORMAT["pct"], "ticksuffix": "%"}
    return {"tickformat": TICK_FORMAT.get(spec, spec)}
