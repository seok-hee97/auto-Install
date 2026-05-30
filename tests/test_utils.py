"""Tests for utils.py — classify_installer, verify_folder, note_file_txt."""
import json
import os
import subprocess
import pytest
from unittest.mock import patch, MagicMock
import psutil

from utils import classify_installer, verify_folder, note_file_txt, terminate_process_tree


# ---------------------------------------------------------------------------
# classify_installer
# ---------------------------------------------------------------------------

def _die_json(filetype, value_type, value_name):
    return json.dumps({
        "detects": [{
            "filetype": filetype,
            "values": [{"type": value_type, "name": value_name}]
        }]
    }).encode()


class TestClassifyInstaller:
    """All tests mock os.path.exists=True so the diec.exe path check is bypassed."""

    @pytest.fixture(autouse=True)
    def _diec_exists(self):
        with patch("utils.os.path.exists", return_value=True):
            yield

    @patch("utils.subprocess.run")
    def test_inno_setup(self, mock_run):
        mock_run.return_value.stdout = _die_json("PE", "Installer", "Inno Setup")
        assert classify_installer("fake.exe") == "Inno Setup"

    @patch("utils.subprocess.run")
    def test_nsis(self, mock_run):
        mock_run.return_value.stdout = _die_json("PE", "Installer", "NSIS")
        assert classify_installer("fake.exe") == "NSIS"

    @patch("utils.subprocess.run")
    def test_msi(self, mock_run):
        mock_run.return_value.stdout = _die_json("PE", "Installer", "MSI")
        assert classify_installer("fake.exe") == "Microsoft Installer(MSI)"

    @patch("utils.subprocess.run")
    def test_7z_sfx(self, mock_run):
        mock_run.return_value.stdout = _die_json("PE", "SFX", "7-Zip")
        assert classify_installer("fake.exe") == "7z installer"

    @patch("utils.subprocess.run")
    def test_unknown_sfx_returns_zip(self, mock_run):
        mock_run.return_value.stdout = _die_json("PE", "SFX", "WinRAR")
        assert classify_installer("fake.exe") == "zip"

    @patch("utils.subprocess.run")
    def test_cab_filetype_returns_zip(self, mock_run):
        mock_run.return_value.stdout = json.dumps({
            "detects": [{"filetype": "cab", "values": []}]
        }).encode()
        assert classify_installer("fake.exe") == "zip"

    @patch("utils.subprocess.run")
    def test_archive_filetype_returns_zip(self, mock_run):
        mock_run.return_value.stdout = json.dumps({
            "detects": [{"filetype": "archive", "values": []}]
        }).encode()
        assert classify_installer("fake.exe") == "zip"

    @patch("utils.subprocess.run")
    def test_unknown_installer(self, mock_run):
        mock_run.return_value.stdout = json.dumps({
            "detects": [{"filetype": "PE", "values": [{"type": "Compiler", "name": "MSVC"}]}]
        }).encode()
        assert classify_installer("fake.exe") == "Unknown"

    @patch("utils.subprocess.run")
    def test_invalid_json_returns_error(self, mock_run):
        mock_run.return_value.stdout = b"not valid json"
        assert classify_installer("fake.exe") == "Error"

    @patch("utils.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="x", timeout=60))
    def test_timeout_returns_timeout(self, mock_run):
        assert classify_installer("fake.exe") == "Timeout"

    def test_missing_diec_returns_error(self, tmp_path):
        # Bypass the autouse fixture for this one test — use a nonexistent path
        with patch("utils.os.path.exists", return_value=False):
            result = classify_installer("fake.exe", exe_path=str(tmp_path / "nonexistent.exe"))
        assert result == "Error"

    @patch("utils.subprocess.run")
    def test_installshield(self, mock_run):
        mock_run.return_value.stdout = _die_json("PE", "Installer", "InstallShield")
        assert classify_installer("fake.exe") == "InstallShield"

    @patch("utils.subprocess.run")
    def test_wix(self, mock_run):
        mock_run.return_value.stdout = _die_json("PE", "Installer", "WiX")
        assert classify_installer("fake.exe") == "WIX Toolset installer"

    @patch("utils.subprocess.run")
    def test_wise_installer(self, mock_run):
        mock_run.return_value.stdout = _die_json("PE", "Installer", "Wise Installer")
        assert classify_installer("fake.exe") == "Wise Installer"

    @patch("utils.subprocess.run")
    def test_case_insensitive_die_name(self, mock_run):
        # DIE may return "inno setup" in mixed case
        mock_run.return_value.stdout = _die_json("PE", "Installer", "inno setup")
        assert classify_installer("fake.exe") == "Inno Setup"


# ---------------------------------------------------------------------------
# verify_folder
# ---------------------------------------------------------------------------

class TestVerifyFolder:
    def test_nonexistent_folder_returns_minus_one(self, tmp_path):
        result = verify_folder(str(tmp_path / "does_not_exist"))
        assert result == -1

    @patch("utils.classify_installer")
    def test_counts_known_installers(self, mock_classify, tmp_path):
        (tmp_path / "setup.exe").write_bytes(b"MZ fake")
        (tmp_path / "app.msi").write_bytes(b"MZ fake")
        mock_classify.return_value = "Inno Setup"
        count = verify_folder(str(tmp_path))
        assert count == 2

    @patch("utils.classify_installer")
    def test_skips_unknown_installers(self, mock_classify, tmp_path):
        (tmp_path / "setup.exe").write_bytes(b"MZ fake")
        mock_classify.return_value = "Unknown"
        count = verify_folder(str(tmp_path))
        assert count == 0

    @patch("utils.classify_installer")
    def test_skips_non_exe_msi(self, mock_classify, tmp_path):
        (tmp_path / "readme.txt").write_text("hello")
        count = verify_folder(str(tmp_path))
        mock_classify.assert_not_called()
        assert count == 0

    @patch("utils.classify_installer")
    def test_empty_folder_returns_zero(self, mock_classify, tmp_path):
        count = verify_folder(str(tmp_path))
        assert count == 0

    @patch("utils.classify_installer")
    def test_error_type_not_counted(self, mock_classify, tmp_path):
        (tmp_path / "setup.exe").write_bytes(b"MZ fake")
        mock_classify.return_value = "Error"
        count = verify_folder(str(tmp_path))
        assert count == 0

    @patch("utils.classify_installer")
    def test_timeout_type_not_counted(self, mock_classify, tmp_path):
        (tmp_path / "setup.exe").write_bytes(b"MZ fake")
        mock_classify.return_value = "Timeout"
        count = verify_folder(str(tmp_path))
        assert count == 0


# ---------------------------------------------------------------------------
# note_file_txt
# ---------------------------------------------------------------------------

class TestNoteFileTxt:
    def test_creates_file_and_writes(self, tmp_path):
        log = str(tmp_path / "log.txt")
        with patch("utils.LOG_FILE", log):
            note_file_txt("C:\\test.exe", title="[failed]")
        assert os.path.exists(log)
        content = open(log).read()
        assert "C:\\test.exe" in content
        assert "[failed]" in content

    def test_appends_multiple_entries(self, tmp_path):
        log = str(tmp_path / "log.txt")
        with patch("utils.LOG_FILE", log):
            note_file_txt("file1.exe", title="[A]")
            note_file_txt("file2.exe", title="[B]")
        lines = open(log).readlines()
        assert len(lines) == 2
        assert "file1.exe" in lines[0]
        assert "file2.exe" in lines[1]

    def test_no_title(self, tmp_path):
        log = str(tmp_path / "log.txt")
        with patch("utils.LOG_FILE", log):
            note_file_txt("path.exe")
        assert "path.exe" in open(log).read()


# ---------------------------------------------------------------------------
# terminate_process_tree
# ---------------------------------------------------------------------------

class TestTerminateProcessTree:
    def test_no_such_process_returns_false(self):
        with patch("utils.psutil.Process", side_effect=psutil.NoSuchProcess(pid=99999)):
            result = terminate_process_tree(99999)
        assert result is False

    def test_successful_termination_returns_true(self):
        mock_proc = MagicMock()
        mock_proc.children.return_value = []
        mock_proc.wait.return_value = None
        with patch("utils.psutil.Process", return_value=mock_proc):
            with patch("utils.psutil.wait_procs", return_value=([], [])):
                result = terminate_process_tree(12345)
        assert result is True
        mock_proc.terminate.assert_called_once()
