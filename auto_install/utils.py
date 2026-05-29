import os
import shutil
import subprocess
import time
import ctypes

from pywinauto import Desktop
import psutil

from config import CLASSIFY_TOOL_EXE, ZIP_TYPE_LIST, INSTALLER_TYPE_LIST


def terminate_installation_process(file_path: str) -> bool:

    try:
        process_name = os.path.splitext(os.path.basename(file_path))[0].lower()
        process_keywords: list = process_name.split()

        for proc in psutil.process_iter(['name', 'pid']):
            if any(keyword in proc.info['name'].lower() for keyword in process_keywords):
                process = psutil.Process(proc.info['pid'])
                for child in process.children(recursive=True):
                    child.terminate()
                process.terminate()
                print(f"Terminated process: {process_name}")
                return True

        print(f"Process {process_name} not found")
        return False

    except Exception as e:
        print(f"Error terminating process {process_name}: {e}")
        return False


def close_windows(step: int = 5) -> None:
    print("def close_window() working!!")
    clicks = [
        # eng
        "cancel", "exit", "quit", "finish", "yes", "ok", 'x', "later", "close",
        # kor
        "취소", "예", "예(Y)", "마침", "확인", "완료", "나중에"
    ]

    pass_window = ['명령 프롬프트', 'sublime', 'program manager', "파일 탐색기", "작업 표시줄"]

    for i in range(step):
        print("step : ", i + 1)
        try:
            time.sleep(1)
            windows = Desktop(backend="uia").windows()

            if len(windows) == 0:
                print("No windows found. Continuing to next step.")
                continue

            for window in windows:
                try:
                    title = window.window_text().lower()
                    if any(program in title for program in pass_window):
                        continue

                    for button in window.descendants(control_type="Button"):
                        if any(click in button.window_text().lower() for click in clicks):
                            print(f"Clicking button: {button.window_text()}")
                            button.click_input()

                    print(f"Closing browser window: {title}")
                    window.close()
                    time.sleep(1)

                except Exception as e:
                    print(f"Error processing window: {str(e)}")

        except Exception as e:
            print(f"Error scanning for windows: {str(e)}")


def set_windows_error_mode():

    SEM_FAILCRITICALERRORS = 0x0001
    SEM_NOGPFAULTERRORBOX = 0x0002
    SEM_NOALIGNMENTFAULTEXCEPT = 0x0004
    SEM_NOOPENFILEERRORBOX = 0x8000

    error_mode = (SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX |
                  SEM_NOALIGNMENTFAULTEXCEPT | SEM_NOOPENFILEERRORBOX)
    ctypes.windll.kernel32.SetErrorMode(error_mode)


def classify_installer(file_path: str, exe_path=CLASSIFY_TOOL_EXE) -> str:

    if not os.path.exists(exe_path):
        print(f"Error: ClassifyTool.exe not found at {exe_path}")
        return "Error"

    try:
        result = subprocess.run([exe_path, file_path], capture_output=True, timeout=60)
        output = result.stdout.decode('latin-1').split('->')[-1].strip()

        if any(zip_type in output.lower() for zip_type in ZIP_TYPE_LIST):
            return 'zip'

        if "Installer:" in output:
            installer_info = output.split("Installer:")[-1].strip()
            for installer_type in INSTALLER_TYPE_LIST:
                if installer_type in installer_info:
                    return installer_type

        return 'Unknown'

    except subprocess.TimeoutExpired:
        print(f"Timeout occurred while processing {file_path}")
        return "Timeout"
    except Exception as e:
        print(f"Error occurred while processing {file_path}: {str(e)}")
        return "Error"


def verify_folder(folder_path):

    count: int = 0

    if not os.path.exists(folder_path):
        print(f"Error: Folder not found at {folder_path}")
        return -1

    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith('.exe'):
                file_path = os.path.join(root, file)
                installer_type = classify_installer(file_path)
                if installer_type not in ('Unknown', 'Error', 'Timeout'):
                    count += 1
    return count


def seperate_installer(folder_path):

    try:
        cnt = 0
        path_list = os.listdir(folder_path)
        dir_name = os.path.dirname(folder_path)
        print(dir_name)

        for i in path_list:
            file_path = dir_name + '/' + i
            print("file_path :", file_path)

            installer_type = classify_installer(file_path)

            src = file_path
            dst = dir_name + '/' + installer_type
            move_to_file(src, dst)
            cnt += 1

        print("count file(move) : ", cnt)
    except Exception as e:
        print("error : ", e)


def move_to_file(src_path: str, dst_path: str) -> int:

    if not os.path.exists(dst_path):
        os.mkdir(dst_path)

    shutil.move(src_path, dst_path)
    print(f'{src_path} has been moved to new folder : {dst_path} !')
    return 0


def note_file_txt(file_path: str, title: str = '') -> None:

    try:
        output_file = 'log_files.txt'
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"{title} {file_path}\n")
    except Exception as e:
        print(f"파일 기록 중 오류 발생: {e}")
