"""
End-to-end pipeline: parse -> analyse -> persist -> reload -> generate reports.

This is the path a user actually exercises, and it is where the previous
in-memory store silently lost data between page loads.
"""

import zipfile

import pandas as pd
import pytest

from src.analysis.dcma_analyzer import DCMAAnalyzer
from src.analysis.metrics_calculator import MetricsCalculator
from src.analysis.recommendations import RecommendationsEngine
from src.database.db_manager import DatabaseManager
from src.parsers.schedule_parser import ScheduleParser
from src.reports.docx_generator import DOCXGenerator
from src.reports.excel_generator import ExcelGenerator


def run_full_pipeline(db, admin, csv_bytes, file_name="schedule.csv"):
    """Mirror exactly what pages/1_Upload_Schedule.py does."""
    data = ScheduleParser().parse_csv(csv_bytes, file_name)
    assert data["success"], data.get("errors")

    project = db.create_project("Integration", "INT-1", "", admin["id"])
    schedule = db.create_schedule(project["id"], data, file_name, admin["id"])

    analyzer = DCMAAnalyzer(data)
    dcma = analyzer.analyze()
    performance = MetricsCalculator(data, dcma["metrics"]).calculate_all_metrics()
    summary = analyzer.get_dcma_14_point_summary(
        performance.get("cpli", {}).get("value", 0),
        performance.get("bei", {}).get("value", 0),
    )
    recommendations = RecommendationsEngine(
        dcma["metrics"], performance, dcma["issues"]).generate_recommendations()

    analysis = db.save_analysis_result(
        schedule_id=schedule["id"],
        metrics=dcma["metrics"],
        issues=dcma["issues"],
        recommendations=recommendations,
        health_score=performance["health_score"]["score"],
        extra={
            "performance_metrics": performance,
            "dcma_metrics": dcma["metrics"],
            "dcma_14_point": summary,
        },
    )
    return project, schedule, analysis


class TestFullPipeline:
    def test_sample_schedule_end_to_end(self, db, admin, sample_csv_bytes):
        project, schedule, analysis = run_full_pipeline(db, admin, sample_csv_bytes)

        assert schedule["schedule_data"]["total_activities"] == 28
        assert 0 <= analysis["health_score"] <= 100
        assert analysis["recommendations"]

    def test_real_export_end_to_end(self, db, admin, real_export_bytes):
        project, schedule, analysis = run_full_pipeline(
            db, admin, real_export_bytes, "Schedule export.csv")

        assert schedule["schedule_data"]["total_activities"] == 1261
        assert 0 <= analysis["health_score"] <= 100

    def test_everything_survives_an_application_restart(self, db, admin,
                                                        sample_csv_bytes):
        """
        The core regression: with the old session_state store, a refresh lost
        every project, schedule and analysis.
        """
        project, schedule, analysis = run_full_pipeline(db, admin, sample_csv_bytes)

        restarted = DatabaseManager(db_path=db.db_path)

        assert len(restarted.get_all_projects()) == 1
        assert restarted.count_schedules() == 1
        assert restarted.count_analyses() == 1

        reloaded = restarted.get_analysis_by_schedule(schedule["id"])
        assert reloaded["health_score"] == analysis["health_score"]
        # The dashboard reads the rating from here; it used to be lost, leaving
        # the UI showing "Unknown".
        assert reloaded["performance_metrics"]["health_score"]["rating"] != "Unknown"
        assert reloaded["dcma_14_point"]["categories"]

    def test_reanalysing_a_reloaded_schedule_gives_the_same_result(
            self, db, admin, sample_csv_bytes):
        """Round-tripping through the database must not change the numbers."""
        project, schedule, analysis = run_full_pipeline(db, admin, sample_csv_bytes)

        reloaded = DatabaseManager(db_path=db.db_path).get_schedule_by_id(
            schedule["id"])
        data = reloaded["schedule_data"]

        dcma = DCMAAnalyzer(data).analyze()
        performance = MetricsCalculator(data, dcma["metrics"]).calculate_all_metrics()

        assert performance["health_score"]["score"] == analysis["health_score"]


