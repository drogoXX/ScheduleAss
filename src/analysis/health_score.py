"""
Schedule health score.

The score is a weighted average of DCMA 14-Point checks. Each component is
measured as a percentage of the schedule, scored against the published DCMA
threshold, and combined using the weights in COMPONENTS below.

Design constraints, each of which the previous implementation violated:

1. **Proportional.** Component scores decline linearly from the DCMA threshold
   to a "zero" bound, so a schedule with 15 leads scores worse than one with 3.
   The previous version capped each deduction at a fixed number of points,
   which was reached after 3 leads or 5 activities with missing logic - beyond
   that, arbitrarily worse schedules scored identically.

2. **Correctly ordered.** Logic completeness (DCMA #1) carries the largest
   weight, because every other network metric depends on it. Previously leads
   were penalised more heavily (-30) than a total absence of logic (-25), so a
   schedule with no relationships at all scored *better* than a well-linked one
   with three leads.

3. **Honest about missing data.** A check whose input is absent is marked "n/a"
   and excluded, with the remaining weights renormalised - it does not silently
   score as a pass. Where the missing data means the schedule cannot be
   assessed at all, a documented cap applies (see GATES).

4. **Explainable.** Every component reports its measured value, threshold,
   weight and resulting score, so the number can be defended line by line.

Thresholds follow the DCMA 14-Point Assessment. The weights are this
application's own judgement of relative severity - DCMA defines pass/fail
criteria, not a composite score - and are stated here so they can be reviewed
and adjusted deliberately.
"""

from typing import Any, Dict, List, Optional

# Rating bands, unchanged from previous releases so existing reports remain
# comparable in vocabulary.
RATING_BANDS = [
    (90, "Excellent", "green"),
    (75, "Good", "blue"),
    (60, "Fair", "yellow"),
    (40, "Poor", "orange"),
    (0, "Critical", "red"),
]


class Component:
    """
    One scored check.

    ``target``  - value at or better than which the component scores 100.
    ``zero_at`` - value at or beyond which it scores 0.
    Scores in between interpolate linearly.
    """

    def __init__(self, key: str, label: str, dcma: Optional[int], weight: float,
                 target: float, zero_at: float, higher_is_better: bool = False,
                 unit: str = "%", critical: bool = False):
        self.key = key
        self.label = label
        self.dcma = dcma
        self.weight = weight
        self.target = target
        self.zero_at = zero_at
        self.higher_is_better = higher_is_better
        self.unit = unit
        # Foundational checks: DCMA either permits none of these at all, or
        # the check underpins the validity of the network. Failing one outright
        # limits the overall rating regardless of how well everything else
        # scores - see CEILINGS.
        self.critical = critical

    def score(self, value: float) -> float:
        """Score a measured value on a 0-100 scale."""
        if self.higher_is_better:
            if value >= self.target:
                return 100.0
            if value <= self.zero_at:
                return 0.0
            span = self.target - self.zero_at
            return 100.0 * (value - self.zero_at) / span

        if value <= self.target:
            return 100.0
        if value >= self.zero_at:
            return 0.0
        span = self.zero_at - self.target
        return 100.0 * (1 - (value - self.target) / span)

    def describe_target(self) -> str:
        comparator = "≥" if self.higher_is_better else "≤"
        if self.unit == "%":
            return f"{comparator}{self.target:g}%"
        return f"{comparator}{self.target:g}"


# Weights sum to 100. Logic completeness dominates by design.
COMPONENTS: List[Component] = [
    Component("missing_logic", "Logic completeness", 1, 22, target=5, zero_at=30,
              critical=True),
    Component("negative_float", "Negative float", 7, 12, target=0, zero_at=20,
              critical=True),
    Component("leads", "Leads (negative lags)", 2, 10, target=0, zero_at=20,
              critical=True),
    Component("hard_constraints", "Hard constraints", 5, 9, target=5, zero_at=40),
    Component("lags", "Lags (positive)", 3, 7, target=5, zero_at=40),
    Component("high_float", "High float (>44d)", 6, 7, target=5, zero_at=50),
    Component("long_durations", "Long durations (>44d)", 8, 7, target=5, zero_at=50),
    Component("relationship_types", "Non-FS relationships", 4, 6, target=10,
              zero_at=50),
    Component("invalid_dates", "Invalid dates", 9, 6, target=0, zero_at=10,
              critical=True),
    Component("missing_resources", "Unresourced activities", 10, 4, target=0,
              zero_at=50),
    Component("cpli", "CPLI", 13, 5, target=0.95, zero_at=0.80,
              higher_is_better=True, unit=""),
    Component("bei", "BEI", 14, 5, target=0.95, zero_at=0.80,
              higher_is_better=True, unit=""),
]

