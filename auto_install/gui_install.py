import logging
import os
import time

from pywinauto import Desktop
from pywinauto import Application
import psutil

from utils import set_windows_error_mode, terminate_process_tree, close_windows

logger = logging.getLogger(__name__)

COMPLETION_KEYWORDS = [
    "finish", "completed", "complete", "done", "close",
    "마침", "완료", "종료",
    "fertig", "beenden",
]

DANGER_KEYWORDS = [
    "uninstall", "remove", "deinstallieren", "entfernen",
    "restart now", "reboot now", "jetzt neu starten",
]


def wait_for_progress(window, timeout=30):
    start_time = time.time()
    try:
        for progress in window.descendants(control_type="ProgressBar"):
            if progress.is_visible():
                logger.info("Waiting for progress bar")
                while progress.is_visible() and get_progress_value(progress) < 100:
                    value = get_progress_value(progress)
                    logger.debug("Progress: %d%%", value)
                    time.sleep(2)

                    if time.time() - start_time > timeout:
                        logger.warning("Progress bar timeout reached")
                        break

                    if not progress.is_visible():
                        logger.debug("Progress bar no longer visible")
                        break

                logger.info("Progress completed or window closed")
    except Exception as e:
        logger.warning("Progress bar handling error: %s", e)


def get_progress_value(progress):

    try:
        properties = progress.legacy_properties()
        if 'Value' in properties:
            return int(properties['Value'].rstrip('%'))
        else:
            return 0
    except ValueError:
        logger.warning("Invalid progress value")
        return 0
    except Exception as e:
        logger.warning("Error getting progress value: %s", e)
        return 0


def click_button(window):

    clicks = [
        # eng
        "next", "install", "finish", "ok", "yes", "accept", "agree",
        "run", "i agree", "continue", "done", "close",
        "enable", "retry", "don't send", "don't save",
        "continue", "unzip", "open", "close the program", "save",
        "later", "end", "keep", "allow access", "remind me later", "select", "select all",
        "ignore",
        # kor
        "예", "예(Y)", "마침", "확인", "설치", "다음", "완료", "동의", "무시", "종료", "종료(f)", "계속",
        # german
        "ja", "weiter", "akzeptieren", "ende", "starten", "jetzt starten",
        "neustarten", "neu starten", "jetzt neu starten", "beenden", "oeffnen",
        "schliessen", "installation weiterfuhren", "fertig", "beenden",
        "fortsetzen", "fortfahren", "stimme zu", "zustimmen", "senden",
        "nicht senden", "speichern", "nicht speichern", "ausfuehren",
        "spaeter", "einverstanden",
        # ru
        "установить",
    ]
    clicked_completion = False
    try:
        for button in window.descendants(control_type="Button"):
            button_text = button.window_text().lower()

            if any(danger in button_text for danger in DANGER_KEYWORDS):
                logger.info("Skipping dangerous button: %s", button_text)
                continue

            for click in clicks:
                if click in button_text:
                    logger.info("Clicking button: %s", button_text)
                    button.click_input()
                    if any(keyword in button_text for keyword in COMPLETION_KEYWORDS):
                        clicked_completion = True
                    break

    except Exception as e:
        logger.warning("Button handling error: %s", e)
    return clicked_completion


def check_checkbox(window):

    try:
        for checkbox in window.descendants(control_type="CheckBox"):
            logger.debug("Checkbox: %s", checkbox.window_text())
            try:
                state = checkbox.get_toggle_state()
            except Exception:
                state = None
            if state == 0:
                checkbox.click_input()
                logger.info("Checked a checkbox: %s", checkbox.window_text())
            break
    except Exception as e:
        logger.warning("Checkbox handling error: %s", e)


def check_radiobutton(window):

    radiobutton_list = [
        # eng
        "agree", "accept", "i agree",
        # kor
        "동의", "확인",
        # german
        "akzeptieren", "zustimmen", "stimme zu", "einverstanden"
    ]
    try:
        for radiobutton in window.descendants(control_type="RadioButton"):
            radiobutton_text = radiobutton.window_text().lower()
            logger.debug("RadioButton: %s", radiobutton_text)

            for radio_button in radiobutton_list:
                if radio_button in radiobutton_text:
                    radiobutton.click()
                    logger.info("Checked a RadioButton: %s", radiobutton_text)
                    return

    except Exception as e:
        logger.warning("RadioButton handling error: %s", e)


def get_install_windows(file_path):

    get_windows = []
    try:
        desktop = Desktop(backend="uia")
        windows = desktop.windows()
        file_name = os.path.splitext(os.path.basename(file_path))[0].lower()
        file_keyword: list = file_name.split()
        installation_keywords = [
            "setup", "install", "installer",
            "wizard", "inno", "nsis", "msi", 'language',
            "설치", "마법사", '언어'
        ]

        installation_keywords.extend(file_keyword)
        pass_window = ['명령 프롬프트', 'sublime text', 'program manager', '작업 표시줄']

        for window in windows:
            title = window.window_text().lower()

            skip_window = False
            for program in pass_window:
                if program in title:
                    skip_window = True
                    break

            if skip_window:
                continue

            for keyword in installation_keywords:
                if keyword in title:
                    get_windows.append(window)
        return get_windows
    except Exception as e:
        logger.warning("Error while checking installation window: %s", e)
        return get_windows


def gui_install(file_path, step=20):

    logger.info("gui_install() start: %s", file_path)
    pass_window = ['명령 프롬프트', 'sublime', 'program manager', '작업 표시줄']

    if not os.path.exists(file_path):
        logger.error("File not found: %s", file_path)
        return False
    set_windows_error_mode()
    try:
        app = Application(backend="uia").start(file_path)
        pid = app.process
        clicked_completion = False
        time.sleep(5)

        for i in range(step):
            time.sleep(3)
            logger.debug("GUI install step %d", i + 1)
            windows: list = app.windows()
            logger.debug("app_windows: %s", windows)

            additional_window = get_install_windows(file_path)
            merged = {w.handle: w for w in windows}
            for w in additional_window:
                merged.setdefault(w.handle, w)
            windows = list(merged.values())
            logger.debug("windows: %s", windows)

            if len(windows) == 0:
                logger.debug("No relevant windows found.")
                continue

            for window in windows:
                title = window.window_text().lower()

                skip_window = False
                for program in pass_window:
                    if program in title:
                        skip_window = True
                        break

                if skip_window:
                    continue

                logger.debug("Processing window: %s", window)

                if click_button(window):
                    clicked_completion = True
                check_checkbox(window)
                check_radiobutton(window)
                wait_for_progress(window)

        logger.info("GUI install loop complete: %s", file_path)
        close_windows()

        process_exited = not psutil.pid_exists(pid)
        if clicked_completion and process_exited:
            return True

        logger.info(
            "GUI install did not meet success criteria: clicked_completion=%s, process_exited=%s",
            clicked_completion, process_exited
        )
        if not process_exited:
            terminate_process_tree(pid)
        return False

    except Exception as e:
        logger.error("Error during gui_install %s: %s", file_path, e)
        if 'pid' in locals():
            terminate_process_tree(pid)
        close_windows()
        return False
