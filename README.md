# auto-Install

Batch automation for Windows `.exe`/`.msi` installers — classify, silent install, GUI fallback, and isolated VM execution.

## Overview

Given a folder of installer files, auto-Install processes each one through three sequential stages:

1. **Classify** — Identifies the installer framework (Inno Setup, NSIS, MSI, etc.) using [DIE](https://github.com/horsicq/Detect-It-Easy)
2. **Silent install** — Runs the installer with the appropriate silent flag (`/VERYSILENT`, `/S`, `/qn`, etc.)
3. **GUI automation** — If silent mode fails or is unavailable, automates the install wizard via [pywinauto](https://github.com/pywinauto/pywinauto)

Newly installed files are detected via filesystem monitoring (watchdog) and collected to `C:\Data\`.

For real batch automation, run installers inside a Windows guest VM through the host-side orchestrator. The host restores a clean snapshot, copies the project and installer set into the guest, executes `auto_install.main` inside the guest, then copies the result archive back to the host.

## Project Structure

```
auto-Install/
├── auto_install/               # Main package
│   ├── main.py                 # Guest worker — runs the install pipeline inside Windows
│   ├── config.py               # Paths, constants, installer type mappings
│   ├── utils.py                # classify_installer(), terminate_process_tree(), etc.
│   ├── silent_mode.py          # Silent install runner with polling-based window detection
│   ├── gui_install.py          # pywinauto GUI automation (click, checkbox, radiobutton, OCR fallback)
│   ├── filesystem_monitor.py   # watchdog-based file collection to C:\Data\collected\
│   └── extract_zip.py          # 7-Zip archive extraction for NSIS/MSI/7z installers
├── tools/
│   ├── snapshot_diff.py        # Pre/post install filesystem diff (Phase 8)
│   ├── vm_controller.py        # Legacy snapshot helper kept for compatibility
│   └── compare_collected_files.py  # SHA-256 comparison of collected vs. reference files
├── host_runner/                # Host-side VM orchestration
│   ├── orchestrator.py         # Restore/start VM, run guest worker, collect results
│   └── backends/
│       ├── base.py             # VMBackend interface
│       ├── hyperv.py           # Hyper-V + PowerShell Direct backend
│       └── virtualbox.py       # VirtualBox guestcontrol backend
├── tests/                      # pytest test suite (149 tests, cross-platform mocks)
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

### Direct Guest Run

Run this inside the Windows guest as Administrator:

```bash
python -m auto_install.main <path_to_installer_folder>
```

Logs of failed files are written to `C:\Data\log_files.txt`.

`auto_install.main` is the guest worker. It no longer performs VM restore/start/stop itself. The old `--vm-name` option is deprecated and refuses to run installers on the host to prevent accidental host contamination.

### Host VM Run

Run this from the host:

```bash
python -m host_runner.orchestrator \
  --backend hyperv \
  --vm-name AutoInstall \
  --snapshot Clean-State \
  --input ./samples \
  --out ./results
```

The orchestrator performs:

1. Restore VM snapshot
2. Start VM
3. Copy the project archive and installer input into `C:\AutoInstall`
4. Run `C:\AutoInstall\venv\Scripts\python.exe -m auto_install.main C:\AutoInstall\input`
5. Compress guest results from `C:\Data`
6. Copy `guest_result.zip` and `host_run.json` back to the host output directory
7. Stop VM

Host result layout:

```text
results/
└── <run_id>/
    ├── guest_result.zip
    └── host_run.json
```

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

### Guest VM Preparation

Inside the Windows guest:

- Install Python and create `C:\AutoInstall\venv`
- Install project dependencies into that venv
- Install 7-Zip at `C:\Program Files\7-Zip\7z.exe`
- Install DIE at `C:\Program Files\DIE\diec.exe`
- Run automation under an Administrator account
- Disable UAC prompts in the disposable VM if GUI automation must cross elevated installers

For Hyper-V PowerShell Direct, set guest credentials on the host:

```powershell
$env:AUTOINSTALL_GUEST_USERNAME = "Administrator"
$env:AUTOINSTALL_GUEST_PASSWORD = "<guest-password>"
```

For VirtualBox, install Guest Additions and set the same environment variables. You can also set `VBOXMANAGE_EXE` if `VBoxManage` is not on `PATH`.

Hyper-V manual snapshot commands:

```powershell
Restore-VMCheckpoint -VMName "AutoInstall" -Name "Clean-State"
Start-VM -Name "AutoInstall"
```

## License

MIT
