import os
import subprocess
import time
from pathlib import Path

from host_runner.backends.base import VMBackend


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class HyperVBackend(VMBackend):
    """
    Hyper-V backend using PowerShell Direct.

    Required environment variables for guest operations:
      AUTOINSTALL_GUEST_USERNAME
      AUTOINSTALL_GUEST_PASSWORD

    The guest must have PowerShell Direct support and a local account matching
    those credentials. The host must run with permissions to control the VM.
    """

    def __init__(self, powershell: str = "powershell"):
        self.powershell = powershell

    def _run_ps(self, script: str, timeout_sec: int = 300) -> subprocess.CompletedProcess:
        return subprocess.run(
            [self.powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )

    def _credential_script(self) -> str:
        username = os.environ.get("AUTOINSTALL_GUEST_USERNAME")
        password = os.environ.get("AUTOINSTALL_GUEST_PASSWORD")
        if not username or not password:
            raise RuntimeError(
                "AUTOINSTALL_GUEST_USERNAME and AUTOINSTALL_GUEST_PASSWORD are required"
            )
        return (
            f"$sec = ConvertTo-SecureString {_ps_quote(password)} -AsPlainText -Force; "
            f"$cred = New-Object System.Management.Automation.PSCredential"
            f"({_ps_quote(username)}, $sec); "
        )

    def _session_script(self, vm_name: str, body: str) -> str:
        return (
            self._credential_script()
            + f"$session = New-PSSession -VMName {_ps_quote(vm_name)} -Credential $cred; "
            + "try { "
            + body
            + " } finally { if ($session) { Remove-PSSession $session } }"
        )

    def restore_snapshot(self, vm_name: str, snapshot: str) -> None:
        script = (
            f"Restore-VMCheckpoint -VMName {_ps_quote(vm_name)} "
            f"-Name {_ps_quote(snapshot)} -Confirm:$false"
        )
        self._run_ps(script)

    def start(self, vm_name: str, wait_sec: int) -> None:
        self._run_ps(f"Start-VM -Name {_ps_quote(vm_name)}")
        time.sleep(wait_sec)

    def stop(self, vm_name: str) -> None:
        self._run_ps(f"Stop-VM -Name {_ps_quote(vm_name)} -Force")

    def copy_to_guest(self, vm_name: str, local: Path, guest: str) -> None:
        local = local.resolve()
        script = self._session_script(
            vm_name,
            "Copy-Item "
            f"-ToSession $session -Path {_ps_quote(str(local))} "
            f"-Destination {_ps_quote(guest)} -Recurse -Force",
        )
        self._run_ps(script)

    def copy_from_guest(self, vm_name: str, guest: str, local: Path) -> None:
        local.parent.mkdir(parents=True, exist_ok=True)
        script = self._session_script(
            vm_name,
            "Copy-Item "
            f"-FromSession $session -Path {_ps_quote(guest)} "
            f"-Destination {_ps_quote(str(local))} -Recurse -Force",
        )
        self._run_ps(script)

    def run_in_guest(self, vm_name: str, command: str, timeout_sec: int) -> int:
        script = self._session_script(
            vm_name,
            "$result = Invoke-Command -Session $session "
            f"-ScriptBlock {{ cmd.exe /c {_ps_quote(command)} }}; "
            "if ($LASTEXITCODE -ne $null) { exit $LASTEXITCODE }",
        )
        try:
            completed = self._run_ps(script, timeout_sec=timeout_sec)
            return completed.returncode
        except subprocess.CalledProcessError as e:
            return e.returncode

