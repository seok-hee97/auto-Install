import os
import subprocess
import time

from pywinauto import Desktop

from config import SILENT_COMMANDS
from utils import set_windows_error_mode, terminate_installation_process, close_windows


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
            print("No windows found. check_installation_window() return False.")
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

            print("check_install_window : ", window)

            for keyword in installation_keywords:
                if keyword in title:
                    return True

        return False
    except Exception as e:
        print(f"Error while checking installation window: {str(e)}")
        return False


def run_silent_install(file_path, installer_type, timeout_sec=180):

    if installer_type not in SILENT_COMMANDS:
        print(f"Unknown installer type or no silent option available for: {file_path}")
        return False

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
            process.kill()
            print(f"Silent Installation failed : Install window detected for {file_path}. Silent installation not supported.")
            time.sleep(5)
            terminate_installation_process(file_path)
            time.sleep(3)
            close_windows()
            time.sleep(3)
            return False

        try:
            stdout, stderr = process.communicate(timeout=timeout_sec)
            if process.returncode == 0:
                print(f"Successfully silent installed: {file_path}")
                return True
            else:
                print(f"Silent Installation failed: {file_path}. Error: {stderr.decode()}")
                terminate_installation_process(file_path)
                close_windows()
                return False
        except subprocess.TimeoutExpired:
            process.kill()
            terminate_installation_process(file_path)
            close_windows()
            print(f"Silent Installation timed out: {file_path}")
            return False

    except Exception as e:
        print(f"Error occurred while installing {file_path}: {str(e)}")
        return False
