"""Schedule parsing: date handling, validation, relationships and robustness."""

import pandas as pd
import pytest

from src.parsers.schedule_parser import ScheduleParser


def parse(content, name="test.csv"):
    return ScheduleParser().parse_csv(content, name)


def activities(result):
    return pd.DataFrame(result["activities"])


class TestDateOrderDetection:
    """
    Regression tests for silent date corruption.

    pandas infers a datetime format from the first non-null value only. Given a
    day-first export whose first date happens to be ambiguous, it locked in
    month-first for the entire column: 03/04/2025 was read as 4 March instead
    of 3 April, and unambiguous day-first values like 29/08/2025 became NaT and
    disappeared from the schedule entirely.
    """

    def test_day_first_detected_despite_ambiguous_first_row(self, csv_builder):
        build_csv, build_row = csv_builder
        content = build_csv([
            build_row("A1", start="03/04/2025 08:00", finish="10/04/2025 17:00"),
            build_row("A2", start="29/08/2025 08:00", finish="05/09/2025 17:00"),
        ])
        df = activities(parse(content))

        assert df.loc[0, "Start"] == pd.Timestamp("2025-04-03 08:00")
        assert df.loc[1, "Start"] == pd.Timestamp("2025-08-29 08:00")

    def test_no_dates_are_silently_dropped(self, csv_builder):
        build_csv, build_row = csv_builder
        content = build_csv([
            build_row("A1", start="03/04/2025 08:00", finish="10/04/2025 17:00"),
            build_row("A2", start="29/08/2025 08:00", finish="05/09/2025 17:00"),
        ])
        df = activities(parse(content))
        assert df["Start"].isna().sum() == 0
        assert df["Finish"].isna().sum() == 0

    def test_month_first_export_is_detected(self, csv_builder):
        build_csv, build_row = csv_builder
        content = build_csv([
            build_row("A1", start="04/03/2025 08:00", finish="04/10/2025 17:00"),
            build_row("A2", start="08/29/2025 08:00", finish="09/05/2025 17:00"),
        ])
        df = activities(parse(content))

        assert df.loc[0, "Start"] == pd.Timestamp("2025-04-03 08:00")
        assert df.loc[1, "Start"] == pd.Timestamp("2025-08-29 08:00")

    def test_iso_dates_are_not_reinterpreted(self, csv_builder):
        """dayfirst applies to year-first strings too, so ISO must bypass it."""
        build_csv, build_row = csv_builder
        content = build_csv([
            build_row("A1", start="2025-04-03", finish="2025-04-10"),
        ])
        df = activities(parse(content))
        assert df.loc[0, "Start"] == pd.Timestamp("2025-04-03")

    def test_fully_ambiguous_file_warns(self, csv_builder):
        build_csv, build_row = csv_builder
        content = build_csv([build_row("A1", start="03/04/2025", finish="05/06/2025")])
        result = parse(content)
        assert any("ambiguous" in w.lower() for w in result["warnings"])

    def test_mixed_orders_are_reported_as_inconsistent(self, csv_builder):
        build_csv, build_row = csv_builder
        content = build_csv([
            build_row("A1", start="29/08/2025", finish="30/08/2025"),
            build_row("A2", start="08/29/2025", finish="12/31/2025"),
        ])
        result = parse(content)
        assert any("inconsistent" in w.lower() for w in result["warnings"])

    def test_configuration_overrides_detection(self, csv_builder, monkeypatch):
        monkeypatch.setenv("APP_DATE_ORDER", "month")
        build_csv, build_row = csv_builder
        content = build_csv([build_row("A1", start="03/04/2025", finish="05/06/2025")])
        df = activities(parse(content))
        assert df.loc[0, "Start"] == pd.Timestamp("2025-03-04")

    def test_unparseable_dates_are_reported(self, csv_builder):
        build_csv, build_row = csv_builder
        content = build_csv([
            build_row("A1", start="not-a-date", finish="29/08/2025"),
            build_row("A2", start="30/08/2025", finish="31/08/2025"),
        ])
        result = parse(content)
        assert any("could not be read as a date" in w for w in result["warnings"])

    def test_blank_dates_are_allowed_without_warning(self, csv_builder):
        build_csv, build_row = csv_builder
        content = build_csv([
            build_row("A1", start="29/08/2025", finish=""),
            build_row("A2", start="30/08/2025", finish="31/08/2025"),
        ])
        result = parse(content)
        assert result["success"]
        assert not any("could not be read as a date" in w for w in result["warnings"])


