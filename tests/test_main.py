"""Tests for main.py — load_completed_files, parallel_zip_phase, _zip_worker."""
import csv
import os
import datetime
import pytest
from unittest.mock import MagicMock, patch

from main import load_completed_files, _zip_worker, parallel_zip_phase, write_report


# ---------------------------------------------------------------------------
# load_completed_files
# ---------------------------------------------------------------------------

class TestLoadCompletedFiles:
    def _write_csv(self, path, rows):
        fieldnames = ["run_id", "file", "installer_type", "stage", "result", "elapsed_sec"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_returns_empty_set_for_missing_file(self, tmp_path):
        result = load_completed_files(str(tmp_path / "nonexistent.csv"))
        assert result == set()

    def test_loads_success_rows_only(self, tmp_path):
        csv_path = str(tmp_path / "report.csv")
        self._write_csv(csv_path, [
            {"run_id": "r1", "file": "C:\\a.exe", "installer_type": "Inno Setup",
             "stage": "silent", "result": "success", "elapsed_sec": "1.0"},
            {"run_id": "r1", "file": "C:\\b.exe", "installer_type": "NSIS",
             "stage": "gui", "result": "failed", "elapsed_sec": "2.0"},
        ])
        result = load_completed_files(csv_path)
        assert "C:\\a.exe" in result
        assert "C:\\b.exe" not in result

    def test_loads_multiple_success_rows(self, tmp_path):
        csv_path = str(tmp_path / "report.csv")
        self._write_csv(csv_path, [
            {"run_id": "r1", "file": "C:\\a.exe", "installer_type": "Inno Setup",
             "stage": "silent", "result": "success", "elapsed_sec": "1.0"},
            {"run_id": "r1", "file": "C:\\b.exe", "installer_type": "NSIS",
             "stage": "silent", "result": "success", "elapsed_sec": "1.5"},
        ])
        result = load_completed_files(csv_path)
        assert "C:\\a.exe" in result
        assert "C:\\b.exe" in result

    def test_returns_empty_for_all_failed(self, tmp_path):
        csv_path = str(tmp_path / "report.csv")
        self._write_csv(csv_path, [
            {"run_id": "r1", "file": "C:\\a.exe", "installer_type": "NSIS",
             "stage": "gui", "result": "failed", "elapsed_sec": "2.0"},
        ])
        result = load_completed_files(csv_path)
        assert result == set()

    def test_handles_corrupt_csv_gracefully(self, tmp_path):
        csv_path = str(tmp_path / "report.csv")
        with open(csv_path, "w") as f:
            f.write("not valid csv content\n\x00\x01\x02")
        # Should not raise; returns empty or partial
        result = load_completed_files(csv_path)
        assert isinstance(result, set)


# ---------------------------------------------------------------------------
# _zip_worker
# ---------------------------------------------------------------------------

class TestZipWorker:
    @patch("main.process_seven_zip", return_value=True)
    @patch("main.classify_installer", return_value="7z installer")
    def test_zip_type_extracted_skip_sequential(self, mock_classify, mock_zip):
        res = _zip_worker("fake.exe", "run001")
        assert res["zip_success"] is True
        assert res["skip_sequential"] is True
        assert res["record"]["stage"] == "zip"
        assert res["record"]["result"] == "success"

    @patch("main.process_seven_zip", return_value=False)
    @patch("main.note_file_txt")
    @patch("main.classify_installer", return_value="7z installer")
    def test_zip_extraction_failed(self, mock_classify, mock_note, mock_zip):
        res = _zip_worker("fake.exe", "run001")
        assert res["zip_success"] is False
        assert res["record"]["result"] == "failed"
        mock_note.assert_called_once()

    @patch("main.classify_installer", return_value="Inno Setup")
    def test_non_zip_type_goes_to_sequential(self, mock_classify):
        res = _zip_worker("fake.exe", "run001")
        assert res["skip_sequential"] is False
        assert res["record"] is None

    @patch("main.note_file_txt")
    @patch("main.classify_installer", return_value="Error")
    def test_classify_error_skips_sequential(self, mock_classify, mock_note):
        res = _zip_worker("fake.exe", "run001")
        assert res["skip_sequential"] is True
        assert res["record"]["stage"] == "classify"
        assert res["record"]["result"] == "failed"

    @patch("main.note_file_txt")
    @patch("main.classify_installer", return_value="Timeout")
    def test_classify_timeout_skips_sequential(self, mock_classify, mock_note):
        res = _zip_worker("fake.exe", "run001")
        assert res["skip_sequential"] is True


# ---------------------------------------------------------------------------
# parallel_zip_phase
# ---------------------------------------------------------------------------

class TestParallelZipPhase:
    @patch("main._zip_worker")
    def test_non_zip_goes_to_pending(self, mock_worker):
        mock_worker.return_value = {
            "record": None,
            "installer_type": "Inno Setup",
            "zip_success": False,
            "skip_sequential": False,
        }
        zip_records, pending = parallel_zip_phase(["a.exe"], "run001", max_workers=1)
        assert len(pending) == 1
        assert pending[0][0] == "a.exe"
        assert len(zip_records) == 0

    @patch("main._zip_worker")
    def test_zip_success_goes_to_records(self, mock_worker):
        mock_worker.return_value = {
            "record": {"run_id": "r1", "file": "a.exe", "installer_type": "7z installer",
                       "stage": "zip", "result": "success", "elapsed_sec": 0.5},
            "installer_type": "7z installer",
            "zip_success": True,
            "skip_sequential": True,
        }
        zip_records, pending = parallel_zip_phase(["a.exe"], "run001", max_workers=1)
        assert len(zip_records) == 1
        assert len(pending) == 0

    @patch("main._zip_worker")
    def test_multiple_files_parallel(self, mock_worker):
        mock_worker.return_value = {
            "record": None,
            "installer_type": "NSIS",
            "zip_success": False,
            "skip_sequential": False,
        }
        files = ["a.exe", "b.exe", "c.exe"]
        zip_records, pending = parallel_zip_phase(files, "run001", max_workers=3)
        assert len(pending) == 3


# ---------------------------------------------------------------------------
# write_report
# ---------------------------------------------------------------------------

class TestWriteReport:
    def test_creates_report_file(self, tmp_path):
        report_path = str(tmp_path / "report.csv")
        records = [{
            "run_id": "r1", "file": "a.exe", "installer_type": "Inno Setup",
            "stage": "silent", "result": "success", "elapsed_sec": 1.0
        }]
        with patch("main.REPORT_PATH", report_path), \
             patch("main.REPORTS_DIR", str(tmp_path)):
            write_report(records)

        assert os.path.exists(report_path)
        with open(report_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]["result"] == "success"
        assert rows[0]["file"] == "a.exe"

    def test_appends_to_existing_report(self, tmp_path):
        report_path = str(tmp_path / "report.csv")
        records1 = [{"run_id": "r1", "file": "a.exe", "installer_type": "NSIS",
                     "stage": "silent", "result": "success", "elapsed_sec": 1.0}]
        records2 = [{"run_id": "r2", "file": "b.exe", "installer_type": "Inno Setup",
                     "stage": "gui", "result": "failed", "elapsed_sec": 2.0}]

        with patch("main.REPORT_PATH", report_path), \
             patch("main.REPORTS_DIR", str(tmp_path)):
            write_report(records1)
            write_report(records2)

        with open(report_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
