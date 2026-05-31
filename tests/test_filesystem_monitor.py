"""Tests for filesystem_monitor.py — noise filtering and event handling."""
import os
import pytest
from unittest.mock import MagicMock, patch, call
from queue import Queue

from filesystem_monitor import _is_noise, wait_until_stable, InstallationMonitor


class TestIsNoise:
    """_is_noise() should return True for temp/cache/log files, False for real files."""

    # --- should be noise ---
    @pytest.mark.parametrize("path", [
        r"C:\Windows\Temp\abc.tmp",
        r"C:\Users\user\AppData\Local\Temp\setup123.log",
        r"C:\Windows\System32\winevt\Logs\System.etl",
        r"C:\path\to\something.db-journal",
        r"C:\file.part",
        r"C:\download.crdownload",
        r"C:\file.bak",
        r"C:\AppData\Local\Google\Chrome\User Data\Default\Cache\cache.db",
        r"C:\AppData\Local\Microsoft\Edge\User Data\data.dat",
        r"C:\AppData\Local\Microsoft\Windows\INetCache\IE\file.dat",
        r"C:\AppData\Roaming\Microsoft\Windows\Recent\file.lnk",
    ])
    def test_noise_paths(self, path):
        assert _is_noise(path) is True, f"Expected noise: {path}"

    # --- should NOT be noise ---
    @pytest.mark.parametrize("path", [
        r"C:\Program Files\MyApp\app.exe",
        r"C:\Program Files\MyApp\resources\icon.png",
        r"C:\ProgramData\MyApp\config.ini",
        r"C:\Users\user\AppData\Local\MyApp\data.db",
        r"C:\Windows\System32\notepad.exe",
        r"C:\MyApp\installer.msi",
    ])
    def test_non_noise_paths(self, path):
        assert _is_noise(path) is False, f"Should not be noise: {path}"

    def test_case_insensitive(self):
        assert _is_noise(r"C:\WINDOWS\TEMP\file.TMP") is True
        assert _is_noise(r"C:\PROGRAM FILES\APP\BINARY.EXE") is False

    def test_log_extension_is_noise(self):
        assert _is_noise(r"C:\anywhere\debug.log") is True

    def test_lock_extension_is_noise(self):
        assert _is_noise(r"C:\anywhere\db.lock") is True


class TestWaitUntilStable:
    def test_returns_true_after_size_stabilizes(self):
        with patch("filesystem_monitor.os.path.getsize", side_effect=[10, 20, 20, 20]), \
             patch("filesystem_monitor.time.sleep"):
            assert wait_until_stable("file.bin", timeout=5, interval=0.1) is True

    def test_returns_false_when_file_disappears(self):
        with patch("filesystem_monitor.os.path.getsize", side_effect=OSError), \
             patch("filesystem_monitor.time.sleep"):
            assert wait_until_stable("missing.bin", timeout=5, interval=0.1) is False


class TestInstallationMonitorOnCreated:
    """on_created() should enqueue real files and skip noise."""

    def _make_monitor(self, tmp_path):
        m = InstallationMonitor(
            source_path=str(tmp_path / "src"),
            destination_path=str(tmp_path / "dst"),
            excluded_paths=[str(tmp_path / "excluded")],
            manifest_path=None,
            collection_name="test",
        )
        m._stop_event.set()  # prevent background worker from running
        return m

    def _make_event(self, path, is_directory=False):
        ev = MagicMock()
        ev.src_path = path
        ev.is_directory = is_directory
        return ev

    def test_normal_file_enqueued(self, tmp_path):
        monitor = self._make_monitor(tmp_path)
        monitor.queue = MagicMock()
        ev = self._make_event(r"C:\Program Files\App\app.exe")
        monitor.on_created(ev)
        monitor.queue.put.assert_called_once()

    def test_noise_file_not_enqueued(self, tmp_path):
        monitor = self._make_monitor(tmp_path)
        monitor.queue = MagicMock()
        ev = self._make_event(r"C:\Windows\Temp\abc.tmp")
        monitor.on_created(ev)
        monitor.queue.put.assert_not_called()

    def test_excluded_path_not_enqueued(self, tmp_path):
        excluded = str(tmp_path / "excluded")
        monitor = self._make_monitor(tmp_path)
        monitor.queue = MagicMock()
        # Use the actual excluded path
        ev = self._make_event(os.path.join(excluded, "something.exe"))
        monitor.on_created(ev)
        monitor.queue.put.assert_not_called()

    def test_directory_not_noise_filtered(self, tmp_path):
        monitor = self._make_monitor(tmp_path)
        monitor.queue = MagicMock()
        ev = self._make_event(r"C:\Program Files\NewApp", is_directory=True)
        monitor.on_created(ev)
        monitor.queue.put.assert_called_once()

    def test_log_file_not_enqueued(self, tmp_path):
        monitor = self._make_monitor(tmp_path)
        monitor.queue = MagicMock()
        ev = self._make_event(r"C:\Somewhere\install.log")
        monitor.on_created(ev)
        monitor.queue.put.assert_not_called()
