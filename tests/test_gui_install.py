"""Tests for gui_install.py — core UI interaction logic."""
import pytest
from unittest.mock import MagicMock, patch, call
import psutil

import gui_install
from gui_install import (
    check_radiobutton,
    check_checkbox,
    click_button,
    wait_for_installer_idle,
    get_install_windows,
    _process_windows,
    cleanup_post_install_processes,
    COMPLETION_KEYWORDS,
)


# ---------------------------------------------------------------------------
# Helper: build mock RadioButton / CheckBox / Button
# ---------------------------------------------------------------------------

def _mock_radio(text):
    r = MagicMock()
    r.window_text.return_value = text
    return r


def _mock_checkbox(state):
    cb = MagicMock()
    cb.get_toggle_state.return_value = state
    cb.window_text.return_value = f"checkbox_state_{state}"
    return cb


def _mock_button(text):
    btn = MagicMock()
    btn.window_text.return_value = text
    return btn


def _mock_window(radios=(), checkboxes=(), buttons=()):
    w = MagicMock()
    def descendants(control_type=None):
        if control_type == "RadioButton":
            return list(radios)
        if control_type == "CheckBox":
            return list(checkboxes)
        if control_type == "Button":
            return list(buttons)
        return []
    w.descendants.side_effect = descendants
    w.window_text.return_value = "Setup"
    return w


# ---------------------------------------------------------------------------
# check_radiobutton — Phase 4.8-A
# ---------------------------------------------------------------------------

class TestCheckRadiobutton:
    def test_clicks_agree_skips_disagree(self):
        agree = _mock_radio("I agree to the terms")
        disagree = _mock_radio("I do not agree to the terms")
        window = _mock_window(radios=[disagree, agree])

        check_radiobutton(window)

        agree.click_input.assert_called_once()
        disagree.click_input.assert_not_called()

    def test_agree_before_disagree(self):
        agree = _mock_radio("I agree")
        disagree = _mock_radio("I do not agree")
        window = _mock_window(radios=[agree, disagree])

        check_radiobutton(window)

        agree.click_input.assert_called_once()
        disagree.click_input.assert_not_called()

    def test_only_agree_present(self):
        agree = _mock_radio("동의합니다")
        window = _mock_window(radios=[agree])

        check_radiobutton(window)

        agree.click_input.assert_called_once()

    def test_only_disagree_no_click(self):
        disagree = _mock_radio("동의하지 않습니다")
        window = _mock_window(radios=[disagree])

        check_radiobutton(window)

        disagree.click_input.assert_not_called()

    def test_no_agree_keyword_no_click(self):
        radio1 = _mock_radio("Option A")
        radio2 = _mock_radio("Option B")
        window = _mock_window(radios=[radio1, radio2])

        check_radiobutton(window)

        radio1.click_input.assert_not_called()
        radio2.click_input.assert_not_called()

    def test_last_agree_wins(self):
        agree1 = _mock_radio("I agree")
        agree2 = _mock_radio("I accept")
        window = _mock_window(radios=[agree1, agree2])

        check_radiobutton(window)

        agree2.click_input.assert_called_once()
        agree1.click_input.assert_not_called()

    def test_german_disagree_skipped(self):
        agree = _mock_radio("Ich stimme zu")
        disagree = _mock_radio("Stimme nicht zu")
        window = _mock_window(radios=[disagree, agree])

        check_radiobutton(window)

        agree.click_input.assert_called_once()
        disagree.click_input.assert_not_called()

    def test_exception_in_descendants_handled(self):
        window = MagicMock()
        window.descendants.side_effect = Exception("COM error")
        check_radiobutton(window)  # should not raise

    def test_click_exception_handled(self):
        agree = _mock_radio("I agree")
        agree.click_input.side_effect = Exception("click failed")
        window = _mock_window(radios=[agree])
        check_radiobutton(window)  # should not propagate


# ---------------------------------------------------------------------------
# check_checkbox — Phase 4.8, Priority 3 (no break bug)
# ---------------------------------------------------------------------------

class TestCheckCheckbox:
    def test_checks_all_unchecked(self):
        cb1 = _mock_checkbox(0)
        cb2 = _mock_checkbox(0)
        cb3 = _mock_checkbox(0)
        window = _mock_window(checkboxes=[cb1, cb2, cb3])

        check_checkbox(window)

        cb1.click_input.assert_called_once()
        cb2.click_input.assert_called_once()
        cb3.click_input.assert_called_once()

    def test_already_checked_not_clicked(self):
        checked = _mock_checkbox(1)
        window = _mock_window(checkboxes=[checked])

        check_checkbox(window)

        checked.click_input.assert_not_called()

    def test_mixed_checked_unchecked(self):
        unchecked = _mock_checkbox(0)
        checked = _mock_checkbox(1)
        window = _mock_window(checkboxes=[unchecked, checked])

        check_checkbox(window)

        unchecked.click_input.assert_called_once()
        checked.click_input.assert_not_called()

    def test_no_checkboxes_no_error(self):
        window = _mock_window(checkboxes=[])
        check_checkbox(window)  # should not raise

    def test_get_toggle_state_exception_skips(self):
        cb = _mock_checkbox(None)
        cb.get_toggle_state.side_effect = Exception("UIA error")
        window = _mock_window(checkboxes=[cb])
        check_checkbox(window)  # should not raise, and should not click
        cb.click_input.assert_not_called()

    def test_second_checkbox_also_checked(self):
        """Regression: old code had `break` that prevented second checkbox from being checked."""
        cb1 = _mock_checkbox(0)
        cb2 = _mock_checkbox(0)
        window = _mock_window(checkboxes=[cb1, cb2])

        check_checkbox(window)

        cb2.click_input.assert_called_once()


