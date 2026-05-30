"""Tests for silent_mode.py — check_installation_window and run_silent_install."""
import subprocess
import pytest
from unittest.mock import MagicMock, patch

from silent_mode import check_installation_window, run_silent_install


# ---------------------------------------------------------------------------
# check_installation_window
# ---------------------------------------------------------------------------

def _mock_desktop_with_windows(titles):
    """Return a mocked Desktop whose .windows() returns windows with given titles."""
    windows = []
    for t in titles:
        w = MagicMock()
        w.window_text.return_value = t
        windows.append(w)
    desktop = MagicMock()
    desktop.windows.return_value = windows
    return desktop


class TestCheckInstallationWindow:
    def test_installer_window_detected(self):
        desktop = _mock_desktop_with_windows(["Setup Wizard"])
        with patch("silent_mode.Desktop", return_value=desktop):
            assert check_installation_window() is True

    def test_install_keyword_detected(self):
        desktop = _mock_desktop_with_windows(["Install Progress"])
        with patch("silent_mode.Desktop", return_value=desktop):
            assert check_installation_window() is True

    def test_pass_window_skipped(self):
        desktop = _mock_desktop_with_windows(["명령 프롬프트"])
        with patch("silent_mode.Desktop", return_value=desktop):
            assert check_installation_window() is False

    def test_unrelated_window_not_detected(self):
        desktop = _mock_desktop_with_windows(["Notepad", "Calculator"])
        with patch("silent_mode.Desktop", return_value=desktop):
            assert check_installation_window() is False

    def test_no_windows_returns_false(self):
        desktop = _mock_desktop_with_windows([])
        with patch("silent_mode.Desktop", return_value=desktop):
            assert check_installation_window() is False

    def test_exception_returns_false(self):
        with patch("silent_mode.Desktop", side_effect=Exception("COM error")):
            assert check_installation_window() is False

    def test_nsis_keyword_detected(self):
        desktop = _mock_desktop_with_windows(["NSIS Installer"])
        with patch("silent_mode.Desktop", return_value=desktop):
            assert check_installation_window() is True

    def test_mixed_pass_and_install_windows(self):
        desktop = _mock_desktop_with_windows(["작업 표시줄", "Setup Wizard"])
        with patch("silent_mode.Desktop", return_value=desktop):
            assert check_installation_window() is True


# ---------------------------------------------------------------------------
# run_silent_install
# ---------------------------------------------------------------------------

class TestRunSilentInstall:
    def test_unknown_type_returns_false(self):
        result = run_silent_install("fake.exe", "Unknown")
        assert result is False

    def test_zip_type_returns_false(self):
        result = run_silent_install("fake.exe", "zip")
        assert result is False

    @patch("silent_mode.subprocess.Popen")
    def test_success_return_code_zero(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.pid = 1234
        mock_proc.poll.return_value = 0       # 즉시 종료 → 폴링 루프 break
        mock_proc.communicate.return_value = (b"", b"")
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        result = run_silent_install("fake.exe", "Inno Setup", timeout_sec=5)

        assert result is True

    @patch("silent_mode.subprocess.Popen")
    def test_nonzero_return_code_returns_false(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.pid = 1234
        mock_proc.poll.return_value = 1
        mock_proc.communicate.return_value = (b"", b"error")
        mock_proc.returncode = 1
        mock_popen.return_value = mock_proc

        result = run_silent_install("fake.exe", "NSIS", timeout_sec=5)

        assert result is False

    @patch("silent_mode.subprocess.Popen")
    def test_msi_success_code_3010(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.pid = 1234
        mock_proc.poll.return_value = 3010
        mock_proc.communicate.return_value = (b"", b"")
        mock_proc.returncode = 3010  # reboot required — still a success
        mock_popen.return_value = mock_proc

        result = run_silent_install("fake.exe", "Microsoft Installer(MSI)", timeout_sec=5)

        assert result is True

    @patch("silent_mode.check_installation_window", return_value=True)
    @patch("silent_mode.subprocess.Popen")
    @patch("silent_mode.terminate_process_tree")
    @patch("silent_mode.close_windows")
    def test_install_window_detected_returns_false(
        self, mock_close, mock_terminate, mock_popen, mock_check_win
    ):
        mock_proc = MagicMock()
        mock_proc.pid = 1234
        mock_proc.poll.return_value = None    # 아직 실행 중
        mock_popen.return_value = mock_proc

        result = run_silent_install("fake.exe", "NSIS", timeout_sec=5)

        assert result is False
        mock_terminate.assert_called_once_with(1234)

    @patch("silent_mode.check_installation_window", return_value=False)
    @patch("silent_mode.subprocess.Popen")
    @patch("silent_mode.terminate_process_tree")
    @patch("silent_mode.close_windows")
    def test_timeout_returns_false(self, mock_close, mock_terminate, mock_popen, mock_check_win):
        mock_proc = MagicMock()
        mock_proc.pid = 1234
        mock_proc.poll.return_value = 0
        mock_proc.communicate.side_effect = subprocess.TimeoutExpired(cmd="x", timeout=5)
        mock_popen.return_value = mock_proc

        result = run_silent_install("fake.exe", "Inno Setup", timeout_sec=5)

        assert result is False
        mock_terminate.assert_called()

    @patch("silent_mode.subprocess.Popen")
    def test_process_exits_early_skips_full_poll_timeout(self, mock_popen):
        """프로세스가 폴링 중 종료되면 8s를 다 기다리지 않고 바로 communicate로 넘어간다."""
        mock_proc = MagicMock()
        mock_proc.pid = 1234
        mock_proc.poll.return_value = 0       # 첫 poll에서 즉시 종료
        mock_proc.communicate.return_value = (b"", b"")
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        import time as _time
        start = _time.time()
        result = run_silent_install("fake.exe", "Inno Setup", timeout_sec=10)
        elapsed = _time.time() - start

        assert result is True
        assert elapsed < 2.0, f"Should exit early, not wait 8s (took {elapsed:.1f}s)"
