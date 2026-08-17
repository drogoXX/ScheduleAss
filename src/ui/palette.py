"""
Palette, escaping and number formatting — the Streamlit-free half of the
design system.

This module deliberately has no Streamlit or Plotly import so it can be used
from the analysis layer (``src/analysis``) and the report generators
(``src/reports``) without dragging the web framework in. Rendering helpers that
do need Streamlit live in :mod:`src.ui.theme`.

The palette originates from ``tools/build_user_guide_docx.py``, which produced
the shipped User Guide. ``src/reports/docx_styles.py`` mirrors these values as
``RGBColor`` and ``.streamlit/config.toml`` mirrors the core four — edit them
together.
"""

import html
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
COLORS = {
    "primary": "#004B87",       # Deep corporate blue — headings, primary actions
    "primary_dark": "#003A6B",  # Hover/pressed states, chart series 8
    "primary_light": "#EEF3F8", # Tinted surface for callouts
    "accent": "#FFD100",        # Yellow accent rule / highlight
    "accent_dark": "#B38F00",   # Readable text-weight variant of the accent
    "success": "#2E7D32",
    "warning": "#ED6C02",
    "danger": "#C62828",
    "info": "#0277BD",
    "text": "#212121",
    "text_muted": "#757575",
    "surface": "#F5F5F5",
    "surface_alt": "#FAFAFA",
    "border": "#E0E0E0",
    "white": "#FFFFFF",
}

#: The one rating -> colour map. Replaces the three forks that previously lived
#: in helpers.py (Bootstrap), dcma_analyzer.py (Flat-UI) and docx_generator.py
#: (raw primaries).
RATING_COLORS = {
    "Excellent": COLORS["success"],
    "Good": COLORS["info"],
    "Fair": COLORS["accent_dark"],
    "Poor": COLORS["warning"],
    "Critical": COLORS["danger"],
}

#: Severity / priority -> colour. Same scale, different vocabulary.
SEVERITY_COLORS = {
    "critical": COLORS["danger"],
    "high": COLORS["danger"],
    "medium": COLORS["warning"],
    "low": COLORS["success"],
}

#: Pass/warn/fail vocabulary used by DCMA check tables and badges.
STATUS_COLORS = {
    "pass": COLORS["success"],
    "good": COLORS["success"],
    "warning": COLORS["warning"],
    "fail": COLORS["danger"],
    "bad": COLORS["danger"],
    "unknown": COLORS["text_muted"],
}

BODY_FONT_STACK = "Arial, Helvetica, sans-serif"
BODY_FONT_NAME = "Arial"


def esc(value: Any, default: str = "") -> str:
    """Escape a value for interpolation into ``unsafe_allow_html`` markup."""
    if value is None:
        return html.escape(default)
    return html.escape(str(value))


def rating_color(rating: str) -> str:
    """Colour for a health-score rating, falling back to muted grey."""
    return RATING_COLORS.get(str(rating).title(), COLORS["text_muted"])


def status_color(status: str) -> str:
    """Colour for a pass/warning/fail style status token."""
    return STATUS_COLORS.get(str(status).lower(), COLORS["text_muted"])


# ---------------------------------------------------------------------------
# Number formatting
# ---------------------------------------------------------------------------
# One set of formatters so the same quantity never renders two ways. Each
# tolerates None/non-numeric input and degrades to an en dash rather than
# raising inside a render path.
MISSING = "—"


def _num(value: Any) -> Optional[float]:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt_count(value: Any) -> str:
    """Integer count with thousands separators: ``1,284``."""
    n = _num(value)
    return MISSING if n is None else f"{int(round(n)):,}"


def fmt_days(value: Any, *, unit: bool = True) -> str:
    """Duration in days: ``1,284.5 days``."""
    n = _num(value)
    if n is None:
        return MISSING
    return f"{n:,.1f} days" if unit else f"{n:,.1f}"


def fmt_pct(value: Any) -> str:
    """Percentage, one decimal: ``18.3%``."""
    n = _num(value)
    return MISSING if n is None else f"{n:,.1f}%"


def fmt_score(value: Any) -> str:
    """Health score out of 100, one decimal: ``72.4/100``."""
    n = _num(value)
    return MISSING if n is None else f"{n:,.1f}/100"


def fmt_index(value: Any) -> str:
    """CPLI / BEI style index, three decimals: ``0.947``."""
    n = _num(value)
    return MISSING if n is None else f"{n:.3f}"


def fmt_ratio(value: Any) -> str:
    """Unitless ratio, two decimals: ``1.24``."""
    n = _num(value)
    return MISSING if n is None else f"{n:.2f}"


def fmt_delta_count(value: Any) -> str:
    """Signed integer delta: ``+12`` / ``-3``."""
    n = _num(value)
    return MISSING if n is None else f"{int(round(n)):+,}"


def fmt_delta_score(value: Any) -> str:
    """Signed one-decimal delta: ``+4.2``."""
    n = _num(value)
    return MISSING if n is None else f"{n:+,.1f}"


def fmt_delta_pct(value: Any) -> str:
    """Signed percentage delta: ``+4.2%``."""
    n = _num(value)
    return MISSING if n is None else f"{n:+,.1f}%"


def fmt_delta_index(value: Any) -> str:
    """Signed three-decimal delta: ``+0.031``."""
    n = _num(value)
    return MISSING if n is None else f"{n:+.3f}"


#: Column formats for ``st.dataframe(column_config=...)``. Streamlit uses printf
#: style here, not Python format specs.
COLUMN_FORMAT = {
    "count": "%d",
    "days": "%.1f",
    "pct": "%.1f%%",
    "score": "%.1f",
    "index": "%.3f",
    "ratio": "%.2f",
}


def threshold_status(value: Any, target: Any, *, lower_is_better: bool = True,
                     tolerance: float = 0.1) -> str:
    """
    Classify a value against a target as ``success | warning | danger``.

    Presentation only — the pass/fail rules that drive scoring live in
    ``src/analysis``. This just picks a colour for a number already computed.
    Within ``tolerance`` (a fraction of the target) on the wrong side reads as
    ``warning`` rather than a hard fail.
    """
    v, t = _num(value), _num(target)
    if v is None or t is None:
        return "neutral"
    margin = abs(t) * tolerance
    if lower_is_better:
        if v <= t:
            return "success"
        return "warning" if v <= t + margin else "danger"
    if v >= t:
        return "success"
    return "warning" if v >= t - margin else "danger"
