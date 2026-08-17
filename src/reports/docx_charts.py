"""
Chart images for the DOCX report.

Every figure here is built with :func:`src.ui.charts.apply_chart_theme` — the
same template, colour sequence and tick formats the on-screen charts use — so a
chart in the report cannot drift from its counterpart in the app.

Rendering to PNG needs ``kaleido``. If it is missing or fails (it shells out to
a bundled Chromium, which some locked-down environments block), every function
here returns ``None`` and the report is generated without that figure rather
than failing outright.
"""

import io
from typing import Dict, List, Optional, Tuple

import plotly.graph_objects as go

from src.logging_config import get_logger
from src.ui.charts import (
    CHART_SCALE_DIVERGING,
    CHART_SEQUENCE,
    apply_chart_theme,
)
from src.ui.palette import COLORS

logger = get_logger("reports")

# Rendered at 2x for a crisp result in print; the display width is set when the
# picture is placed, so the larger pixel size costs only file size.
_EXPORT_WIDTH = 1000
_EXPORT_HEIGHT = 420
_EXPORT_SCALE = 2


def _to_png(fig: go.Figure, *, height: int = _EXPORT_HEIGHT) -> Optional[io.BytesIO]:
    """Render a figure to a PNG stream, or None if export is unavailable."""
    try:
        buffer = io.BytesIO()
        fig.write_image(
            buffer, format="png",
            width=_EXPORT_WIDTH, height=height, scale=_EXPORT_SCALE,
        )
        buffer.seek(0)
        return buffer
    except Exception as exc:  # noqa: BLE001 - any failure means "no chart"
        logger.warning("Chart export unavailable, omitting figure: %s", exc)
        return None


def dcma_compliance_chart(dcma_14: Dict) -> Optional[io.BytesIO]:
    """Pass / fail / n-a / manual counts across the DCMA 14-point assessment."""
    counts = [
        ("Pass", dcma_14.get("overall_pass_count", 0), COLORS["success"]),
        ("Fail", dcma_14.get("overall_fail_count", 0), COLORS["danger"]),
        ("N/A", dcma_14.get("overall_na_count", 0), COLORS["text_muted"]),
        ("Manual", dcma_14.get("overall_manual_count", 0), COLORS["info"]),
    ]
    if not any(value for _, value, _ in counts):
        return None

    labels = [label for label, _, _ in counts]
    values = [value for _, value, _ in counts]
    colors = [color for _, _, color in counts]

    fig = go.Figure(go.Bar(
        x=labels, y=values, marker_color=colors,
        text=[f"{v:,}" for v in values], textposition="outside",
    ))
    apply_chart_theme(
        fig, showlegend=False,
        xaxis_title="Assessment result", yaxis_title="Checks",
        yaxis_format="count",
    )
    return _to_png(fig, height=360)


def issues_by_severity_chart(issues: List[Dict]) -> Optional[io.BytesIO]:
    """Issue counts grouped by severity."""
    if not issues:
        return None

    order = [("High", "high", COLORS["danger"]),
             ("Medium", "medium", COLORS["warning"]),
             ("Low", "low", COLORS["success"])]
    labels, values, colors = [], [], []
    for label, key, color in order:
        count = len([i for i in issues if str(i.get("severity", "")).lower() == key])
        labels.append(label)
        values.append(count)
        colors.append(color)

    if not any(values):
        return None

    fig = go.Figure(go.Bar(
        x=labels, y=values, marker_color=colors,
        text=[f"{v:,}" for v in values], textposition="outside",
    ))
    apply_chart_theme(
        fig, showlegend=False,
        xaxis_title="Severity", yaxis_title="Issues",
        yaxis_format="count",
    )
    return _to_png(fig, height=360)


def wbs_health_chart(level1: Dict, *, max_phases: int = 12) -> Optional[io.BytesIO]:
    """
    Health score by WBS phase.

    Capped at ``max_phases`` by activity count so a deep WBS does not produce an
    unreadable strip of bars; the caller states the cap in the caption.
    """
    if not level1:
        return None

    phases: List[Tuple[str, float, int]] = []
    for wbs_code, stats in level1.items():
        health = stats.get("health_score", {}) or {}
        phases.append((
            f"Phase {wbs_code}",
            float(health.get("score", 0) or 0),
            int(stats.get("activity_count", 0) or 0),
        ))

    if not phases:
        return None

    phases.sort(key=lambda item: item[2], reverse=True)
    phases = phases[:max_phases]
    phases.sort(key=lambda item: item[1])  # Worst score first, left to right

    fig = go.Figure(go.Bar(
        x=[name for name, _, _ in phases],
        y=[score for _, score, _ in phases],
        marker=dict(
            color=[score for _, score, _ in phases],
            colorscale=CHART_SCALE_DIVERGING,
            cmin=0, cmax=100,
            colorbar=dict(title="Health"),
        ),
        text=[f"{score:.1f}" for _, score, _ in phases],
        textposition="outside",
    ))
    apply_chart_theme(
        fig, showlegend=False,
        xaxis_title="WBS phase", yaxis_title="Health score",
        yaxis_format="score", yaxis_range=[0, 105],
    )
    return _to_png(fig, height=400)


def phase_count_used(level1: Dict, *, max_phases: int = 12) -> Tuple[int, int]:
    """(shown, total) phase counts, so a caption can state what was capped."""
    total = len(level1 or {})
    return min(total, max_phases), total


__all__ = [
    "dcma_compliance_chart",
    "issues_by_severity_chart",
    "wbs_health_chart",
    "phase_count_used",
    "CHART_SEQUENCE",
]
