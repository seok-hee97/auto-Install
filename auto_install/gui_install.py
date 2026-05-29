import os
import time

from pywinauto import Desktop
from pywinauto import Application

from utils import set_windows_error_mode, terminate_installation_process, close_windows


def wait_for_progress(window, timeout=30):
    start_time = time.time()
    try:
        for progress in window.descendants(control_type="ProgressBar"):
            if progress.is_visible():
                print("waiting progressbar")
                while progress.is_visible() and get_progress_value(progress) < 100:
                    value = get_progress_value(progress)
                    print(f"progressbar value: {value}%")
                    time.sleep(2)

                    if time.time() - start_time > timeout:
                        print("Progress bar timeout reached")
                        break

                    if not progress.is_visible():
                        print("Progress bar not visible")
                        break

                print("Progress completed or window closed")
    except Exception as e:
        print(f"Progress bar handling error: {e}")


def get_progress_value(progress):

    try:
        properties = progress.legacy_properties()
        if 'Value' in properties:
            return int(properties['Value'].rstrip('%'))
        else:
            return 0
    except ValueError:
        print(f"Invalid progress value: {properties.get('Value', 'N/A')}")
        return 0
    except Exception as e:
        print(f"Error getting progress value: {e}")
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
    try:
        for button in window.descendants(control_type="Button"):
            button_text = button.window_text().lower()

            for click in clicks:
                if click in button_text:
                    print(f"Clicking button: {button_text}")
                    button.click_input()

    except Exception as e:
        print(f"Button handling error: {e}")


def check_checkbox(window):

    try:
        for checkbox in window.descendants(control_type="CheckBox"):
            print(f"Checkbox: {checkbox.window_text()}")
            checkbox.click_input()
            print("Checked a checkbox")
            break
    except Exception as e:
        print(f"Checkbox handling error: {e}")


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
            print(f"radiobutton: {radiobutton_text}")

            for radio_button in radiobutton_list:
                if radio_button in radiobutton_text:
                    radiobutton.click()
                    print("Checked a RadioButton")
                    return

    except Exception as e:
        print(f"RadioButton handling error: {e}")


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
        print(f"Error while checking installation window: {str(e)}")
        return get_windows


def gui_install(file_path, step=20):

    print("def gui_install() working!!")
    pass_window = ['명령 프롬프트', 'sublime', 'program manager', '작업 표시줄']

    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return False
    set_windows_error_mode()
    try:
        app = Application(backend="uia").start(file_path)
        time.sleep(5)

        for step in range(step):
            time.sleep(3)
            print(f"Step {step + 1}")
            windows: list = app.windows()
            print("app_windows : ", windows)

            additional_window = get_install_windows(file_path)
            windows.extend(additional_window)
            print("windows : ", windows)

            if len(windows) == 0:
                print("No relevant windows found.")
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

                print("window : ", window)

                click_button(window)
                check_checkbox(window)
                check_radiobutton(window)
                wait_for_progress(window)

        print("Installation process completed.")
        ret_process = terminate_installation_process(file_path)
        close_windows()
        if ret_process:
            return True     # 프로세스 정상 종료 = 성공
        return False        # 프로세스를 찾지 못함 = 실패

    except Exception as e:
        print(f"An error occurred: {e}")
        terminate_installation_process(file_path)
        close_windows()
        return False
