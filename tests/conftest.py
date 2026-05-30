"""
pytest conftest — mock all Windows-only packages so tests run on macOS/Linux.
This file is loaded by pytest before any test module, ensuring sys.modules mocks
are in place before auto_install/* modules are imported.
"""
import sys
import os
from unittest.mock import MagicMock

# ------------------------------------------------------------------
# Path setup: let test modules do `from config import ...` etc.
# ------------------------------------------------------------------
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_AUTO = os.path.join(_ROOT, "auto_install")
_TOOLS = os.path.join(_ROOT, "tools")
for _p in (_AUTO, _TOOLS, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ------------------------------------------------------------------
# Mock Windows-only packages (pywinauto, win32*, watchdog, OCR libs)
# ------------------------------------------------------------------
_WIN_PACKAGES = [
    "pywinauto",
    "pywinauto.application",
    "pywinauto.controls",
    "pywinauto.controls.uia_controls",
    "win32gui",
    "win32process",
    "pyautogui",
    "pytesseract",
    "PIL",
    "PIL.Image",
]
for _pkg in _WIN_PACKAGES:
    sys.modules.setdefault(_pkg, MagicMock())

# watchdog — cross-platform but may not be installed in test env
try:
    import watchdog  # noqa: F401
except ImportError:
    _wd_mock = MagicMock()
    sys.modules.setdefault("watchdog", _wd_mock)
    sys.modules.setdefault("watchdog.observers", _wd_mock)
    sys.modules.setdefault("watchdog.events", _wd_mock)
    # FileSystemEventHandler base class must be importable
    sys.modules["watchdog.events"].FileSystemEventHandler = object

# ------------------------------------------------------------------
# Mock ctypes.windll (not present on macOS/Linux)
# ------------------------------------------------------------------
import ctypes
if not hasattr(ctypes, "windll"):
    ctypes.windll = MagicMock()
