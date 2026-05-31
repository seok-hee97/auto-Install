import argparse
import datetime
import json
import logging
import tempfile
import zipfile
from pathlib import Path

from host_runner.backends.hyperv import HyperVBackend
from host_runner.backends.virtualbox import VirtualBoxBackend
from host_runner.paths import (
    GUEST_APP,
    GUEST_DATA,
    GUEST_INPUT,
    GUEST_OUTPUT,
    GUEST_PYTHON,
    GUEST_RESULT_ZIP,
    PROJECT_ROOT,
)

logger = logging.getLogger(__name__)

_ARCHIVE_EXCLUDED_DIRS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "results",
    "backup",
}

_ARCHIVE_EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
}


def create_backend(name: str):
    if name == "hyperv":
        return HyperVBackend()
    if name == "virtualbox":
        return VirtualBoxBackend()
    raise ValueError(f"Unsupported backend: {name}")


def _cmd_quote(value: str) -> str:
    return '"' + value.replace('"', r'\"') + '"'


def _guest_prepare_command() -> str:
    return (
        f'if exist {_cmd_quote(GUEST_APP)} rmdir /s /q {_cmd_quote(GUEST_APP)} && '
        f'if exist {_cmd_quote(GUEST_INPUT)} rmdir /s /q {_cmd_quote(GUEST_INPUT)} && '
        f'if exist {_cmd_quote(GUEST_OUTPUT)} rmdir /s /q {_cmd_quote(GUEST_OUTPUT)} && '
        f'mkdir {_cmd_quote(GUEST_APP)} && '
        f'mkdir {_cmd_quote(GUEST_INPUT)} && '
        f'mkdir {_cmd_quote(GUEST_OUTPUT)}'
    )


def _guest_unpack_project_command() -> str:
    archive = GUEST_OUTPUT + r"\project.zip"
    return (
        'powershell -NoProfile -ExecutionPolicy Bypass -Command '
        f'"Expand-Archive -Path \'{archive}\' -DestinationPath \'{GUEST_APP}\' -Force"'
    )


def _guest_run_command(run_id: str, extra_args=None) -> str:
    args = extra_args or []
    joined_args = " ".join(args)
    return (
        f'cd /d {_cmd_quote(GUEST_APP)} && '
        f'{_cmd_quote(GUEST_PYTHON)} -m auto_install.main '
        f'{_cmd_quote(GUEST_INPUT)} --run-id {_cmd_quote(run_id)} {joined_args}'
    ).strip()


def _guest_pack_results_command() -> str:
    paths = [
        GUEST_DATA + r"\reports",
        GUEST_DATA + r"\collected",
        GUEST_DATA + r"\manifest.jsonl",
        GUEST_DATA + r"\log_files.txt",
        GUEST_DATA + r"\run.log",
    ]
    path_list = ",".join("'" + path + "'" for path in paths)
    return (
        'powershell -NoProfile -ExecutionPolicy Bypass -Command '
        '"$paths = @(' + path_list + ') | Where-Object { Test-Path $_ }; '
        "if (Test-Path '" + GUEST_RESULT_ZIP + "') { Remove-Item '" + GUEST_RESULT_ZIP + "' -Force }; "
        "if ($paths.Count -eq 0) { New-Item -ItemType Directory -Force '" + GUEST_OUTPUT + r"\empty' | Out-Null; "
        "$paths = @('" + GUEST_OUTPUT + r"\empty') }; "
        "Compress-Archive -Path $paths -DestinationPath '" + GUEST_RESULT_ZIP + '\' -Force"'
    )


def _make_project_archive(run_id: str) -> Path:
    archive_path = Path(tempfile.gettempdir()) / f"auto_install_project_{run_id}.zip"
    if archive_path.exists():
        archive_path.unlink()

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in PROJECT_ROOT.rglob("*"):
            rel = path.relative_to(PROJECT_ROOT)
            if any(part in _ARCHIVE_EXCLUDED_DIRS for part in rel.parts):
                continue
            if path.is_file() and path.suffix.lower() not in _ARCHIVE_EXCLUDED_SUFFIXES:
                zf.write(path, rel)

    return archive_path


def run_batch(args, backend=None) -> int:
    run_id = args.run_id or datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.out).resolve() / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    backend = backend or create_backend(args.backend)
    host_result_zip = output_dir / "guest_result.zip"
    metadata = {
        "run_id": run_id,
        "backend": args.backend,
        "vm_name": args.vm_name,
        "snapshot": args.snapshot,
        "input": str(Path(args.input).resolve()),
        "output": str(output_dir),
        "guest_input": GUEST_INPUT,
        "guest_result_zip": GUEST_RESULT_ZIP,
        "status": "started",
        "exit_code": None,
    }

    rc = 1
    project_archive = None
    try:
        logger.info("Restoring VM snapshot: %s / %s", args.vm_name, args.snapshot)
        backend.restore_snapshot(args.vm_name, args.snapshot)
        logger.info("Starting VM: %s", args.vm_name)
        backend.start(args.vm_name, args.boot_wait)

        backend.run_in_guest(args.vm_name, _guest_prepare_command(), timeout_sec=120)
        project_archive = _make_project_archive(run_id)
        backend.copy_to_guest(args.vm_name, project_archive, GUEST_OUTPUT + r"\project.zip")
        backend.run_in_guest(args.vm_name, _guest_unpack_project_command(), timeout_sec=300)
        backend.copy_to_guest(args.vm_name, Path(args.input).resolve(), GUEST_INPUT)

        logger.info("Running guest worker: %s", run_id)
        rc = backend.run_in_guest(
            args.vm_name,
            _guest_run_command(run_id, args.guest_arg),
            timeout_sec=args.timeout,
        )
        metadata["exit_code"] = rc

        backend.run_in_guest(args.vm_name, _guest_pack_results_command(), timeout_sec=300)
        backend.copy_from_guest(args.vm_name, GUEST_RESULT_ZIP, host_result_zip)
        metadata["status"] = "success" if rc == 0 else "guest_failed"
        return rc

    except Exception as e:
        metadata["status"] = "host_failed"
        metadata["error"] = str(e)
        logger.error("Host orchestration failed: %s", e)
        return 1
    finally:
        try:
            backend.stop(args.vm_name)
        except Exception as e:
            logger.warning("Failed to stop VM: %s", e)
        if project_archive and project_archive.exists():
            project_archive.unlink()
        with open(output_dir / "host_run.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Host-side VM orchestrator for auto-Install guest runs"
    )
    parser.add_argument("--backend", choices=["hyperv", "virtualbox"], default="hyperv")
    parser.add_argument("--vm-name", required=True)
    parser.add_argument("--snapshot", default="Clean-State")
    parser.add_argument("--input", required=True, help="Host path containing installer files")
    parser.add_argument("--out", required=True, help="Host output directory for run results")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--boot-wait", type=int, default=30)
    parser.add_argument("--timeout", type=int, default=7200)
    parser.add_argument(
        "--guest-arg",
        action="append",
        default=[],
        help="Additional argument passed to auto_install.main inside the guest",
    )
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = build_parser().parse_args()
    raise SystemExit(run_batch(args))


if __name__ == "__main__":
    main()
