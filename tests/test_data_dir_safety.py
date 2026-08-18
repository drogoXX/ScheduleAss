"""The app must flag a data directory that will corrupt a live database.

A OneDrive-hosted database caused repeated Streamlit session loss with no
server-side error at all. This check turns that class of failure into a startup
warning. See docs/TECHNICAL_SPECIFICATION_v2.md §5.6.
"""

import pytest

from src.config import data_dir_warnings


def warnings_for(path, monkeypatch):
    monkeypatch.setenv("APP_DATA_DIR", str(path))
    return data_dir_warnings()


class TestSyncedFolderDetection:
    @pytest.mark.parametrize("path", [
        r"C:\Users\Someone\OneDrive\App\instance",
        r"C:\Users\Someone\Dropbox\data",
        r"C:\Users\Someone\Google Drive\app",
        r"/home/someone/Nextcloud/scheduleass",
    ])
    def test_synced_locations_are_flagged(self, path, monkeypatch):
        problems = warnings_for(path, monkeypatch)
        assert problems, f"{path} should be flagged"
        assert "APP_DATA_DIR" in " ".join(problems)

    def test_ordinary_local_path_is_clean(self, tmp_path, monkeypatch):
        assert warnings_for(tmp_path / "runtime", monkeypatch) == []

    def test_detection_is_case_insensitive(self, monkeypatch):
        assert warnings_for(r"C:\Users\X\onedrive\data", monkeypatch)


class TestOtherUnsafeLocations:
    def test_unc_network_share_is_flagged(self, monkeypatch):
        problems = warnings_for(r"\\fileserver\share\scheduleass", monkeypatch)
        assert any("network share" in p for p in problems)

    def test_inside_the_repository_is_flagged(self, monkeypatch):
        from src.config import BASE_DIR
        problems = warnings_for(BASE_DIR / "instance", monkeypatch)
        assert any("code tree" in p for p in problems)


def test_warning_names_the_offending_path(monkeypatch):
    path = r"C:\Users\Someone\OneDrive\App\instance"
    problems = warnings_for(path, monkeypatch)
    assert any("OneDrive" in p for p in problems)
