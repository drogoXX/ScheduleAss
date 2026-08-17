"""Translate a Microsoft Project CSV export into the canonical schedule frame.

Microsoft Project and Primavera P6 describe the same network with different
vocabulary, and MS Project's CSV writer has two behaviours that will corrupt an
assessment if they are not handled explicitly:

1. **Relationship cells are hard-capped at 255 characters** and truncated with an
   ellipsis. In the reference export three `Successors` cells hit the cap, silently
   dropping 47 edges. Because the graph is bidirectional and the `Predecessors`
   column was complete, the canonical graph is built from predecessors and
   successors are *derived by inversion* rather than read from the file. Any
   truncation encountered is still reported.

2. **Summary rows are tasks.** Where P6 keeps the WBS as separate structure, MS
   Project interleaves rollup rows with real activities (107 of 764 in the
   reference export). Their duration and float are derived from their children, so
   including them corrupts every duration and float denominator. They are flagged
   and excluded.

Two further gaps are recorded rather than papered over: MS Project CSV carries no
activity status and no resource assignment, so any check depending on those must
report NOT_ASSESSABLE rather than assume a value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.core.ingest.formats import decode_bytes

# ---------------------------------------------------------------------------
# Vocabulary mapping
# ---------------------------------------------------------------------------

# MS Project constraint names -> the P6 names the analyser already categorises.
# The Hard/Flexible/Schedule-Driven split downstream depends on these exact strings.
CONSTRAINT_MAP: Dict[str, str] = {
    "as soon as possible": "As Soon As Possible",
    "as late as possible": "As Late As Possible",
    "must start on": "Must Start On",
    "must finish on": "Must Finish On",
    "start no earlier than": "Start On or After",
    "start no later than": "Start On or Before",
    "finish no earlier than": "Finish On or After",
    "finish no later than": "Finish On or Before",
}

# Duration/lag unit -> working days. MS Project "edays" are elapsed (calendar)
# days; converting them to working days needs a calendar we do not have from CSV,
# so they are passed through at face value and reported.
UNIT_TO_DAYS: Dict[str, float] = {
    "day": 1.0, "days": 1.0, "d": 1.0,
    "wk": 5.0, "wks": 5.0, "week": 5.0, "weeks": 5.0, "w": 5.0,
    "mon": 20.0, "mons": 20.0, "month": 20.0, "months": 20.0,
    "hr": 1.0 / 8.0, "hrs": 1.0 / 8.0, "hour": 1.0 / 8.0, "hours": 1.0 / 8.0, "h": 1.0 / 8.0,
    "eday": 1.0, "edays": 1.0,
    "yr": 260.0, "yrs": 260.0, "year": 260.0, "years": 260.0,
}

_DURATION_RE = re.compile(r"^\s*(-?[\d.,]+)\s*([A-Za-z]*)\??\s*$")
# "5FS+62 days", "49SS", "154", "12FF-3 days"
_REL_RE = re.compile(
    r"^\s*(\d+)\s*(FS|SS|FF|SF)?\s*(?:([+-])\s*([\d.,]+)\s*([A-Za-z]*))?\s*$",
    re.IGNORECASE,
)

DATE_FORMATS = ("%d.%m.%y", "%d.%m.%Y", "%d/%m/%y", "%d/%m/%Y",
                "%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d")


@dataclass
class MSProjectTranslation:
    """Result of translating an MS Project export."""

    frame: pd.DataFrame
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    summary_task_count: int = 0
    truncated_cells: int = 0
    recovered_edges: int = 0
    dropped_blank_rows: int = 0
    date_format: Optional[str] = None
    encoding: Optional[str] = None

    @property
    def ok(self) -> bool:
        return not self.errors


def _parse_quantity(value: object) -> Tuple[Optional[float], Optional[str]]:
    """Parse '827 days' -> (827.0, 'days'). Returns (None, None) if unparseable."""
    if value is None:
        return None, None
    text = str(value).strip()
    if not text or text.upper() in {"NA", "N/A", "NAN", "NONE"}:
        return None, None
    match = _DURATION_RE.match(text)
    if not match:
        return None, None
    number, unit = match.group(1), (match.group(2) or "").lower()
    # MS Project writes thousands separators in some locales; the decimal mark is
    # a period in every export dialect we handle.
    number = number.replace(",", "")
    try:
        amount = float(number)
    except ValueError:
        return None, None
    return amount, unit


def _to_days(value: object, unknown_units: set) -> Optional[float]:
    """Convert a duration/slack string to working days."""
    amount, unit = _parse_quantity(value)
    if amount is None:
        return None
    if not unit:
        return amount
    factor = UNIT_TO_DAYS.get(unit)
    if factor is None:
        unknown_units.add(unit)
        return amount
    return amount * factor


def _pick_date_format(series: pd.Series) -> Optional[str]:
    """Choose the date format that parses the most values.

    MS Project writes the operator's locale format, so this cannot be assumed.
    Ties are broken by the order in DATE_FORMATS, which puts day-first ahead of
    month-first - the reference export is DD.MM.YY and an ambiguous value like
    05.06.26 must not silently flip month and day between uploads.
    """
    sample = series.dropna().astype(str).str.strip()
    sample = sample[(sample != "") & (sample.str.upper() != "NA")]
    if sample.empty:
        return None
    best, best_hits = None, 0
    for fmt in DATE_FORMATS:
        hits = pd.to_datetime(sample, format=fmt, errors="coerce").notna().sum()
        if hits > best_hits:
            best, best_hits = fmt, hits
    # Require most values to parse before trusting a format.
    return best if best_hits >= 0.8 * len(sample) else None


def _parse_relationship_cell(
    cell: object,
    id_to_activity: Dict[str, str],
    unknown_units: set,
) -> Tuple[List[Dict], bool, int]:
    """Parse an MS Project relationship cell.

    Returns (relationships, was_truncated, unresolved_count). Relationship targets
    are remapped from the volatile row `ID` to the stable `Unique_ID`.
    """
    if cell is None:
        return [], False, 0
    text = str(cell).strip()
    if not text or text.lower() == "nan":
        return [], False, 0

    truncated = text.endswith("...")
    relationships: List[Dict] = []
    unresolved = 0

    for token in text.split(";"):
        token = token.strip()
        if not token:
            continue
        if token.endswith("..."):
            # The tail of a truncated cell; the edge is recovered by inversion.
            continue
        match = _REL_RE.match(token)
        if not match:
            unresolved += 1
            continue
        row_id, rel_type, sign, lag_amount, lag_unit = match.groups()
        activity = id_to_activity.get(row_id)
        if activity is None:
            unresolved += 1
            continue
        lag = 0.0
        if lag_amount:
            magnitude = _to_days(f"{lag_amount} {lag_unit or 'days'}", unknown_units) or 0.0
            lag = -magnitude if sign == "-" else magnitude
        relationships.append({
            "activity": activity,
            "type": (rel_type or "FS").upper(),
            "lag": int(lag) if float(lag).is_integer() else lag,
        })
    return relationships, truncated, unresolved


def _format_details(relationships: List[Dict]) -> str:
    """Render relationships in the 'ID: TYPE LAG' notation the parser consumes."""
    return ", ".join(
        f"{r['activity']}: {r['type']} {r['lag']}" if r["lag"] else f"{r['activity']}: {r['type']}"
        for r in relationships
    )


class MSProjectCsvReader:
    """Reads an MS Project CSV export and emits a canonical, P6-shaped frame."""

    REQUIRED_COLUMNS = ("ID", "Name")

    def read(self, content: bytes) -> MSProjectTranslation:
        import io

        try:
            text, encoding = decode_bytes(content)
        except UnicodeDecodeError as exc:
            return MSProjectTranslation(
                frame=pd.DataFrame(),
                errors=[f"Could not decode the file as text: {exc}"],
            )

        try:
            raw = pd.read_csv(io.StringIO(text), dtype=str)
        except Exception as exc:  # pragma: no cover - pandas raises many types
            return MSProjectTranslation(
                frame=pd.DataFrame(),
                errors=[f"Could not read the file as CSV: {exc}"],
            )

        raw.columns = [str(c).strip() for c in raw.columns]
        missing = [c for c in self.REQUIRED_COLUMNS if c not in raw.columns]
        if missing:
            return MSProjectTranslation(
                frame=pd.DataFrame(),
                errors=[f"Missing required MS Project columns: {', '.join(missing)}"],
            )

        result = MSProjectTranslation(frame=pd.DataFrame(), encoding=encoding)
        return self._translate(raw, result)

    # -- translation ------------------------------------------------------

    def _translate(self, raw: pd.DataFrame, result: MSProjectTranslation) -> MSProjectTranslation:
        raw = raw.copy()
        for col in raw.columns:
            raw[col] = raw[col].astype(str).str.strip().replace({"nan": ""})

        # MS Project emits placeholder rows carrying only ID/Unique_ID/WBS.
        blank = raw["Name"] == ""
        result.dropped_blank_rows = int(blank.sum())
        if result.dropped_blank_rows:
            result.warnings.append(
                f"Dropped {result.dropped_blank_rows} row(s) with no task name "
                "(empty placeholder rows in the export)."
            )
        raw = raw[~blank].reset_index(drop=True)

        if raw.empty:
            result.errors.append("The export contains no named tasks.")
            return result

        has_unique = "Unique_ID" in raw.columns and (raw["Unique_ID"] != "").all()
        # Prefer Unique_ID: it is stable across re-exports, whereas ID renumbers
        # when rows are inserted, which would break version-over-version comparison.
        activity_ids = raw["Unique_ID"] if has_unique else raw["ID"]
        if not has_unique:
            result.warnings.append(
                "No usable 'Unique_ID' column; falling back to row 'ID' as the activity "
                "identifier. IDs renumber when tasks are inserted, so comparison across "
                "schedule versions may mismatch."
            )
        if not activity_ids.is_unique:
            dupes = int(activity_ids.duplicated().sum())
            result.warnings.append(
                f"{dupes} duplicate activity identifier(s) found; relationships to "
                "those tasks may resolve to the wrong activity."
            )

        id_to_activity = dict(zip(raw["ID"], activity_ids))
        unknown_units: set = set()

        out = pd.DataFrame(index=raw.index)
        out["Activity ID"] = activity_ids.values
        out["Activity Name"] = raw["Name"].values

        # --- summary (rollup) rows -----------------------------------------
        is_summary = raw["Summary"].str.lower().eq("yes") if "Summary" in raw else pd.Series(False, index=raw.index)
        result.summary_task_count = int(is_summary.sum())
        out["is_summary_task"] = is_summary.values

        is_milestone = raw["Milestone"].str.lower().eq("yes") if "Milestone" in raw else pd.Series(False, index=raw.index)

        # Activity Type drives milestone and rollup exclusions downstream. The
        # analyser matches the substring "Milestone" case-insensitively.
        activity_type = np.where(
            is_summary, "WBS Summary",
            np.where(is_milestone, "Finish Milestone", "Task Dependent"),
        )
        out["Activity Type"] = activity_type

        # --- status ---------------------------------------------------------
        # MS Project CSV carries no status or % complete. Emitting "Completed" or
        # "Not Started" here would be a fabricated input of exactly the kind the
        # specification forbids, so the column is left explicitly unknown.
        out["Activity Status"] = "Unknown"
        result.warnings.append(
            "MS Project CSV carries no activity status or % complete. Checks that are "
            "scoped to incomplete activities will assess ALL activities instead, and "
            "checks requiring completion data cannot be assessed. Supply a data date "
            "so progress can be established, or export from P6 for a full assessment."
        )

        # --- dates ----------------------------------------------------------
        fmt = _pick_date_format(raw["Start_Date"]) if "Start_Date" in raw else None
        result.date_format = fmt
        if fmt:
            result.warnings.append(f"Interpreted dates using the format '{fmt}'.")
        else:
            result.warnings.append(
                "Could not determine a consistent date format; dates were parsed "
                "individually and may be unreliable."
            )
        for src, dst in (("Start_Date", "Start"), ("Finish_Date", "Finish")):
            if src in raw.columns:
                values = raw[src].replace({"NA": None, "": None})
                out[dst] = (
                    pd.to_datetime(values, format=fmt, errors="coerce")
                    if fmt else pd.to_datetime(values, errors="coerce", dayfirst=True)
                )
            else:
                out[dst] = pd.NaT

        # --- durations and float ---------------------------------------------
        def to_days_col(name: str) -> pd.Series:
            if name not in raw.columns:
                return pd.Series(np.nan, index=raw.index)
            return raw[name].map(lambda v: _to_days(v, unknown_units))

        out["At Completion Duration"] = to_days_col("Duration")
        out["Total Float"] = to_days_col("Total_Slack")
        out["Free Float"] = to_days_col("Free_Slack")
        if unknown_units:
            result.warnings.append(
                "Unrecognised duration unit(s) "
                f"{sorted(unknown_units)} were treated as days without conversion."
            )

        # --- constraints -------------------------------------------------------
        if "Constraint_Type" in raw.columns:
            lowered = raw["Constraint_Type"].str.lower()
            mapped = lowered.map(CONSTRAINT_MAP)
            unmapped = sorted({
                original for original, m in zip(raw["Constraint_Type"], mapped)
                if original and pd.isna(m)
            })
            if unmapped:
                result.warnings.append(
                    f"Unrecognised MS Project constraint type(s): {unmapped}. "
                    "They are recorded verbatim and will categorise as 'Other'."
                )
            out["Primary Constraint"] = mapped.fillna(raw["Constraint_Type"]).replace({"": None}).values
        else:
            out["Primary Constraint"] = None

        # --- relationships -----------------------------------------------------
        self._translate_relationships(raw, out, id_to_activity, unknown_units, result)

        # --- WBS ---------------------------------------------------------------
        # MS Project's WBS is already a dotted outline path, which the WBS parser
        # decomposes directly.
        out["WBS Code"] = raw["WBS"].replace({"": None}).values if "WBS" in raw.columns else None
        out["Duration Type"] = raw["Type"].values if "Type" in raw.columns else "Fixed Duration"

        if result.summary_task_count:
            result.warnings.append(
                f"{result.summary_task_count} summary (rollup) row(s) identified and marked as "
                "'WBS Summary'. Their dates, durations and float are derived from child tasks, "
                "so they are excluded from duration and float checks."
            )

        result.frame = out.reset_index(drop=True)
        return result

    def _translate_relationships(
        self,
        raw: pd.DataFrame,
        out: pd.DataFrame,
        id_to_activity: Dict[str, str],
        unknown_units: set,
        result: MSProjectTranslation,
    ) -> None:
        """Build the relationship graph, deriving successors by inversion.

        The `Successors` column is deliberately not trusted: MS Project caps these
        cells at 255 characters and truncates, which silently drops edges. The
        `Predecessors` column describes every edge exactly once, so inverting it
        yields a complete and self-consistent graph.
        """
        n = len(raw)
        pred_lists: List[List[Dict]] = [[] for _ in range(n)]
        truncated = 0
        unresolved_total = 0

        if "Predecessors" in raw.columns:
            for i, cell in enumerate(raw["Predecessors"]):
                rels, was_truncated, unresolved = _parse_relationship_cell(
                    cell, id_to_activity, unknown_units
                )
                pred_lists[i] = rels
                truncated += int(was_truncated)
                unresolved_total += unresolved
        else:
            result.warnings.append(
                "No 'Predecessors' column found; logic and relationship checks cannot be assessed."
            )

        # Count truncation in the successor column too, purely to report it.
        stated_truncated = 0
        if "Successors" in raw.columns:
            stated_truncated = int(raw["Successors"].str.endswith("...").sum())

        # Invert predecessors -> successors.
        activity_ids = list(out["Activity ID"])
        position = {aid: i for i, aid in enumerate(activity_ids)}
        succ_lists: List[List[Dict]] = [[] for _ in range(n)]
        for i, rels in enumerate(pred_lists):
            target = activity_ids[i]
            for rel in rels:
                src_index = position.get(rel["activity"])
                if src_index is None:
                    continue
                succ_lists[src_index].append({
                    "activity": target,
                    "type": rel["type"],
                    "lag": rel["lag"],
                })

        derived_edges = sum(len(s) for s in succ_lists)
        stated_edges = 0
        if "Successors" in raw.columns:
            for cell in raw["Successors"]:
                rels, _, _ = _parse_relationship_cell(cell, id_to_activity, unknown_units)
                stated_edges += len(rels)
        result.recovered_edges = max(0, derived_edges - stated_edges)
        result.truncated_cells = truncated + stated_truncated

        if result.truncated_cells:
            result.warnings.append(
                f"{result.truncated_cells} relationship cell(s) were truncated by MS Project's "
                "255-character export limit. Successors were rebuilt from the predecessor "
                f"column, recovering {result.recovered_edges} relationship(s) that the "
                "truncated cells omitted."
            )
        if truncated:
            result.warnings.append(
                f"{truncated} PREDECESSOR cell(s) were truncated. Unlike successors these "
                "cannot be recovered by inversion, so some logic may be missing. Re-export "
                "from MS Project using a format without the 255-character cap."
            )
        if unresolved_total:
            result.warnings.append(
                f"{unresolved_total} relationship reference(s) could not be resolved to a task "
                "and were skipped."
            )

        out["predecessor_list"] = pd.Series(pred_lists, index=out.index)
        out["successor_list"] = pd.Series(succ_lists, index=out.index)
        out["Predecessor Details"] = [_format_details(r) or None for r in pred_lists]
        out["Successor Details"] = [_format_details(r) or None for r in succ_lists]
