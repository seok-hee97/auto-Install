# auto-Install

Batch automation for Windows `.exe`/`.msi` installers — classify, silent install, GUI fallback.

## Overview

Given a folder of installer files, auto-Install processes each one through three sequential stages:

1. **Classify** — Identifies the installer framework (Inno Setup, NSIS, MSI, etc.) using [DIE](https://github.com/horsicq/Detect-It-Easy)
2. **Silent install** — Runs the installer with the appropriate silent flag (`/VERYSILENT`, `/S`, `/qn`, etc.)
3. **GUI automation** — If silent mode fails or is unavailable, automates the install wizard via [pywinauto](https://github.com/pywinauto/pywinauto)

Newly installed files are detected via filesystem monitoring (watchdog) and collected to `C:\Data\`.

## Project Structure

```
auto-Install/
├── auto_install/               # Main package
│   ├── main.py                 # Entry point — orchestrates the full pipeline
│   ├── config.py               # Paths, constants, installer type mappings
│   ├── utils.py                # classify_installer(), terminate_process_tree(), etc.
│   ├── silent_mode.py          # Silent install runner with polling-based window detection
│   ├── gui_install.py          # pywinauto GUI automation (click, checkbox, radiobutton, OCR fallback)
│   ├── filesystem_monitor.py   # watchdog-based file collection to C:\Data\collected\
│   └── extract_zip.py          # 7-Zip archive extraction for NSIS/MSI/7z installers
├── tools/
│   ├── snapshot_diff.py        # Pre/post install filesystem diff (Phase 8)
│   ├── vm_controller.py        # Hyper-V / VirtualBox snapshot automation (Phase 7)
│   └── compare_collected_files.py  # SHA-256 comparison of collected vs. reference files
├── tests/                      # pytest test suite (138 tests, cross-platform mocks)
│   ├── conftest.py             # Windows-only package mocks (pywinauto, win32gui, watchdog, etc.)
│   ├── test_config.py
│   ├── test_utils.py
│   ├── test_filesystem_monitor.py
│   ├── test_silent_mode.py
│   ├── test_gui_install.py
│   └── test_main.py
├── requirements.txt
└── LICENSE
```

## Requirements

- Windows 10 / 11
- Python 3.8+
- [7-Zip](https://www.7-zip.org/) — default install path (`C:\Program Files\7-Zip\`)
- [DIE (Detect It Easy)](https://github.com/horsicq/Detect-It-Easy) — `diec.exe` at `C:\Program Files\DIE\`
- Administrator privileges (required for UAC dialog handling)

## Installation

```bash
pip install -r requirements.txt
```

## Usage

Run as Administrator:

```bash
python auto_install/main.py <path_to_installer_folder>
```

Logs of failed files are written to `C:\Data\log_files.txt`.

## Supported Installer Types

| Type | Silent flag |
|------|-------------|
| Inno Setup | `/VERYSILENT /SUPPRESSMSGBOXES` |
| NSIS | `/S` |
| InstallShield | `/s` |
| WIX Toolset | `/q` |
| Microsoft Installer (MSI) | `/qn` |
| Wise Installer | `/s` |
| Advanced Installer | `/quiet` |
| Setup Factory | `/S` |
| Ghost Installer | `/S` |
| BitRock Installer | `--mode unattended` |
| CreateInstall-Overlay | `-silent` |
| Acronis Installer [ZIP] | `/quiet` |
| Sony Windows Installer | `/q` |
| Windows Installer | `/qn` |
| QT Installer | `--accept-licenses --default-answer --confirm-command install` |
| 7z Installer | `/S` |

## Recommended Environment

Running against unknown installers carries risk. Use an isolated VM:

| Purpose | Recommended |
|---------|-------------|
| Development / testing | Windows Sandbox (built-in, free) |
| Batch processing | Hyper-V + snapshot (Windows Pro, free) |
| Cross-platform host | VirtualBox or VMware |

Hyper-V snapshot automation example:

```powershell
Restore-VMCheckpoint -VMName "AutoInstall" -Name "Clean-State"
Start-VM -Name "AutoInstall"
```

## License

MIT
