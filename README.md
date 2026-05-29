# auto-Install

Automated Windows installer processing pipeline. Classifies installer types, extracts archives, runs silent installs, and falls back to GUI automation to collect installed program files.

## Overview

Processes `.exe` / `.msi` installer files through three sequential stages:

1. **Archive extraction** — Extracts NSIS, MSI, and 7z-packaged installers using 7-Zip
2. **Silent install** — Runs installers with type-specific silent flags (`/S`, `/VERYSILENT`, `/qn`, etc.)
3. **GUI automation** — Automates install wizards via pywinauto when silent mode is unavailable

Newly installed files are detected via filesystem monitoring (watchdog) and collected to `C:\Data\`.

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
