import logging
import os
import time

from pywinauto import Desktop
from pywinauto import Application
import psutil

from config import (
    DANGER_KEYWORDS, DISAGREE_KEYWORDS_RADIO, AGREE_KEYWORDS,
    PASS_WINDOW, INSTALLATION_KEYWORDS,
)
from utils import set_windows_error_mode, terminate_process_tree, close_windows

logger = logging.getLogger(__name__)

COMPLETION_KEYWORDS = [
    "finish", "completed", "complete", "done", "close",
    "마침", "완료", "종료",
    "fertig", "beenden",
]

# pyautogui — 키보드 네비게이션 fallback + OCR screenshot에 필요
try:
    import pyautogui as _pyautogui
    _PYAUTOGUI_AVAILABLE = True
except ImportError:
    _PYAUTOGUI_AVAILABLE = False

# OCR fallback — pyautogui + pytesseract 가 모두 설치된 경우에만 활성화
try:
    import pytesseract as _pytesseract
    _OCR_AVAILABLE = _PYAUTOGUI_AVAILABLE
    _BUTTON_KEYWORDS_OCR = [
        "ok", "next", "install", "finish", "yes", "다음", "설치", "확인", "마침"
    ]
except ImportError:
    _OCR_AVAILABLE = False

# PID 트리 창 탐색 — pywin32 가 설치된 경우에만 활성화
try:
    import win32gui as _win32gui
    import win32process as _win32process
    _PYWIN32_AVAILABLE = True
except ImportError:
    _PYWIN32_AVAILABLE = False


# ---------------------------------------------------------------------------
# Progress bar helpers
# ---------------------------------------------------------------------------

def wait_for_progress(window, timeout=30):
    start_time = time.time()
    try:
        for progress in window.descendants(control_type="ProgressBar"):
            if progress.is_visible():
                logger.info("Waiting for progress bar")
                while progress.is_visible() and get_progress_value(progress) < 100:
                    logger.debug("Progress: %d%%", get_progress_value(progress))
                    time.sleep(2)
                    if time.time() - start_time > timeout:
                        logger.warning("Progress bar timeout reached")
                        break
                    if not progress.is_visible():
                        break
                logger.info("Progress completed or window closed")
    except Exception as e:
        logger.warning("Progress bar handling error: %s", e)


def get_progress_value(progress):
    try:
        properties = progress.legacy_properties()
        if 'Value' in properties:
            return int(properties['Value'].rstrip('%'))
        return 0
    except ValueError:
        logger.warning("Invalid progress value")
        return 0
    except Exception as e:
        logger.warning("Error getting progress value: %s", e)
        return 0


# ---------------------------------------------------------------------------
# UI interaction helpers
# ---------------------------------------------------------------------------

