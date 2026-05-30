import logging
import os
import subprocess
import time

from pywinauto import Desktop

from config import SILENT_COMMANDS, PASS_WINDOW, INSTALLATION_KEYWORDS
from utils import set_windows_error_mode, terminate_process_tree, close_windows

# Windows-only subprocess flag; falls back to 0 on non-Windows
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

logger = logging.getLogger(__name__)

MSI_TYPES = {"Microsoft Installer(MSI)", "Windows Installer"}
MSI_SUCCESS_CODES = {0, 3010}


def check_installation_window():
    try:
        desktop = Desktop(backend="uia")
        windows = desktop.windows()

        if not windows:
            logger.debug("No windows found in check_installation_window()")
            return False

        for window in windows:
            title = window.window_text().lower()
            if any(p in title for p in PASS_WINDOW):
                continue
            logger.debug("check_install_window: %s", window)
            if any(k in title for k in INSTALLATION_KEYWORDS):
                return True

        return False
    except Exception as e:
        logger.warning("Error while checking installation window: %s", e)
        return False


def run_silent_install(file_path, installer_type, timeout_sec=180):

    if installer_type not in SILENT_COMMANDS:
        logger.info("No silent option for %s (%s)", file_path, installer_type)
        return False

    if installer_type in MSI_TYPES:
        command = ["msiexec.exe", "/i", file_path, "/qn", "/norestart"]
    else:
        command = [file_path] + SILENT_COMMANDS[installer_type]

    set_windows_error_mode()

    try:
        process = subprocess.Popen(
            command,
            creationflags=_CREATE_NO_WINDOW,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # 고정 sleep 대신 폴링: 0.5s 간격으로 최대 8s 동안
        # 프로세스가 먼저 종료되면 즉시 빠져나오고,
        # 에러 창이 나타나면 즉시 캐치한다.
        _POLL_INTERVAL = 0.5
        _POLL_TIMEOUT = 8.0
        poll_start = time.time()
        while time.time() - poll_start < _POLL_TIMEOUT:
            if process.poll() is not None:
                break  # 이미 종료 — communicate()로 결과 수집
            if check_installation_window():
                terminate_process_tree(process.pid)
                logger.info("Silent install failed (window detected): %s", file_path)
                time.sleep(5)
                close_windows()
                time.sleep(3)
                return False
            time.sleep(_POLL_INTERVAL)

        try:
            stdout, stderr = process.communicate(timeout=timeout_sec)
            success_codes = MSI_SUCCESS_CODES if installer_type in MSI_TYPES else {0}
            if process.returncode in success_codes:
                logger.info("Silent install succeeded: %s", file_path)
                return True
            else:
                logger.warning("Silent install failed (rc=%d): %s — %s",
                               process.returncode, file_path, stderr.decode(errors="replace"))
                terminate_process_tree(process.pid)
                close_windows()
                return False
        except subprocess.TimeoutExpired:
            terminate_process_tree(process.pid)
            close_windows()
            logger.warning("Silent install timed out: %s", file_path)
            return False

    except Exception as e:
        logger.error("Error during silent install %s: %s", file_path, e)
        return False
