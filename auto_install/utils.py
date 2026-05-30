import os
import json
import logging
import shutil
import subprocess
import time
import ctypes

from pywinauto import Desktop
import psutil

from config import DIEC_EXE, INSTALLER_TYPE_LIST, DIE_INSTALLER_MAP, DIE_SFX_MAP, LOG_FILE, DANGER_KEYWORDS

logger = logging.getLogger(__name__)

_KNOWN_RETURNS = set(INSTALLER_TYPE_LIST) | {"zip", "Unknown", "Error", "Timeout"}


def terminate_process_tree(pid: int) -> bool:
    try:
        process = psutil.Process(pid)
        children = process.children(recursive=True)
        for child in children:
            child.terminate()
        gone, alive = psutil.wait_procs(children, timeout=5)
        for child in alive:
            child.kill()
        process.terminate()
        try:
            process.wait(timeout=5)
        except psutil.TimeoutExpired:
            process.kill()
        logger.info("Terminated process tree: %d", pid)
        return True
    except psutil.NoSuchProcess:
        logger.info("Process already exited: %d", pid)
        return False
    except Exception as e:
        logger.error("Error terminating process tree %d: %s", pid, e)
        return False


def close_windows(step: int = 5) -> None:
    logger.info("close_windows() start")
    clicks = [
        # eng
        "cancel", "exit", "quit", "finish", "yes", "ok", 'x', "later", "close",
        # kor
        "취소", "예", "예(Y)", "마침", "확인", "완료", "나중에"
    ]

    pass_window = ['명령 프롬프트', 'sublime', 'program manager', "파일 탐색기", "작업 표시줄"]

    for i in range(step):
        logger.debug("close_windows step %d", i + 1)
        try:
            time.sleep(1)
            windows = Desktop(backend="uia").windows()

            if len(windows) == 0:
                logger.debug("No windows found.")
                continue

            for window in windows:
                try:
                    title = window.window_text().lower()
                    if any(program in title for program in pass_window):
                        continue

                    for button in window.descendants(control_type="Button"):
                        btn_text = button.window_text().lower()
                        if any(danger in btn_text for danger in DANGER_KEYWORDS):
                            logger.info("Skipping dangerous button in close_windows: %s", btn_text)
                            continue
                        if any(click in btn_text for click in clicks):
                            logger.info("Clicking button: %s", button.window_text())
                            button.click_input()

                    logger.info("Closing window: %s", title)
                    window.close()
                    time.sleep(1)

                except Exception as e:
                    logger.warning("Error processing window: %s", e)

        except Exception as e:
            logger.warning("Error scanning for windows: %s", e)


def set_windows_error_mode():

    SEM_FAILCRITICALERRORS = 0x0001
    SEM_NOGPFAULTERRORBOX = 0x0002
    SEM_NOALIGNMENTFAULTEXCEPT = 0x0004
    SEM_NOOPENFILEERRORBOX = 0x8000

    error_mode = (SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX |
                  SEM_NOALIGNMENTFAULTEXCEPT | SEM_NOOPENFILEERRORBOX)
    ctypes.windll.kernel32.SetErrorMode(error_mode)


def classify_installer(file_path: str, exe_path=DIEC_EXE) -> str:

    if not os.path.exists(exe_path):
        logger.error("diec.exe not found at %s", exe_path)
        return "Error"

    try:
        result = subprocess.run(
            [exe_path, "--json", file_path],
            capture_output=True, timeout=60
        )
        data = json.loads(result.stdout)

        for detect in data.get("detects", []):
            filetype = detect.get("filetype", "").lower()

            # CAB / 순수 아카이브 파일타입 → zip
            if filetype in {"cab", "archive"}:
                return "zip"

            for value in detect.get("values", []):
                value_type = value.get("type", "").lower()
                value_name = value.get("name", "").lower()

                if value_type == "sfx":
                    # 7-Zip SFX → 7z installer; 그 외 SFX → zip
                    for key, installer_type in DIE_SFX_MAP.items():
                        if key in value_name:
                            return installer_type
                    return "zip"

                if value_type == "installer":
                    for key, installer_type in DIE_INSTALLER_MAP.items():
                        if key in value_name:
                            if installer_type in _KNOWN_RETURNS:
                                return installer_type

        return "Unknown"

    except json.JSONDecodeError as e:
        logger.error("Error parsing DIE output for %s: %s", file_path, e)
        return "Error"
    except subprocess.TimeoutExpired:
        logger.warning("Timeout while classifying: %s", file_path)
        return "Timeout"
    except Exception as e:
        logger.error("Error classifying %s: %s", file_path, e)
        return "Error"


def verify_folder(folder_path):

    count: int = 0

    if not os.path.exists(folder_path):
        logger.error("Folder not found: %s", folder_path)
        return -1

    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith('.exe'):
                file_path = os.path.join(root, file)
                installer_type = classify_installer(file_path)
                if installer_type not in ('Unknown', 'Error', 'Timeout'):
                    count += 1
    return count


def move_to_file(src_path: str, dst_path: str) -> int:

    if not os.path.exists(dst_path):
        os.mkdir(dst_path)

    shutil.move(src_path, dst_path)
    logger.info("Moved %s -> %s", src_path, dst_path)
    return 0


def note_file_txt(file_path: str, title: str = '') -> None:

    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{title} {file_path}\n")
    except Exception as e:
        logger.error("파일 기록 중 오류: %s", e)