# Caps applied when the schedule cannot be meaningfully assessed. Without these
# a weighted average is misleading: the checks that would have failed are the
# very ones with no data to evaluate.
GATES = {
    "no_relationships": (
        25.0,
        "No relationship data: the schedule network cannot be assessed.",
    ),
    "logic_unusable": (
        40.0,
        "More than half of all activities are missing predecessor or successor "
        "logic; the network is not a usable critical path model.",
    ),
}

# A weighted average alone lets a total failure on a critical check cost
# only that check's weight, so a schedule with half its relationships as leads
# could still average out to "Excellent". DCMA assessments are reported per
# point, and a schedule failing such a check outright is not a
# high-quality schedule whatever else it does well.
#
# The rule: **each critical DCMA check that fails outright costs one rating
# band.** Each ceiling below is the top of the band one step down.
CEILINGS = [
    (1, 89.0, "cannot be rated Excellent"),
    (2, 74.0, "cannot be rated above Fair"),
    (3, 59.0, "cannot be rated above Poor"),
]

# A critical check is treated as failed outright below this score.
CRITICAL_FAIL_BELOW = 50.0

# One open start and one open finish are expected in any valid network and are
# excluded from the missing-logic measurement.
EXPECTED_OPEN_ENDS = 2


def _percentage(part: Optional[float], whole: Optional[float]) -> Optional[float]:
    """Percentage, or None when the denominator is unusable."""
    if part is None or not whole:
        return None
    try:
        return 100.0 * float(part) / float(whole)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def measure(dcma_metrics: Dict[str, Any], total_activities: int,
            cpli_value: Optional[float] = None,
            bei_value: Optional[float] = None) -> Dict[str, Optional[float]]:
    """
    Reduce the analyzer's metrics to one measured value per component.

    Returns None for any component whose input is unavailable, which marks it
    "n/a" rather than passing it by default.
    """
    def block(name: str) -> Dict[str, Any]:
        value = dcma_metrics.get(name)
        return value if isinstance(value, dict) else {}

    total_relationships = block("positive_lags").get("total_relationships") or 0

    measured: Dict[str, Optional[float]] = {}

    # Every valid network has exactly one open start and one open finish - the
    # project's own beginning and end. Counting those as defects penalises
    # correctly-built schedules, and on small schedules it dominates: a clean
    # three-activity chain would otherwise measure 67% "missing logic".
    missing_logic_count = block("missing_logic").get("count")
    if missing_logic_count is not None:
        missing_logic_count = max(0, missing_logic_count - EXPECTED_OPEN_ENDS)
    measured["missing_logic"] = _percentage(missing_logic_count, total_activities)

    measured["negative_float"] = (
        block("dcma_negative_float").get("percentage")
        if "dcma_negative_float" in dcma_metrics else None)

    measured["leads"] = _percentage(
        block("negative_lags").get("count"), total_relationships)

    measured["hard_constraints"] = (
        block("hard_constraints").get("percentage")
        if "hard_constraints" in dcma_metrics else None)

    measured["lags"] = (
        block("positive_lags").get("percentage")
        if total_relationships else None)

    measured["high_float"] = (
        block("dcma_high_float").get("percentage")
        if "dcma_high_float" in dcma_metrics else None)

    measured["long_durations"] = (
        block("dcma_long_durations").get("percentage")
        if "dcma_long_durations" in dcma_metrics else None)

    percentages = block("relationship_types").get("percentages") or {}
    if total_relationships and percentages:
        finish_to_start = float(percentages.get("FS", 0) or 0)
        measured["relationship_types"] = max(0.0, 100.0 - finish_to_start)
    else:
        measured["relationship_types"] = None

    measured["invalid_dates"] = _percentage(
        block("dcma_invalid_dates").get("count"), total_activities)

    measured["missing_resources"] = (
        block("dcma_missing_resources").get("percentage")
        if "dcma_missing_resources" in dcma_metrics else None)

    # CPLI/BEI of exactly 0 mean "could not be calculated" upstream, not a real
    # index value, so they are treated as unavailable.
    measured["cpli"] = cpli_value if cpli_value else None
    measured["bei"] = bei_value if bei_value else None

    return measured