# ---------------------------------------------------------------------------
# click_button — DANGER keywords + completion detection
# ---------------------------------------------------------------------------

class TestClickButton:
    def test_skips_uninstall_button(self):
        uninstall = _mock_button("Uninstall")
        window = _mock_window(buttons=[uninstall])

        click_button(window)

        uninstall.click_input.assert_not_called()

    def test_skips_restart_now_button(self):
        restart = _mock_button("Restart Now")
        window = _mock_window(buttons=[restart])

        click_button(window)

        restart.click_input.assert_not_called()

    def test_clicks_next(self):
        btn = _mock_button("Next")
        window = _mock_window(buttons=[btn])

        click_button(window)

        btn.click_input.assert_called_once()

    def test_clicks_install(self):
        btn = _mock_button("Install")
        window = _mock_window(buttons=[btn])

        click_button(window)

        btn.click_input.assert_called_once()

    def test_clicks_korean_next(self):
        btn = _mock_button("다음")
        window = _mock_window(buttons=[btn])

        click_button(window)

        btn.click_input.assert_called_once()

    def test_finish_returns_completion_true(self):
        btn = _mock_button("Finish")
        window = _mock_window(buttons=[btn])

        result = click_button(window)

        assert result is True

    def test_next_returns_completion_false(self):
        btn = _mock_button("Next")
        window = _mock_window(buttons=[btn])

        result = click_button(window)

        assert result is False

    def test_마침_returns_completion_true(self):
        btn = _mock_button("마침")
        window = _mock_window(buttons=[btn])

        result = click_button(window)

        assert result is True

    def test_german_fertig_returns_completion_true(self):
        btn = _mock_button("Fertig")
        window = _mock_window(buttons=[btn])

        result = click_button(window)

        assert result is True

    def test_uninstall_mixed_with_next_only_next_clicked(self):
        uninstall = _mock_button("Uninstall")
        next_btn = _mock_button("Next")
        window = _mock_window(buttons=[uninstall, next_btn])

        click_button(window)

        uninstall.click_input.assert_not_called()
        next_btn.click_input.assert_called_once()


# ---------------------------------------------------------------------------
# wait_for_installer_idle — Phase 4.8-F
# ---------------------------------------------------------------------------

class TestWaitForInstallerIdle:
    def test_idle_returns_true(self):
        mock_proc = MagicMock()
        mock_proc.cpu_percent.return_value = 0.5  # below threshold
        with patch("gui_install.psutil.Process", return_value=mock_proc):
            result = wait_for_installer_idle(pid=1234, threshold=3.0, timeout=5)
        assert result is True

    def test_no_such_process_returns_true(self):
        with patch("gui_install.psutil.Process", side_effect=psutil.NoSuchProcess(pid=99999)):
            result = wait_for_installer_idle(pid=99999)
        assert result is True

    def test_busy_exceeds_timeout_returns_false(self):
        mock_proc = MagicMock()
        mock_proc.cpu_percent.return_value = 99.0  # always busy
        with patch("gui_install.psutil.Process", return_value=mock_proc):
            result = wait_for_installer_idle(pid=1234, threshold=3.0, timeout=1)
        assert result is False


# ---------------------------------------------------------------------------
# get_install_windows — keyword-based window filter
# ---------------------------------------------------------------------------

class TestGetInstallWindows:
    def test_returns_windows_matching_keyword(self):
        mock_desktop = MagicMock()
        win_setup = MagicMock()
        win_setup.window_text.return_value = "Setup Wizard"
        win_other = MagicMock()
        win_other.window_text.return_value = "Notepad"
        mock_desktop.windows.return_value = [win_setup, win_other]

        with patch("gui_install.Desktop", return_value=mock_desktop):
            result = get_install_windows("C:\\installer_setup.exe")

        assert win_setup in result
        assert win_other not in result

    def test_skips_pass_window(self):
        mock_desktop = MagicMock()
        win_cmd = MagicMock()
        win_cmd.window_text.return_value = "명령 프롬프트"
        mock_desktop.windows.return_value = [win_cmd]

        with patch("gui_install.Desktop", return_value=mock_desktop):
            result = get_install_windows("C:\\app.exe")

        assert win_cmd not in result

    def test_filename_keyword_matched(self):
        mock_desktop = MagicMock()
        win = MagicMock()
        win.window_text.return_value = "MyApp"  # matches filename keyword 'myapp'
        mock_desktop.windows.return_value = [win]

        # Use os.sep-agnostic path so basename() returns just 'myapp.exe' on any platform
        import os
        fake_path = os.path.join("some", "dir", "myapp.exe")
        with patch("gui_install.Desktop", return_value=mock_desktop):
            result = get_install_windows(fake_path)

        assert win in result


