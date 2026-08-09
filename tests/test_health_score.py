"""
Health score weighting.

These lock in the three defects the previous scoring had: it saturated after a
handful of occurrences, it ranked a schedule with no logic at all above a
well-linked one with a few leads, and the weights were undocumented magic
numbers.
"""

import pytest

from src.analysis import health_score
from src.analysis.dcma_analyzer import DCMAAnalyzer
from src.analysis.metrics_calculator import MetricsCalculator
from src.parsers.schedule_parser import ScheduleParser

HEADER = ("Activity ID,Activity Name,Activity Status,Start,Finish,Total Float,"
          "Duration Type,Predecessor Details,Successor Details,"
          "Primary Constraint,At Completion Duration\n")


def _row(index, predecessor="", successor="", total_float=5):
    return (f"A{index},Task {index},Not Started,01/03/2025,15/03/2025,"
            f"{total_float},Fixed,{predecessor},{successor},,10\n")


def build_chain(size=200, leads=0, dangling=0, negative_float=0):
    """A linked chain, optionally degraded in a specific, isolated way."""
    rows = [_row(0, successor="A1: FS")]
    for index in range(1, size - 1):
        if index <= dangling:
            rows.append(_row(index))
            continue
        predecessor = (f"A{index - 1}: FS -5" if index <= leads + dangling
                       else f"A{index - 1}: FS")
        rows.append(_row(index, predecessor=predecessor,
                         successor=f"A{index + 1}: FS",
                         total_float=-10 if index <= negative_float else 5))
    rows.append(_row(size - 1, predecessor=f"A{size - 2}: FS"))
    return rows


def score_of(rows):
    data = ScheduleParser().parse_csv((HEADER + "".join(rows)).encode(), "t.csv")
    assert data["success"], data.get("errors")
    results = DCMAAnalyzer(data).analyze()
    metrics = MetricsCalculator(data, results["metrics"]).calculate_all_metrics()
    return metrics["health_score"]


class TestComponentScoring:
    def test_value_at_target_scores_full_marks(self):
        component = health_score.Component("x", "X", 1, 10, target=5, zero_at=50)
        assert component.score(5) == 100.0
        assert component.score(0) == 100.0

    def test_value_at_zero_bound_scores_nothing(self):
        component = health_score.Component("x", "X", 1, 10, target=5, zero_at=50)
        assert component.score(50) == 0.0
        assert component.score(80) == 0.0

    def test_interpolation_is_linear(self):
        component = health_score.Component("x", "X", 1, 10, target=0, zero_at=100)
        assert component.score(25) == pytest.approx(75.0)
        assert component.score(50) == pytest.approx(50.0)

    def test_higher_is_better_components_invert(self):
        component = health_score.Component("cpli", "CPLI", 13, 5, target=0.95,
                                           zero_at=0.80, higher_is_better=True)
        assert component.score(1.0) == 100.0
        assert component.score(0.80) == 0.0
        assert component.score(0.875) == pytest.approx(50.0)

    def test_weights_sum_to_one_hundred(self):
        assert sum(c.weight for c in health_score.COMPONENTS) == 100


class TestProportionality:
    """The old score capped deductions by absolute count and stopped moving."""

    def test_more_leads_scores_worse(self):
        scores = [score_of(build_chain(200, leads=n))["score"]
                  for n in (0, 5, 10, 20)]
        assert scores == sorted(scores, reverse=True), scores
        assert scores[0] > scores[-1]

    def test_more_missing_logic_scores_worse(self):
        scores = [score_of(build_chain(200, dangling=n))["score"]
                  for n in (0, 20, 50, 100)]
        assert scores == sorted(scores, reverse=True), scores

    def test_distinct_schedules_get_distinct_scores(self):
        """Previously two unrelated real schedules both scored exactly 40.0."""
        a = score_of(build_chain(200, leads=5))["score"]
        b = score_of(build_chain(200, dangling=30))["score"]
        assert a != b

    def test_real_files_are_not_identical(self, sample_csv_bytes,
                                          real_export_bytes):
        def real_score(content):
            data = ScheduleParser().parse_csv(content, "x.csv")
            results = DCMAAnalyzer(data).analyze()
            return MetricsCalculator(
                data, results["metrics"]
            ).calculate_all_metrics()["health_score"]["score"]

        assert real_score(sample_csv_bytes) != real_score(real_export_bytes)