class TestInputValidation:
    @pytest.mark.parametrize("label,content", [
        ("empty file", b""),
        ("headers only", ("Activity ID,Activity Name,Activity Status,Start,Finish,"
                          "Total Float,Duration Type\n").encode()),
        ("binary junk", b"\x00\x01\x02\x03 not a csv"),
        ("wrong columns", b"foo,bar\n1,2\n"),
    ])
    def test_unusable_input_is_rejected_with_a_message(self, label, content):
        result = parse(content)
        assert result["success"] is False, f"{label} was accepted"
        assert result["errors"], f"{label} produced no error message"

    def test_oversized_file_is_rejected(self, csv_builder, monkeypatch):
        monkeypatch.setenv("APP_MAX_UPLOAD_MB", "0")
        build_csv, build_row = csv_builder
        result = parse(build_csv([build_row("A1")]))
        assert result["success"] is False
        assert any("exceeds" in e for e in result["errors"])

    def test_too_many_activities_is_rejected(self, csv_builder, monkeypatch):
        monkeypatch.setenv("APP_MAX_ACTIVITIES", "2")
        build_csv, build_row = csv_builder
        result = parse(build_csv([build_row(f"A{i}") for i in range(5)]))
        assert result["success"] is False
        assert any("exceeds the supported maximum" in e for e in result["errors"])

    def test_duplicate_columns_are_rejected(self):
        content = (b"Activity ID,Activity Name,Activity Status,Start,Finish,"
                   b"Total Float,Duration Type,Total Float\n"
                   b"A1,T,Not Started,01/03/2025,02/03/2025,0,Fixed,0\n")
        result = parse(content)
        assert result["success"] is False
        assert any("duplicate column" in e.lower() for e in result["errors"])

    def test_missing_required_columns_are_named(self):
        content = b"Activity ID,Activity Name\nA1,Task\n"
        result = parse(content)
        assert result["success"] is False
        assert "Total Float" in result["errors"][0]

    def test_cp1252_encoding_is_handled(self, csv_builder):
        """P6 on Windows commonly exports cp1252 rather than UTF-8."""
        build_csv, build_row = csv_builder
        content = build_csv([build_row("A1", name="Café Ünit")])
        content = content.decode("utf-8").encode("cp1252")
        result = parse(content)
        assert result["success"], result.get("errors")
        assert activities(result).loc[0, "Activity Name"] == "Café Ünit"

    def test_utf8_bom_is_stripped(self, csv_builder):
        build_csv, build_row = csv_builder
        content = b"\xef\xbb\xbf" + build_csv([build_row("A1")])
        result = parse(content)
        assert result["success"], result.get("errors")
        assert "Activity ID" in activities(result).columns

    def test_p6_unit_suffixes_are_normalised(self):
        content = (b"Activity ID,Activity Name,Activity Status,Start,Finish,"
                   b"Total Float(d),Duration Type,At Completion Duration(d)\n"
                   b"A1,T,Not Started,29/08/2025,30/08/2025,5,Fixed,10\n")
        result = parse(content)
        assert result["success"], result.get("errors")
        df = activities(result)
        assert "Total Float" in df.columns
        assert df.loc[0, "Total Float"] == 5


class TestRelationships:
    def test_full_format_relationships_are_parsed(self, csv_builder):
        build_csv, build_row = csv_builder
        content = build_csv([
            build_row("A1", predecessors="", successors="A2: FS"),
            build_row("A2", predecessors="A1: FF 10,A3: FS -5", successors=""),
            build_row("A3", predecessors="", successors="A2: FS -5"),
        ])
        df = activities(parse(content))

        predecessors = df.loc[1, "predecessor_list"]
        assert {"activity": "A1", "type": "FF", "lag": 10} in predecessors
        assert {"activity": "A3", "type": "FS", "lag": -5} in predecessors

    def test_negative_and_positive_lags_are_counted(self, csv_builder):
        build_csv, build_row = csv_builder
        content = build_csv([
            build_row("A1", predecessors="A2: FS -5,A3: FS 10,A4: FS"),
        ])
        df = activities(parse(content))
        assert df.loc[0, "negative_lag_count"] == 1
        assert df.loc[0, "positive_lag_count"] == 1

    def test_missing_logic_flags(self, csv_builder):
        build_csv, build_row = csv_builder
        content = build_csv([
            build_row("A1", predecessors="", successors=""),
            build_row("A2", predecessors="A1: FS", successors="A3: FS"),
        ])
        df = activities(parse(content))
        assert bool(df.loc[0, "missing_logic"]) is True
        assert bool(df.loc[1, "missing_logic"]) is False

    def test_missing_relationship_columns_warn_loudly(self):
        content = (b"Activity ID,Activity Name,Activity Status,Start,Finish,"
                   b"Total Float,Duration Type\n"
                   b"A1,T,Not Started,29/08/2025,30/08/2025,0,Fixed\n")
        result = parse(content)
        assert result["success"]
        assert any("CRITICAL" in w for w in result["warnings"])


class TestConstraints:
    @pytest.mark.parametrize("constraint,expected", [
        ("Must Start On", "Hard"),
        ("Must Finish On", "Hard"),
        ("Start On or After", "Flexible"),
        ("As Late As Possible", "Schedule-Driven"),
        ("", "None"),
    ])
    def test_constraints_are_categorised(self, csv_builder, constraint, expected):
        build_csv, build_row = csv_builder
        content = build_csv([build_row("A1", constraint=constraint)])
        df = activities(parse(content))
        assert df.loc[0, "constraint_category"] == expected


class TestRealFiles:
    def test_sample_schedule_parses(self, sample_csv_bytes):
        result = parse(sample_csv_bytes, "sample_schedule.csv")
        assert result["success"], result.get("errors")
        assert result["total_activities"] == 28

    def test_real_export_parses(self, real_export_bytes):
        result = parse(real_export_bytes, "Schedule export.csv")
        assert result["success"], result.get("errors")
        assert result["total_activities"] == 1261

        df = activities(result)
        # Day-first export: the earliest start must not land in the future or
        # be shifted by a month-first misread.
        assert df["Start"].min() == pd.Timestamp("2022-04-29")
        assert pd.api.types.is_datetime64_any_dtype(df["Start"])

    def test_metadata_is_populated(self, sample_csv_bytes):
        metadata = parse(sample_csv_bytes)["metadata"]
        assert metadata["total_activities"] == 28
        assert metadata["has_wbs"] is True
        assert metadata["date_range"]["start"] is not None