# ---------------------------------------------------------------------------
# _process_windows — orchestration
# ---------------------------------------------------------------------------

class TestProcessWindows:
    def test_returns_true_when_completion_clicked(self):
        finish_btn = _mock_button("Finish")
        window = _mock_window(buttons=[finish_btn])
        window.window_text.return_value = "Setup"

        result = _process_windows([window])

        assert result is True

    def test_returns_false_when_no_completion(self):
        next_btn = _mock_button("Next")
        window = _mock_window(buttons=[next_btn])
        window.window_text.return_value = "Setup"

        result = _process_windows([window])

        assert result is False

    def test_skips_pass_window(self):
        btn = _mock_button("Finish")
        window = _mock_window(buttons=[btn])
        window.window_text.return_value = "명령 프롬프트"

        result = _process_windows([window])

        assert result is False
        btn.click_input.assert_not_called()

    def test_ocr_fallback_called_when_no_completion(self):
        """OCR fallback은 completion 버튼을 못 찾았을 때 호출되어야 한다."""
        next_btn = _mock_button("Next")
        window = _mock_window(buttons=[next_btn])
        window.window_text.return_value = "Setup"

        with patch("gui_install._OCR_AVAILABLE", True), \
             patch("gui_install.ocr_click_button", return_value=True) as mock_ocr:
            result = _process_windows([window])

        mock_ocr.assert_called_once()
        assert result is True

    def test_ocr_fallback_not_called_when_completion_found(self):
        """completion 버튼이 이미 클릭됐으면 OCR fallback을 호출하지 않는다."""
        finish_btn = _mock_button("Finish")
        window = _mock_window(buttons=[finish_btn])
        window.window_text.return_value = "Setup"

        with patch("gui_install._OCR_AVAILABLE", True), \
             patch("gui_install.ocr_click_button") as mock_ocr:
            _process_windows([window])

        mock_ocr.assert_not_called()

    def test_keyboard_nav_called_when_no_completion(self):
        """키보드 네비게이션 fallback은 completion 클릭 실패 시 호출되어야 한다."""
        next_btn = _mock_button("Next")
        window = _mock_window(buttons=[next_btn])
        window.window_text.return_value = "Setup"

        with patch("gui_install.try_keyboard_navigation") as mock_kbd, \
             patch("gui_install._OCR_AVAILABLE", False):
            _process_windows([window])

        mock_kbd.assert_called_once_with(window)

    def test_no_fallback_for_empty_window_list(self):
        """창이 없으면 OCR / 키보드 fallback 모두 호출하지 않는다."""
        with patch("gui_install.try_keyboard_navigation") as mock_kbd, \
             patch("gui_install._OCR_AVAILABLE", True), \
             patch("gui_install.ocr_click_button") as mock_ocr:
            result = _process_windows([])

        mock_kbd.assert_not_called()
        mock_ocr.assert_not_called()
        assert result is False


# ---------------------------------------------------------------------------
# cleanup_post_install_processes — only installer-related processes are killed
# ---------------------------------------------------------------------------

class TestCleanupPostInstallProcesses:
    def test_terminates_child_process_only(self):
        root = MagicMock()
        root.children.return_value = []

        child = MagicMock()
        child.name.return_value = "launched_app.exe"
        child.ppid.return_value = 100
        child.create_time.return_value = 10.0
        child.exe.return_value = r"C:\Program Files\App\launched_app.exe"

        unrelated = MagicMock()
        unrelated.name.return_value = "python.exe"
        unrelated.ppid.return_value = 1
        unrelated.create_time.return_value = 10.0
        unrelated.exe.return_value = r"C:\Python\python.exe"

        def process_for(pid):
            return {100: root, 200: child, 300: unrelated}[pid]

        with patch("gui_install.psutil.pids", return_value=[100, 200, 300]), \
             patch("gui_install.psutil.Process", side_effect=process_for), \
             patch("gui_install.terminate_process_tree") as mock_terminate:
            cleanup_post_install_processes(root_pid=100, before_pids={100}, started_at=5.0)

        mock_terminate.assert_called_once_with(200)

    def test_ignores_unrelated_new_process(self):
        root = MagicMock()
        root.children.return_value = []

        unrelated = MagicMock()
        unrelated.name.return_value = "notepad.exe"
        unrelated.ppid.return_value = 1
        unrelated.create_time.return_value = 10.0
        unrelated.exe.return_value = r"C:\Windows\System32\notepad.exe"

        def process_for(pid):
            return {100: root, 200: unrelated}[pid]

        with patch("gui_install.psutil.pids", return_value=[100, 200]), \
             patch("gui_install.psutil.Process", side_effect=process_for), \
             patch("gui_install.terminate_process_tree") as mock_terminate:
            cleanup_post_install_processes(root_pid=100, before_pids={100}, started_at=5.0)

        mock_terminate.assert_not_called()
