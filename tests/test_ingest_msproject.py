"""Tests for Microsoft Project CSV ingestion.

Covers the two export behaviours that silently corrupt an assessment if not
handled: the 255-character relationship cap, and summary rows being emitted as
tasks. See docs/TECHNICAL_SPECIFICATION_v2.md §6.
"""

from pathlib import Path

import pandas as pd
import pytest

from src.analysis.dcma_analyzer import DCMAAnalyzer
from src.core.ingest import MSProjectCsvReader, SourceFormat, detect_format
from src.parsers.schedule_parser import ScheduleParser

REFERENCE_EXPORT = (
    Path(__file__).resolve().parents[1] / "Schedule extract" / "VRATO" / "Project12.csv"
)

P6_HEADER = (
    "Activity ID,Activity Status,WBS Code,At Completion Duration(d),Activity Name,"
    "Start,Finish,Total Float,Predecessors,Predecessor Details,Successors,"
    "Successor Details,Primary Constraint,Activity Type,Duration Type\n"
    "A100,Not Started,WBS.1,5,Do a thing,01-Jan-26,06-Jan-26,0,,,,,,Task Dependent,Fixed\n"
)

MSP_HEADER = "ID,Unique_ID,WBS,Summary,Name,Duration,Start_Date,Finish_Date,Total_Slack,Free_Slack,Predecessors,Successors,Constraint_Type,Constraint_Date,Milestone,Type\n"


def msp_csv(*rows: str) -> bytes:
    return (MSP_HEADER + "".join(r if r.endswith("\n") else r + "\n" for r in rows)).encode("cp1252")


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

class TestFormatDetection:
    def test_detects_msproject(self):
        assert detect_format(msp_csv()) is SourceFormat.MSPROJECT_CSV

    def test_detects_p6(self):
        assert detect_format(P6_HEADER.encode("utf-8")) is SourceFormat.P6_CSV

    def test_detects_p6_with_unit_suffixes(self):
        header = "Activity ID,Activity Name,Total Float(d),Activity Status\nA1,x,0,Completed\n"
        assert detect_format(header.encode("utf-8")) is SourceFormat.P6_CSV

    def test_unknown_format(self):
        assert detect_format(b"alpha,beta,gamma\n1,2,3\n") is SourceFormat.UNKNOWN

    def test_empty_input(self):
        assert detect_format(b"") is SourceFormat.UNKNOWN

    def test_detection_ignores_filename(self):
        """A P6 file named like an MSP export must still detect as P6."""
        assert detect_format(P6_HEADER.encode("utf-8"), "Project12.csv") is SourceFormat.P6_CSV

    def test_handles_cp1252_bytes(self):
        """MS Project writes the ANSI codepage; a strict UTF-8 read would fail."""
        data = msp_csv("1,1,1,No,Café Ünïcode,5 days,01.02.26,06.02.26,0 days,0 days,,,As Soon As Possible,NA,No,Fixed Duration")
        assert detect_format(data) is SourceFormat.MSPROJECT_CSV
        result = MSProjectCsvReader().read(data)
        assert result.ok
        assert "Café" in result.frame.loc[0, "Activity Name"]


# ---------------------------------------------------------------------------
# Translation semantics
# ---------------------------------------------------------------------------

