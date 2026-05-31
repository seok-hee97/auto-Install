from abc import ABC, abstractmethod
from pathlib import Path


class VMBackend(ABC):
    """Host-side interface for running commands inside a Windows guest VM."""

    @abstractmethod
    def restore_snapshot(self, vm_name: str, snapshot: str) -> None:
        """Restore the VM to a clean snapshot."""

    @abstractmethod
    def start(self, vm_name: str, wait_sec: int) -> None:
        """Start the VM and wait until it is ready enough for guest commands."""

    @abstractmethod
    def stop(self, vm_name: str) -> None:
        """Stop the VM."""

    @abstractmethod
    def copy_to_guest(self, vm_name: str, local: Path, guest: str) -> None:
        """Copy a host file or directory into the guest."""

    @abstractmethod
    def copy_from_guest(self, vm_name: str, guest: str, local: Path) -> None:
        """Copy a guest file or directory back to the host."""

    @abstractmethod
    def run_in_guest(self, vm_name: str, command: str, timeout_sec: int) -> int:
        """Run a command inside the guest and return its exit code."""