class TestOrdering:
    """The old score rated a logic-free schedule above a well-linked one."""

    def test_zero_logic_scores_worse_than_a_few_leads(self):
        zero_logic = score_of([_row(i) for i in range(200)])
        few_leads = score_of(build_chain(200, leads=3))

        assert zero_logic["score"] < few_leads["score"], (
            f"logic-free schedule scored {zero_logic['score']} vs "
            f"{few_leads['score']} for a linked schedule with 3 leads"
        )

    def test_zero_logic_is_rated_critical(self):
        result = score_of([_row(i) for i in range(200)])
        assert result["rating"] == "Critical"
        assert result["caps"], "no explanation given for the capped score"

    def test_pristine_schedule_scores_excellent(self):
        result = score_of(build_chain(200))
        assert result["score"] >= 90
        assert result["rating"] == "Excellent"


class TestGates:
    def test_no_relationship_data_caps_the_score(self):
        result = score_of([_row(i) for i in range(50)])
        assert result["score"] <= health_score.GATES["no_relationships"][0]
        assert any("relationship data" in cap for cap in result["caps"])

    def test_majority_missing_logic_caps_the_score(self):
        result = score_of(build_chain(200, dangling=140))
        assert result["score"] <= health_score.GATES["logic_unusable"][0]

    def test_one_critical_failure_prevents_excellent(self):
        result = score_of(build_chain(200, leads=40))
        assert result["rating"] != "Excellent"
        assert result["score"] <= 89.0

    def test_two_critical_failures_cap_at_fair(self):
        result = score_of(build_chain(200, leads=60, negative_float=60))
        assert result["score"] <= 74.0

    def test_only_one_ceiling_reason_is_reported(self):
        result = score_of(build_chain(200, leads=60, negative_float=60))
        ceiling_reasons = [c for c in result["caps"] if "critical" in c]
        assert len(ceiling_reasons) == 1


class TestMissingDataHandling:
    def test_unavailable_checks_are_marked_na_not_passed(self):
        """A check with no data must not score as a silent pass."""
        result = health_score.calculate(dcma_metrics={}, total_activities=10)
        statuses = {c["key"]: c["status"] for c in result["components"]}
        assert statuses["leads"] == "n/a"
        assert statuses["cpli"] == "n/a"

    def test_weights_are_renormalised_over_applicable_checks(self):
        metrics = {
            "missing_logic": {"count": 0},
            "positive_lags": {"total_relationships": 10, "percentage": 0},
            "negative_lags": {"count": 0},
        }
        result = health_score.calculate(metrics, total_activities=100)
        assert result["applicable_weight"] < 100
        assert result["score"] == pytest.approx(100.0)

    def test_no_measurable_data_yields_zero(self):
        result = health_score.calculate({}, total_activities=0)
        assert result["score"] == 0.0


class TestOutputContract:
    """Reports and pages read these keys; they must keep working."""

    def test_required_keys_are_present(self):
        result = score_of(build_chain(50))
        for key in ("score", "rating", "color", "deductions", "description",
                    "components", "caps"):
            assert key in result, f"missing key {key}"

    def test_rating_matches_the_score_band(self):
        for rows in (build_chain(200), build_chain(200, leads=40),
                     build_chain(200, dangling=140),
                     [_row(i) for i in range(50)]):
            result = score_of(rows)
            expected = next(name for threshold, name, _ in
                            health_score.RATING_BANDS
                            if result["score"] >= threshold)
            assert result["rating"] == expected

    def test_score_is_always_within_bounds(self):
        for rows in (build_chain(200), build_chain(200, leads=100),
                     build_chain(200, dangling=190),
                     [_row(i) for i in range(10)]):
            assert 0 <= score_of(rows)["score"] <= 100

    def test_every_component_is_explainable(self):
        result = score_of(build_chain(200, leads=10))
        for component in result["components"]:
            assert component["label"]
            assert component["weight"] > 0
            assert component["target"]
            assert component["status"] in {"pass", "warning", "fail", "n/a"}


class TestMethodologyIsPublished:
    def test_methodology_table_covers_every_component(self):
        table = health_score.methodology()
        assert len(table) == len(health_score.COMPONENTS)
        for entry in table:
            assert entry["Check"] and entry["Weight"] and entry["Target"]

    def test_methodology_weights_match_the_components(self):
        assert (sum(entry["Weight"] for entry in health_score.methodology())
                == 100)