class TestTranslation:
    def test_duration_and_slack_parsed_to_days(self):
        data = msp_csv("1,1,1,No,Task,827 days,15.05.26,16.07.29,12 days,3 days,,,As Soon As Possible,NA,No,Fixed Duration")
        r = MSProjectCsvReader().read(data)
        assert r.ok
        assert r.frame.loc[0, "At Completion Duration"] == 827.0
        assert r.frame.loc[0, "Total Float"] == 12.0
        assert r.frame.loc[0, "Free Float"] == 3.0

    def test_week_units_converted(self):
        data = msp_csv("1,1,1,No,Task,2 wks,15.05.26,16.07.26,1 wk,0 days,,,As Soon As Possible,NA,No,Fixed Duration")
        r = MSProjectCsvReader().read(data)
        assert r.frame.loc[0, "At Completion Duration"] == 10.0
        assert r.frame.loc[0, "Total Float"] == 5.0

    def test_constraint_vocabulary_mapped_to_p6(self):
        data = msp_csv(
            "1,1,1,No,A,1 day,15.05.26,15.05.26,0 days,0 days,,,Start No Earlier Than,15.05.26,No,Fixed Duration",
            "2,2,2,No,B,1 day,15.05.26,15.05.26,0 days,0 days,,,Must Finish On,15.05.26,No,Fixed Duration",
        )
        r = MSProjectCsvReader().read(data)
        assert r.frame.loc[0, "Primary Constraint"] == "Start On or After"   # flexible
        assert r.frame.loc[1, "Primary Constraint"] == "Must Finish On"      # hard

    def test_unknown_constraint_kept_verbatim_and_warned(self):
        data = msp_csv("1,1,1,No,A,1 day,15.05.26,15.05.26,0 days,0 days,,,Invented Constraint,NA,No,Fixed Duration")
        r = MSProjectCsvReader().read(data)
        assert r.frame.loc[0, "Primary Constraint"] == "Invented Constraint"
        assert any("Unrecognised MS Project constraint" in w for w in r.warnings)

    def test_day_first_dates(self):
        """15.05.26 is 15 May 2026, not 5 Mar 2026."""
        data = msp_csv("1,1,1,No,A,1 day,15.05.26,16.05.26,0 days,0 days,,,As Soon As Possible,NA,No,Fixed Duration")
        r = MSProjectCsvReader().read(data)
        assert r.frame.loc[0, "Start"] == pd.Timestamp("2026-05-15")

    def test_status_is_unknown_not_fabricated(self):
        """MSP CSV has no status; inventing 'Not Started' would be a fabricated input."""
        data = msp_csv("1,1,1,No,A,1 day,15.05.26,16.05.26,0 days,0 days,,,As Soon As Possible,NA,No,Fixed Duration")
        r = MSProjectCsvReader().read(data)
        assert r.frame.loc[0, "Activity Status"] == "Unknown"
        assert any("no activity status" in w.lower() for w in r.warnings)

    def test_blank_placeholder_rows_dropped(self):
        data = msp_csv(
            "1,1,1,No,Real task,1 day,15.05.26,16.05.26,0 days,0 days,,,As Soon As Possible,NA,No,Fixed Duration",
            "2,2,2,,,,,,,,,,,,,",
        )
        r = MSProjectCsvReader().read(data)
        assert len(r.frame) == 1
        assert r.dropped_blank_rows == 1

    def test_missing_required_column_is_an_error(self):
        r = MSProjectCsvReader().read(b"Unique_ID,Total_Slack,Start_Date,Finish_Date\n1,0 days,15.05.26,16.05.26\n")
        assert not r.ok
        assert any("Missing required" in e for e in r.errors)


# ---------------------------------------------------------------------------
# Relationships - the important part
# ---------------------------------------------------------------------------

