import os
import subprocess
import time
from pathlib import Path
from typing import Optional

from host_runner.backends.base import VMBackend


class VirtualBoxBackend(VMBackend):
    """
    VirtualBox backend using VBoxManage guestcontrol.

    Required environment variables:
      AUTOINSTALL_GUEST_USERNAME
      AUTOINSTALL_GUEST_PASSWORD

    The guest must have VirtualBox Guest Additions installed.
    """

    def __init__(self, vboxmanage: Optional[str] = None):
        self.vboxmanage = vboxmanage or os.environ.get("VBOXMANAGE_EXE", "VBoxManage")

    def _guest_auth(self) -> list[str]:
        username = os.environ.get("AUTOINSTALL_GUEST_USERNAME")
        password = os.environ.get("AUTOINSTALL_GUEST_PASSWORD")
        if not username or not password:
            raise RuntimeError(
                "AUTOINSTALL_GUEST_USERNAME and AUTOINSTALL_GUEST_PASSWORD are required"
            )
        return ["--username", username, "--password", password]

    def _run(self, args: list[str], timeout_sec: int = 300, check: bool = True):
        return subprocess.run(
            [self.vboxmanage] + args,
            check=check,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )

    def restore_snapshot(self, vm_name: str, snapshot: str) -> None:
        self._run(["controlvm", vm_name, "poweroff"], check=False)
        time.sleep(3)
        self._run(["snapshot", vm_name, "restore", snapshot])

    def start(self, vm_name: str, wait_sec: int) -> None:
        self._run(["startvm", vm_name, "--type", "headless"])
        time.sleep(wait_sec)

    def stop(self, vm_name: str) -> None:
        self._run(["controlvm", vm_name, "poweroff"])

    def copy_to_guest(self, vm_name: str, local: Path, guest: str) -> None:
        self._run(["guestcontrol", vm_name, "copyto"] + self._guest_auth() + [
            "--recursive",
            str(local.resolve()),
            guest,
        ])

    def copy_from_guest(self, vm_name: str, guest: str, local: Path) -> None:
        local.parent.mkdir(parents=True, exist_ok=True)
        self._run(["guestcontrol", vm_name, "copyfrom"] + self._guest_auth() + [
            "--recursive",
            guest,
            str(local),
        ])

    def run_in_guest(self, vm_name: str, command: str, timeout_sec: int) -> int:
        completed = self._run(
            ["guestcontrol", vm_name, "run"] + self._guest_auth() + [
                "--exe", "C:\\Windows\\System32\\cmd.exe",
                "--",
                "cmd.exe",
                "/c",
                command,
            ],
            timeout_sec=timeout_sec,
            check=False,
        )
        return completed.returncode
