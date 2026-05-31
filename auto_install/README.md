# auto_install Package

`auto_install` is the Windows guest worker package. It runs inside the target Windows environment and performs installer classification, extraction, silent install, GUI fallback, and file collection.

## Role

Use this package only for the actual installation workflow:

```bash
python -m auto_install.main C:\AutoInstall\input --run-id 20260601_120000
```

For isolated VM execution, use the host orchestrator from the project root:

```bash
python -m host_runner.orchestrator --backend hyperv --vm-name AutoInstall --snapshot Clean-State --input ./samples --out ./results
```

`auto_install.main` does not restore, start, stop, or execute commands inside VMs. The deprecated `--vm-name` argument is rejected to avoid accidentally running installers on the host while assuming VM isolation.

## Guest Paths

Default runtime paths are defined in `config.py`:

```text
C:\Data\
  ├── collected\
  ├── reports\install_summary.csv
  ├── manifest.jsonl
  ├── log_files.txt
  └── run.log
```

The host orchestrator copies installers to:

```text
C:\AutoInstall\input
```

and runs:

```text
C:\AutoInstall\venv\Scripts\python.exe -m auto_install.main C:\AutoInstall\input
```

## Pipeline

1. `classify_installer()` calls `diec.exe --json` and maps DIE output to installer types.
2. Extractable types are unpacked with 7-Zip.
3. Silent install is attempted with framework-specific flags.
4. GUI install is attempted with pywinauto UIA, then Win32 fallback.
5. `filesystem_monitor.py` copies new or modified files to `C:\Data\collected`.
6. `install_summary.csv`, `manifest.jsonl`, and logs are written under `C:\Data`.

## Important Constraints

- Run in an interactive Windows desktop session.
- Run as Administrator.
- UAC prompts on Secure Desktop cannot be automated; use a disposable VM and disable UAC prompts there.
- `7z.exe` must exist at `C:\Program Files\7-Zip\7z.exe`.
- `diec.exe` must exist at `C:\Program Files\DIE\diec.exe`.
- GUI automation is best-effort. Custom-drawn installers may still require keyboard/OCR fallback and can fail.

## Main Modules

| File | Purpose |
|------|---------|
| `main.py` | Guest worker entry point and pipeline orchestration |
| `config.py` | Paths, installer mappings, silent flags, shared constants |
| `utils.py` | DIE classification, process cleanup, window cleanup, file logging |
| `extract_zip.py` | 7-Zip extraction |
| `silent_mode.py` | Silent install execution |
| `gui_install.py` | pywinauto GUI automation and fallbacks |
| `filesystem_monitor.py` | watchdog-based file collection and manifest writing |