class TestRelationships:
    def test_bare_id_defaults_to_fs_zero_lag(self):
        data = msp_csv(
            "1,101,1,No,A,1 day,15.05.26,16.05.26,0 days,0 days,,,As Soon As Possible,NA,No,Fixed Duration",
            "2,102,2,No,B,1 day,17.05.26,18.05.26,0 days,0 days,1,,As Soon As Possible,NA,No,Fixed Duration",
        )
        r = MSProjectCsvReader().read(data)
        preds = r.frame.loc[1, "predecessor_list"]
        assert preds == [{"activity": "101", "type": "FS", "lag": 0}]

    def test_type_and_lag_parsed(self):
        data = msp_csv(
            "1,101,1,No,A,1 day,15.05.26,16.05.26,0 days,0 days,,,As Soon As Possible,NA,No,Fixed Duration",
            "2,102,2,No,B,1 day,17.05.26,18.05.26,0 days,0 days,1FF+62 days,,As Soon As Possible,NA,No,Fixed Duration",
        )
        r = MSProjectCsvReader().read(data)
        assert r.frame.loc[1, "predecessor_list"] == [{"activity": "101", "type": "FF", "lag": 62}]

    def test_negative_lag_preserved(self):
        data = msp_csv(
            "1,101,1,No,A,1 day,15.05.26,16.05.26,0 days,0 days,,,As Soon As Possible,NA,No,Fixed Duration",
            "2,102,2,No,B,1 day,17.05.26,18.05.26,0 days,0 days,1SS-5 days,,As Soon As Possible,NA,No,Fixed Duration",
        )
        r = MSProjectCsvReader().read(data)
        assert r.frame.loc[1, "predecessor_list"][0]["lag"] == -5

    def test_references_remapped_from_row_id_to_unique_id(self):
        """Relationships cite the volatile row ID; activities are keyed on Unique_ID."""
        data = msp_csv(
            "1,900,1,No,A,1 day,15.05.26,16.05.26,0 days,0 days,,,As Soon As Possible,NA,No,Fixed Duration",
            "2,901,2,No,B,1 day,17.05.26,18.05.26,0 days,0 days,1,,As Soon As Possible,NA,No,Fixed Duration",
        )
        r = MSProjectCsvReader().read(data)
        assert list(r.frame["Activity ID"]) == ["900", "901"]
        assert r.frame.loc[1, "predecessor_list"][0]["activity"] == "900"

    def test_successors_derived_by_inversion(self):
        data = msp_csv(
            "1,101,1,No,A,1 day,15.05.26,16.05.26,0 days,0 days,,,As Soon As Possible,NA,No,Fixed Duration",
            "2,102,2,No,B,1 day,17.05.26,18.05.26,0 days,0 days,1FF+3 days,,As Soon As Possible,NA,No,Fixed Duration",
        )
        r = MSProjectCsvReader().read(data)
        # A stated no successors, but B names A as a predecessor.
        assert r.frame.loc[0, "successor_list"] == [{"activity": "102", "type": "FF", "lag": 3}]

    def test_truncated_successor_cell_recovered_and_reported(self):
        """The 255-char cap drops edges from Successors; inversion restores them."""
        data = msp_csv(
            "1,101,1,No,A,1 day,15.05.26,16.05.26,0 days,0 days,,2;3;4;5;6;7...,As Soon As Possible,NA,No,Fixed Duration",
            "2,102,2,No,B,1 day,17.05.26,18.05.26,0 days,0 days,1,,As Soon As Possible,NA,No,Fixed Duration",
            "3,103,3,No,C,1 day,17.05.26,18.05.26,0 days,0 days,1,,As Soon As Possible,NA,No,Fixed Duration",
        )
        r = MSProjectCsvReader().read(data)
        successors = {s["activity"] for s in r.frame.loc[0, "successor_list"]}
        assert successors == {"102", "103"}
        assert r.truncated_cells >= 1
        assert any("255-character" in w for w in r.warnings)

    def test_unresolvable_reference_skipped_and_reported(self):
        data = msp_csv(
            "1,101,1,No,A,1 day,15.05.26,16.05.26,0 days,0 days,9999,,As Soon As Possible,NA,No,Fixed Duration",
        )
        r = MSProjectCsvReader().read(data)
        assert r.frame.loc[0, "predecessor_list"] == []
        assert any("could not be resolved" in w for w in r.warnings)


# ---------------------------------------------------------------------------
# Summary (rollup) rows
# ---------------------------------------------------------------------------

