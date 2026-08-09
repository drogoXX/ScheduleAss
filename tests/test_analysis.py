"""DCMA analysis, derived metrics and robustness against degenerate schedules."""

import pytest

from src.analysis.dcma_analyzer import DCMAAnalyzer
from src.analysis.metrics_calculator import MetricsCalculator
from src.analysis.recommendations import RecommendationsEngine
from src.parsers.schedule_parser import ScheduleParser


def analyse(content):
    data = ScheduleParser().parse_csv(content, "t.csv")
    assert data["success"], data.get("errors")
    analyzer = DCMAAnalyzer(data)
    results = analyzer.analyze()
    metrics = MetricsCalculator(data, results["metrics"]).calculate_all_metrics()
    return data, analyzer, results, metrics


class TestDCMAMetrics:
    def test_negative_lags_are_detected(self, csv_builder):
        build_csv, build_row = csv_builder
        content = build_csv([
            build_row("A1", successors="A2: FS -5"),
            build_row("A2", predecessors="A1: FS -5"),
        ])
        _, _, results, _ = analyse(content)
        assert results["metrics"]["negative_lags"]["count"] == 1
        assert results["metrics"]["negative_lags"]["status"] == "fail"

    def test_clean_schedule_passes_negative_lag_check(self, csv_builder):
        build_csv, build_row = csv_builder
        content = build_csv([
            build_row("A1", successors="A2: FS"),
            build_row("A2", predecessors="A1: FS"),
        ])
        _, _, results, _ = analyse(content)
        assert results["metrics"]["negative_lags"]["count"] == 0
        assert results["metrics"]["negative_lags"]["status"] == "pass"

    def test_issues_carry_the_fields_the_ui_renders(self, csv_builder):
        build_csv, build_row = csv_builder
        content = build_csv([
            build_row("A1", successors="A2: FS -5"),
            build_row("A2", predecessors="A1: FS -5"),
        ])
        _, _, results, _ = analyse(content)
        assert results["issues"], "expected at least one issue"
        for issue in results["issues"]:
            for field in ("category", "severity", "title", "description",
                          "recommendation"):
                assert field in issue, f"issue missing {field}: {issue}"

    def test_dcma_14_point_summary_is_produced(self, parsed_sample):
        analyzer = DCMAAnalyzer(parsed_sample)
        results = analyzer.analyze()
        metrics = MetricsCalculator(parsed_sample,
                                    results["metrics"]).calculate_all_metrics()
        summary = analyzer.get_dcma_14_point_summary(
            metrics["cpli"]["value"], metrics["bei"]["value"])

        assert "overall_score" in summary
        assert summary["categories"], "no DCMA categories returned"


class TestHealthScore:
    def test_health_score_bounds(self, sample_csv_bytes):
        _, _, _, metrics = analyse(sample_csv_bytes)
        score = metrics["health_score"]["score"]
        assert 0 <= score <= 100

    def test_rating_matches_the_score_band(self, sample_csv_bytes):
        _, _, _, metrics = analyse(sample_csv_bytes)
        health = metrics["health_score"]
        score, rating = health["score"], health["rating"]

        bands = [(90, "Excellent"), (75, "Good"), (60, "Fair"), (40, "Poor"),
                 (0, "Critical")]
        expected = next(name for threshold, name in bands if score >= threshold)
        assert rating == expected

    def test_clean_schedule_scores_above_a_broken_one(self, csv_builder):
        build_csv, build_row = csv_builder

        clean = build_csv([
            build_row("A1", successors="A2: FS", total_float=5),
            build_row("A2", predecessors="A1: FS", successors="A3: FS",
                      total_float=5),
            build_row("A3", predecessors="A2: FS", total_float=5),
        ])
        broken = build_csv([
            build_row("A1", successors="A2: FS -10", total_float=5),
            build_row("A2", predecessors="A1: FS -10", total_float=5),
            build_row("A3", predecessors="", successors="", total_float=5),
        ])

        _, _, _, clean_metrics = analyse(clean)
        _, _, _, broken_metrics = analyse(broken)
        assert (clean_metrics["health_score"]["score"]
                > broken_metrics["health_score"]["score"])


class TestDegenerateSchedules:
    """Schedules that are valid CSV but pathological must not crash the app."""

    def test_single_activity(self, csv_builder):
        build_csv, build_row = csv_builder
        _, _, results, metrics = analyse(build_csv([build_row("A1")]))
        assert 0 <= metrics["health_score"]["score"] <= 100

    def test_all_dates_blank(self, csv_builder):
        build_csv, build_row = csv_builder
        content = build_csv([
            build_row("A1", start="", finish="", successors="A2: FS"),
            build_row("A2", start="", finish="", predecessors="A1: FS"),
        ])
        _, _, results, metrics = analyse(content)
        assert 0 <= metrics["health_score"]["score"] <= 100

    def test_zero_and_negative_float(self, csv_builder):
        build_csv, build_row = csv_builder
        content = build_csv([
            build_row("A1", total_float=-30, free_float=-30),
            build_row("A2", total_float=0, free_float=0),
        ])
        _, _, results, metrics = analyse(content)
        assert 0 <= metrics["health_score"]["score"] <= 100

    def test_finish_before_start(self, csv_builder):
        build_csv, build_row = csv_builder
        content = build_csv([
            build_row("A1", start="30/08/2025 08:00", finish="01/08/2025 17:00"),
        ])
        _, _, results, metrics = analyse(content)
        assert 0 <= metrics["health_score"]["score"] <= 100

    def test_duplicate_activity_ids(self, csv_builder):
        build_csv, build_row = csv_builder
        content = build_csv([build_row("A1"), build_row("A1")])
        _, _, results, metrics = analyse(content)
        assert 0 <= metrics["health_score"]["score"] <= 100

    def test_relationships_pointing_at_missing_activities(self, csv_builder):
        build_csv, build_row = csv_builder
        content = build_csv([build_row("A1", predecessors="DOES_NOT_EXIST: FS")])
        _, _, results, metrics = analyse(content)
        assert 0 <= metrics["health_score"]["score"] <= 100


class TestRecommendations:
    def test_recommendations_are_generated_for_a_flawed_schedule(self,
                                                                 sample_csv_bytes):
        data, _, results, metrics = analyse(sample_csv_bytes)
        recommendations = RecommendationsEngine(
            results["metrics"], metrics, results["issues"]).generate_recommendations()

        assert recommendations
        for rec in recommendations:
            for field in ("title", "category", "priority", "description",
                          "recommendation", "impact", "effort"):
                assert field in rec, f"recommendation missing {field}: {rec}"

    def test_priorities_are_known_values(self, sample_csv_bytes):
        data, _, results, metrics = analyse(sample_csv_bytes)
        recommendations = RecommendationsEngine(
            results["metrics"], metrics, results["issues"]).generate_recommendations()
        assert all(r["priority"] in {"high", "medium", "low", "critical"}
                   for r in recommendations)


class TestRealExportRegression:
    def test_full_pipeline_on_the_real_export(self, real_export_bytes):
        data, analyzer, results, metrics = analyse(real_export_bytes)

        assert data["total_activities"] == 1261
        assert 0 <= metrics["health_score"]["score"] <= 100
        assert metrics["statistics"]["total_activities"] == 1261

        recommendations = RecommendationsEngine(
            results["metrics"], metrics, results["issues"]).generate_recommendations()
        assert recommendations
