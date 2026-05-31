import argparse
import json
from pathlib import Path

from host_runner.orchestrator import _guest_run_command, run_batch


class FakeBackend:
    def __init__(self):
        self.calls = []

    def restore_snapshot(self, vm_name, snapshot):
        self.calls.append(("restore", vm_name, snapshot))

    def start(self, vm_name, wait_sec):
        self.calls.append(("start", vm_name, wait_sec))

    def stop(self, vm_name):
        self.calls.append(("stop", vm_name))

    def copy_to_guest(self, vm_name, local, guest):
        self.calls.append(("copy_to", vm_name, Path(local).name, guest))

    def copy_from_guest(self, vm_name, guest, local):
        self.calls.append(("copy_from", vm_name, guest, Path(local).name))

    def run_in_guest(self, vm_name, command, timeout_sec):
        self.calls.append(("run", vm_name, command, timeout_sec))
        return 0


def _args(tmp_path):
    input_dir = tmp_path / "installers"
    input_dir.mkdir()
    return argparse.Namespace(
        backend="hyperv",
        vm_name="AutoInstall",
        snapshot="Clean-State",
        input=str(input_dir),
        out=str(tmp_path / "results"),
        run_id="run001",
        boot_wait=1,
        timeout=300,
        guest_arg=[],
    )


def test_guest_run_command_uses_module_entrypoint():
    command = _guest_run_command("run001", ["--workers", "2"])
    assert "python.exe" in command
    assert "-m auto_install.main" in command
    assert "--run-id \"run001\"" in command
    assert "--workers 2" in command


def test_run_batch_calls_backend_and_writes_metadata(tmp_path):
    backend = FakeBackend()
    rc = run_batch(_args(tmp_path), backend=backend)

    assert rc == 0
    assert backend.calls[0] == ("restore", "AutoInstall", "Clean-State")
    assert backend.calls[1] == ("start", "AutoInstall", 1)
    assert backend.calls[-1] == ("stop", "AutoInstall")
    assert any(call[0] == "copy_from" for call in backend.calls)

    metadata_path = tmp_path / "results" / "run001" / "host_run.json"
    with open(metadata_path, encoding="utf-8") as f:
        metadata = json.load(f)

    assert metadata["run_id"] == "run001"
    assert metadata["status"] == "success"
    assert metadata["exit_code"] == 0