def calculate(dcma_metrics: Dict[str, Any], total_activities: int,
              cpli_value: Optional[float] = None,
              bei_value: Optional[float] = None) -> Dict[str, Any]:
    """
    Calculate the overall schedule health score.

    Returns a dict with the keys existing consumers rely on (``score``,
    ``rating``, ``color``, ``deductions``, ``description``) plus ``components``,
    the full per-check breakdown, and ``caps`` describing any gate applied.
    """
    measured = measure(dcma_metrics, total_activities, cpli_value, bei_value)

    components: List[Dict[str, Any]] = []
    weighted_total = 0.0
    applicable_weight = 0.0
    failed_critical: List[str] = []

    for component in COMPONENTS:
        value = measured.get(component.key)
        entry: Dict[str, Any] = {
            "key": component.key,
            "label": component.label,
            "dcma_point": component.dcma,
            "weight": component.weight,
            "target": component.describe_target(),
            "unit": component.unit,
        }

        if value is None:
            entry.update({"value": None, "score": None, "status": "n/a"})
        else:
            value = float(value)
            component_score = component.score(value)
            entry.update({
                "value": round(value, 2),
                "score": round(component_score, 1),
                "status": "pass" if component_score >= 100 else (
                    "warning" if component_score >= 50 else "fail"),
            })
            weighted_total += component_score * component.weight
            applicable_weight += component.weight

            if (component.critical
                    and component_score < CRITICAL_FAIL_BELOW):
                failed_critical.append(component.label)

        components.append(entry)

    if applicable_weight > 0:
        score = weighted_total / applicable_weight
    else:
        # Nothing could be measured at all.
        score = 0.0

    # ---- Data-sufficiency gates -------------------------------------
    caps: List[str] = []
    total_relationships = 0
    positive = dcma_metrics.get("positive_lags")
    if isinstance(positive, dict):
        total_relationships = positive.get("total_relationships") or 0

    if total_activities and not total_relationships:
        cap, reason = GATES["no_relationships"]
        if score > cap:
            score = cap
        caps.append(reason)

    missing_logic_pct = measured.get("missing_logic")
    if missing_logic_pct is not None and missing_logic_pct > 50:
        cap, reason = GATES["logic_unusable"]
        if score > cap:
            score = cap
        caps.append(reason)

    # ---- Zero-tolerance ceilings ------------------------------------
    # Only the strictest applicable ceiling is reported, so the explanation
    # names one reason rather than stacking near-duplicates.
    applicable = [
        (ceiling, phrasing) for minimum, ceiling, phrasing in CEILINGS
        if len(failed_critical) >= minimum
    ]
    if applicable:
        ceiling, phrasing = min(applicable, key=lambda item: item[0])
        if score > ceiling:
            score = ceiling
            caps.append(
                f"Schedule {phrasing}: critical DCMA check(s) failed "
                f"({', '.join(failed_critical)})."
            )

    score = max(0.0, min(100.0, score))
    score = round(score, 1)

    rating, color = next(
        (name, colour) for threshold, name, colour in RATING_BANDS
        if score >= threshold
    )

    # Human-readable summary of what cost the most points. Retained under the
    # original key so existing consumers keep working.
    deductions = [
        f"{entry['label']}: {entry['value']}{entry['unit']} "
        f"(target {entry['target']}) scored {entry['score']}/100"
        for entry in sorted(
            (c for c in components if c["score"] is not None and c["score"] < 100),
            key=lambda c: (100 - c["score"]) * c["weight"], reverse=True,
        )
    ]

    return {
        "score": score,
        "rating": rating,
        "color": color,
        "components": components,
        "caps": caps,
        "deductions": deductions,
        "applicable_weight": applicable_weight,
        "description": f"Overall schedule health: {rating} ({score:.1f}/100)",
    }


def methodology() -> List[Dict[str, Any]]:
    """The weighting table, for display in the UI and in generated reports."""
    return [
        {
            "DCMA Point": component.dcma or "-",
            "Check": component.label,
            "Weight": component.weight,
            "Target": component.describe_target(),
            "Scores 0 at": (
                f"{component.zero_at:g}{component.unit}"
                if not component.higher_is_better
                else f"≤{component.zero_at:g}"
            ),
        }
        for component in COMPONENTS
    ]
