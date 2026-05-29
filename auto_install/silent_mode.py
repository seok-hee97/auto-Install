import logging
import os
import subprocess
import time

from pywinauto import Desktop

from config import SILENT_COMMANDS
from utils import set_windows_error_mode, terminate_process_tree, close_windows

logger = logging.getLogger(__name__)

MSI_TYPES = {"Microsoft Installer(MSI)", "Windows Installer"}
MSI_SUCCESS_CODES = {0, 3010}


def check_installation_window():

    try:
        desktop = Desktop(backend="uia")
        windows = desktop.windows()

        installation_keywords = [
            # eng
            "setup", "install", "installer",
            "wizard", "inno", "nsis", "msi",
            # kor
            "설치", "마법사"
        ]

        pass_window = ['명령 프롬프트', 'sublime', 'program manager', '작업 표시줄']

        if len(windows) == 0:
            logger.debug("No windows found in check_installation_window()")
            return False

        for window in windows:
            title = window.window_text().lower()

            skip_window = False
            for program in pass_window:
                if program in title:
                    skip_window = True
                    break

            if skip_window:
                continue

            logger.debug("check_install_window: %s", window)

            for keyword in installation_keywords:
                if keyword in title:
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
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        time.sleep(5)

        if check_installation_window():
            terminate_process_tree(process.pid)
            logger.info("Silent install failed (window detected): %s", file_path)
            time.sleep(5)
            close_windows()
            time.sleep(3)
            return False

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