class TestSummaryRows:
    def test_summary_rows_flagged_and_typed(self):
        data = msp_csv(
            "1,101,1,Yes,Phase,10 days,15.05.26,26.05.26,0 days,0 days,,,As Soon As Possible,NA,No,Fixed Duration",
            "2,102,1.1,No,Task,5 days,15.05.26,20.05.26,0 days,0 days,,,As Soon As Possible,NA,No,Fixed Duration",
        )
        r = MSProjectCsvReader().read(data)
        assert list(r.frame["is_summary_task"]) == [True, False]
        assert r.frame.loc[0, "Activity Type"] == "WBS Summary"
        assert r.summary_task_count == 1

    def test_milestone_flag_maps_to_activity_type(self):
        data = msp_csv(
            "1,101,1,No,M,0 days,15.05.26,15.05.26,0 days,0 days,,,As Soon As Possible,NA,Yes,Fixed Units",
        )
        r = MSProjectCsvReader().read(data)
        assert "Milestone" in r.frame.loc[0, "Activity Type"]

    def test_analyzer_excludes_summary_rows(self):
        """Rollups have no logic by design; counting them inflates missing-logic."""
        data = msp_csv(
            "1,101,1,Yes,Phase,10 days,15.05.26,26.05.26,0 days,0 days,,,As Soon As Possible,NA,No,Fixed Duration",
            "2,102,1.1,No,TaskA,5 days,15.05.26,20.05.26,0 days,0 days,,3,As Soon As Possible,NA,No,Fixed Duration",
            "3,103,1.2,No,TaskB,5 days,21.05.26,26.05.26,0 days,0 days,2,,As Soon As Possible,NA,No,Fixed Duration",
        )
        sd = ScheduleParser().parse_csv(data, "p.csv")
        assert sd["success"]
        result = DCMAAnalyzer(sd).analyze()
        scope = result["metrics"]["assessment_scope"]
        assert scope["rows_in_export"] == 3
        assert scope["summary_rows_excluded"] == 1
        assert scope["activities_assessed"] == 2

    def test_p6_exports_unaffected_by_summary_exclusion(self):
        """P6 has no summary rows; scope must report zero exclusions."""
        sd = ScheduleParser().parse_csv(P6_HEADER.encode("utf-8"), "p6.csv")
        assert sd["success"]
        scope = DCMAAnalyzer(sd).analyze()["metrics"]["assessment_scope"]
        assert scope["summary_rows_excluded"] == 0
        assert scope["activities_assessed"] == scope["rows_in_export"]


# ---------------------------------------------------------------------------
# End-to-end against the real export
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not REFERENCE_EXPORT.exists(), reason="reference export not present")
class TestReferenceExport:
    @pytest.fixture(scope="class")
    def parsed(self):
        return ScheduleParser().parse_csv(REFERENCE_EXPORT.read_bytes(), "Project12.csv")

    def test_parses(self, parsed):
        assert parsed["success"], parsed.get("errors")
        assert parsed["source_format"] == "msproject_csv"
        assert parsed["total_activities"] == 764

    def test_relationship_graph_is_balanced(self, parsed):
        """Inversion guarantees predecessor and successor edge counts match."""
        df = pd.DataFrame(parsed["activities"])
        assert sum(len(x) for x in df["predecessor_list"]) == 1098
        assert sum(len(x) for x in df["successor_list"]) == 1098

    def test_dates_are_day_first(self, parsed):
        df = pd.DataFrame(parsed["activities"])
        assert df["Start"].min() == pd.Timestamp("2026-05-15")
        assert df["Finish"].max() == pd.Timestamp("2029-07-16")

    def test_analysis_runs_and_excludes_rollups(self, parsed):
        scope = DCMAAnalyzer(parsed).analyze()["metrics"]["assessment_scope"]
        assert scope == {
            "rows_in_export": 764,
            "summary_rows_excluded": 107,
            "activities_assessed": 657,
            "source_format": "msproject_csv",
        }