def click_button(window):
    clicks = [
        # eng
        "next", "install", "finish", "ok", "yes", "accept", "agree",
        "run", "i agree", "continue", "done", "close",
        "enable", "retry", "don't send", "don't save",
        "unzip", "open", "close the program", "save",
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
    # Phase 4.8 Priority 3: break 제거 → 모든 체크박스 순회
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
    except Exception as e:
        logger.warning("Checkbox handling error: %s", e)


def check_radiobutton(window):
    # Phase 4.8 Priority 1: DISAGREE 키워드 건너뜀 + agree_candidate 패턴으로 한 번만 클릭
    # click_input() — 실제 마우스 입력 시뮬레이션 (click()의 WM_CLICK보다 신뢰성 높음)
    agree_candidate = None
    try:
        for radiobutton in window.descendants(control_type="RadioButton"):
            text = radiobutton.window_text().lower()
            logger.debug("RadioButton: %s", text)
            if any(k in text for k in DISAGREE_KEYWORDS_RADIO):
                continue
            if any(k in text for k in AGREE_KEYWORDS):
                agree_candidate = radiobutton
        if agree_candidate:
            agree_candidate.click_input()
            logger.info("Checked RadioButton: %s", agree_candidate.window_text())
    except Exception as e:
        logger.warning("RadioButton handling error: %s", e)


def try_keyboard_navigation(window):
    # Phase 4.8-E: UI 요소는 인식되나 마우스 클릭 실패 시 보조 수단 (pyautogui만 필요)
    if not _PYAUTOGUI_AVAILABLE:
        return
    try:
        window.set_focus()
        for _ in range(5):
            _pyautogui.press('tab')
            time.sleep(0.1)
        _pyautogui.press('enter')
        logger.info("Keyboard navigation fallback applied")
    except Exception as e:
        logger.warning("Keyboard navigation error: %s", e)


def ocr_click_button() -> bool:
    # Phase 4.8-G: custom-drawn 컨트롤 대응 — UIA/Win32 모두 실패 시 마지막 수단
    if not _OCR_AVAILABLE:
        return False
    try:
        screenshot = _pyautogui.screenshot()
        data = _pytesseract.image_to_data(
            screenshot, lang="kor+eng", output_type=_pytesseract.Output.DICT
        )
        for i, word in enumerate(data['text']):
            if not word.strip():
                continue
            if any(k in word.lower() for k in _BUTTON_KEYWORDS_OCR):
                if int(data['conf'][i]) > 60:
                    x = data['left'][i] + data['width'][i] // 2
                    y = data['top'][i] + data['height'][i] // 2
                    _pyautogui.click(x, y)
                    logger.info("OCR clicked at (%d, %d): %s", x, y, word)
                    return True
    except Exception as e:
        logger.warning("OCR fallback error: %s", e)
    return False


# ---------------------------------------------------------------------------
# Window discovery helpers
# ---------------------------------------------------------------------------

def wait_for_installer_idle(pid: int, threshold: float = 3.0, timeout: int = 15) -> bool:
    # Phase 4.8-F: 고정 sleep(3) 대신 CPU-idle 기반 적응형 대기
    try:
        proc = psutil.Process(pid)
        start = time.time()
        while time.time() - start < timeout:
            if proc.cpu_percent(interval=1) < threshold:
                return True
        return False
    except psutil.NoSuchProcess:
        return True
    except Exception as e:
        logger.warning("wait_for_installer_idle error: %s", e)
        return False


def get_all_windows_for_process_tree(root_pid: int) -> list:
    # Phase 4.8-C: 부모뿐 아니라 자식 프로세스의 창까지 캡처 (pywin32 필요)
    if not _PYWIN32_AVAILABLE:
        return []
    try:
        pid_set = {root_pid} | {
            c.pid for c in psutil.Process(root_pid).children(recursive=True)
        }
        result = []

        def _cb(hwnd, _):
            if not _win32gui.IsWindowVisible(hwnd):
                return
            _, pid = _win32process.GetWindowThreadProcessId(hwnd)
            if pid in pid_set:
                try:
                    result.append(Application(backend="uia").window(handle=hwnd))
                except Exception:
                    pass

        _win32gui.EnumWindows(_cb, None)
        return result
    except psutil.NoSuchProcess:
        return []
    except Exception as e:
        logger.warning("get_all_windows_for_process_tree error: %s", e)
        return []


def get_install_windows(file_path):
    get_windows = []
    try:
        desktop = Desktop(backend="uia")
        windows = desktop.windows()
        file_name = os.path.splitext(os.path.basename(file_path))[0].lower()
        file_keyword: list = file_name.split()

        keywords = list(INSTALLATION_KEYWORDS) + file_keyword

        for window in windows:
            title = window.window_text().lower()
            if any(program in title for program in PASS_WINDOW):
                continue
            if any(keyword in title for keyword in keywords):
                get_windows.append(window)
        return get_windows
    except Exception as e:
        logger.warning("Error while checking installation window: %s", e)
        return get_windows


# ---------------------------------------------------------------------------
# Core install logic
# ---------------------------------------------------------------------------

def _process_windows(windows) -> bool:
    """창 목록에 버튼 클릭·체크박스·라디오버튼·프로그레스바 처리. 완료 버튼 클릭 시 True 반환."""
    clicked_completion = False
    active_window = None  # PASS_WINDOW 제외, 첫 번째 유효 창 (fallback용)

    for window in windows:
        title = window.window_text().lower()
        if any(program in title for program in PASS_WINDOW):
            continue
        if active_window is None:
            active_window = window
        logger.debug("Processing window: %s", window)
        if click_button(window):
            clicked_completion = True
        check_checkbox(window)
        check_radiobutton(window)
        wait_for_progress(window)

    if not clicked_completion and active_window is not None:
        # Phase 4.8-E: UIA 요소는 잡히지만 클릭이 실패하는 경우 키보드로 보완
        try_keyboard_navigation(active_window)
        # Phase 4.8-G: custom-drawn 컨트롤 — UIA/Win32 모두 실패 시 OCR로 버튼 좌표 탐색
        if _OCR_AVAILABLE and ocr_click_button():
            clicked_completion = True

    return clicked_completion


def _try_gui_install(file_path: str, backend: str = "uia", step: int = 20) -> bool:
    """단일 백엔드로 GUI 설치 시도. 성공 시 True 반환."""
    set_windows_error_mode()
    try:
        # Phase 4.8 Priority 2: 설치 전 PID 스냅샷
        before_pids = set(psutil.pids())
        app = Application(backend=backend).start(file_path)
        pid = app.process
        clicked_completion = False
        time.sleep(5)

        for i in range(step):
            # 설치 프로세스가 이미 종료됐으면 나머지 루프를 건너뜀
            if not psutil.pid_exists(pid):
                logger.info("Installer process exited at step %d", i + 1)
                break
            # Phase 4.8-F: CPU-idle 기반 대기 (실패 시 고정 sleep fallback)
            if not wait_for_installer_idle(pid, threshold=3.0, timeout=15):
                time.sleep(3)
            logger.debug("GUI install step %d (backend=%s)", i + 1, backend)

            # Phase 4.8-C: app.windows() + PID 트리 + 키워드 탐색 통합
            windows_by_handle: dict = {w.handle: w for w in app.windows()}
            for w in get_all_windows_for_process_tree(pid):
                windows_by_handle.setdefault(w.handle, w)
            for w in get_install_windows(file_path):
                windows_by_handle.setdefault(w.handle, w)

            windows = list(windows_by_handle.values())
            logger.debug("windows: %s", windows)

            if not windows:
                logger.debug("No relevant windows found.")
                continue

            if _process_windows(windows):
                clicked_completion = True

        logger.info("GUI install loop complete (backend=%s): %s", backend, file_path)
        close_windows()

        # Phase 4.8 Priority 2: 설치 후 자동 실행된 신규 프로세스 종료
        after_pids = set(psutil.pids())
        for new_pid in (after_pids - before_pids - {pid}):
            try:
                terminate_process_tree(new_pid)
            except psutil.NoSuchProcess:
                pass

        process_exited = not psutil.pid_exists(pid)
        if clicked_completion and process_exited:
            return True

        logger.info(
            "Success criteria not met (backend=%s): clicked_completion=%s, process_exited=%s",
            backend, clicked_completion, process_exited,
        )
        if not process_exited:
            terminate_process_tree(pid)
        return False

    except Exception as e:
        logger.error("Error during gui_install (backend=%s) %s: %s", backend, file_path, e)
        if 'pid' in locals():
            terminate_process_tree(pid)
        close_windows()
        return False


def gui_install(file_path, step=20):
    logger.info("gui_install() start: %s", file_path)

    if not os.path.exists(file_path):
        logger.error("File not found: %s", file_path)
        return False

    # Phase 4.8-B: UIA 백엔드 먼저 시도, 실패 시 Win32 백엔드로 재시도
    if _try_gui_install(file_path, backend="uia", step=step):
        return True

    logger.info("UIA backend failed, retrying with Win32 backend: %s", file_path)
    return _try_gui_install(file_path, backend="win32", step=step)