class TestReportGeneration:
    @pytest.fixture
    def pipeline(self, db, admin, sample_csv_bytes):
        return run_full_pipeline(db, admin, sample_csv_bytes)

    def _full_analysis(self, analysis):
        return {
            "dcma_metrics": analysis["metrics"],
            "performance_metrics": analysis.get("performance_metrics", {}),
            "dcma_14_point": analysis.get("dcma_14_point", {}),
            "issues": analysis["issues"],
            "recommendations": analysis.get("recommendations", []),
        }

    def test_docx_is_generated_from_persisted_data(self, db, pipeline):
        project, schedule, analysis = pipeline
        reloaded = DatabaseManager(db_path=db.db_path)

        generator = DOCXGenerator(
            project_name=project["project_name"],
            schedule_data=reloaded.get_schedule_by_id(
                schedule["id"])["schedule_data"],
            analysis_results=self._full_analysis(
                reloaded.get_analysis_by_schedule(schedule["id"])),
        )
        content = generator.generate()

        assert isinstance(content, (bytes, bytearray)) and len(content) > 0
        # A .docx is a zip container; verify it is structurally valid.
        import io
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            assert "word/document.xml" in archive.namelist()

    def test_excel_is_generated_from_persisted_data(self, db, pipeline):
        project, schedule, analysis = pipeline
        reloaded = DatabaseManager(db_path=db.db_path)

        generator = ExcelGenerator(
            project_name=project["project_name"],
            schedule_data=reloaded.get_schedule_by_id(
                schedule["id"])["schedule_data"],
            analysis_results=self._full_analysis(
                reloaded.get_analysis_by_schedule(schedule["id"])),
        )
        content = generator.generate()

        assert isinstance(content, (bytes, bytearray)) and len(content) > 0

        import io
        import openpyxl
        workbook = openpyxl.load_workbook(io.BytesIO(content))
        assert workbook.sheetnames


class TestVersionComparison:
    def test_two_versions_of_a_project_are_both_retained(self, db, admin,
                                                         sample_csv_bytes):
        data = ScheduleParser().parse_csv(sample_csv_bytes, "v1.csv")
        project = db.create_project("P", "P-1", "", admin["id"])

        first = db.create_schedule(project["id"], data, "v1.csv", admin["id"])
        second = db.create_schedule(project["id"], data, "v2.csv", admin["id"])

        db.save_analysis_result(first["id"], {}, [], [], 40.0)
        db.save_analysis_result(second["id"], {}, [], [], 70.0)

        schedules = db.get_schedules_by_project(project["id"])
        assert [s["version_number"] for s in schedules] == [1, 2]
        assert db.get_analysis_by_schedule(first["id"])["health_score"] == 40.0
        assert db.get_analysis_by_schedule(second["id"])["health_score"] == 70.0


class TestMaliciousContent:
    def test_script_tags_in_activity_names_survive_as_inert_text(
            self, db, admin, csv_builder):
        """
        A crafted activity name must round-trip as data, never as markup. The
        UI escaping is covered in test_ui_safety; this checks the pipeline does
        not choke on it and does not execute it.
        """
        build_csv, build_row = csv_builder
        content = build_csv([
            build_row("A1", name="<script>alert('xss')</script>",
                      successors="A2: FS"),
            build_row("A2", name="Normal Task", predecessors="A1: FS"),
        ])

        project, schedule, analysis = run_full_pipeline(db, admin, content)
        reloaded = DatabaseManager(db_path=db.db_path).get_schedule_by_id(
            schedule["id"])

        names = pd.DataFrame(
            reloaded["schedule_data"]["activities"])["Activity Name"].tolist()
        assert "<script>alert('xss')</script>" in names

    def test_formula_injection_content_is_stored_verbatim(self, db, admin,
                                                          csv_builder):
        build_csv, build_row = csv_builder
        content = build_csv([build_row("A1", name="=cmd|'/c calc'!A1")])

        project, schedule, _ = run_full_pipeline(db, admin, content)
        reloaded = DatabaseManager(db_path=db.db_path).get_schedule_by_id(
            schedule["id"])
        names = pd.DataFrame(
            reloaded["schedule_data"]["activities"])["Activity Name"].tolist()
        assert names == ["=cmd|'/c calc'!A1"]
