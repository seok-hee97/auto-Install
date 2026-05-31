"""
Phase 7: VM 스냅샷 자동화 — Hyper-V (Windows) / VirtualBox (cross-platform) 지원

환경변수:
    AUTOINSTALL_VM_MODE     = 1 (활성화, 기본 0)
    AUTOINSTALL_VM_NAME     = VM 이름
    AUTOINSTALL_VM_SNAPSHOT = 스냅샷 이름 (기본: Clean-State)
    AUTOINSTALL_VM_BACKEND  = hyperv | virtualbox (기본: hyperv)
    VBOXMANAGE_EXE          = VBoxManage 실행 경로 (기본: VBoxManage)

CLI:
    python tools/vm_controller.py restore --vm <name> [--snapshot <name>]
    python tools/vm_controller.py start   --vm <name>
    python tools/vm_controller.py stop    --vm <name>
    python tools/vm_controller.py cycle   --vm <name> [--snapshot <name>]
"""

import argparse
import logging
import os
import subprocess
import sys
import time

logger = logging.getLogger(__name__)

VM_NAME = os.environ.get('AUTOINSTALL_VM_NAME', '')
VM_SNAPSHOT = os.environ.get('AUTOINSTALL_VM_SNAPSHOT', 'Clean-State')
VM_BACKEND = os.environ.get('AUTOINSTALL_VM_BACKEND', 'hyperv').lower()
VBOXMANAGE = os.environ.get('VBOXMANAGE_EXE', 'VBoxManage')


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _normalize_backend(backend: str = VM_BACKEND) -> str:
    return (backend or VM_BACKEND).lower()


def restore_snapshot(
    vm_name: str = VM_NAME,
    snapshot_name: str = VM_SNAPSHOT,
    backend: str = VM_BACKEND,
) -> bool:
    """VM을 지정 스냅샷 상태로 복원한다."""
    backend = _normalize_backend(backend)
    if backend == 'hyperv':
        return _hyperv_restore(vm_name, snapshot_name)
    if backend == 'virtualbox':
        return _vbox_restore(vm_name, snapshot_name)
    logger.error("Unknown VM backend: %s", backend)
    return False


def start_vm(vm_name: str = VM_NAME, wait_sec: int = 30, backend: str = VM_BACKEND) -> bool:
    """VM을 시작하고 부팅 완료까지 대기한다."""
    backend = _normalize_backend(backend)
    if backend == 'hyperv':
        return _hyperv_start(vm_name, wait_sec)
    if backend == 'virtualbox':
        return _vbox_start(vm_name, wait_sec)
    return False


def stop_vm(vm_name: str = VM_NAME, backend: str = VM_BACKEND) -> bool:
    """VM을 강제 종료한다."""
    backend = _normalize_backend(backend)
    if backend == 'hyperv':
        return _hyperv_stop(vm_name)
    if backend == 'virtualbox':
        return _vbox_stop(vm_name)
    return False


# ---------------------------------------------------------------------------
# Hyper-V backend (Windows PowerShell)
# ---------------------------------------------------------------------------

def _hyperv_restore(vm_name: str, snapshot_name: str) -> bool:
    try:
        subprocess.run(
            ["powershell", "-Command",
             f'Restore-VMCheckpoint -VMName "{vm_name}" '
             f'-Name "{snapshot_name}" -Confirm:$false'],
            check=True, capture_output=True,
        )
        logger.info("Hyper-V snapshot restored: %s -> %s", vm_name, snapshot_name)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Hyper-V restore failed: %s", e.stderr.decode(errors='replace'))
        return False
    except FileNotFoundError:
        logger.error("powershell not found — Hyper-V backend requires Windows")
        return False


def _hyperv_start(vm_name: str, wait_sec: int) -> bool:
    try:
        subprocess.run(
            ["powershell", "-Command", f'Start-VM -Name "{vm_name}"'],
            check=True, capture_output=True,
        )
        logger.info("Hyper-V VM started: %s (waiting %ds for boot)", vm_name, wait_sec)
        time.sleep(wait_sec)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Hyper-V start failed: %s", e.stderr.decode(errors='replace'))
        return False


def _hyperv_stop(vm_name: str) -> bool:
    try:
        subprocess.run(
            ["powershell", "-Command", f'Stop-VM -Name "{vm_name}" -Force'],
            check=True, capture_output=True,
        )
        logger.info("Hyper-V VM stopped: %s", vm_name)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Hyper-V stop failed: %s", e.stderr.decode(errors='replace'))
        return False


# ---------------------------------------------------------------------------
# VirtualBox backend (VBoxManage)
# ---------------------------------------------------------------------------

def _vbox_restore(vm_name: str, snapshot_name: str) -> bool:
    try:
        # 실행 중인 VM 먼저 종료 (실패해도 계속)
        subprocess.run([VBOXMANAGE, "controlvm", vm_name, "poweroff"], capture_output=True)
        time.sleep(3)
        subprocess.run(
            [VBOXMANAGE, "snapshot", vm_name, "restore", snapshot_name],
            check=True, capture_output=True,
        )
        logger.info("VirtualBox snapshot restored: %s -> %s", vm_name, snapshot_name)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("VirtualBox restore failed: %s", e.stderr.decode(errors='replace'))
        return False
    except FileNotFoundError:
        logger.error("VBoxManage not found at: %s", VBOXMANAGE)
        return False


def _vbox_start(vm_name: str, wait_sec: int) -> bool:
    try:
        subprocess.run(
            [VBOXMANAGE, "startvm", vm_name, "--type", "headless"],
            check=True, capture_output=True,
        )
        logger.info("VirtualBox VM started: %s (waiting %ds for boot)", vm_name, wait_sec)
        time.sleep(wait_sec)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("VirtualBox start failed: %s", e.stderr.decode(errors='replace'))
        return False


def _vbox_stop(vm_name: str) -> bool:
    try:
        subprocess.run(
            [VBOXMANAGE, "controlvm", vm_name, "poweroff"],
            check=True, capture_output=True,
        )
        logger.info("VirtualBox VM stopped: %s", vm_name)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("VirtualBox stop failed: %s", e.stderr.decode(errors='replace'))
        return False


# ---------------------------------------------------------------------------
# Context manager — per-installer clean state
# ---------------------------------------------------------------------------

class VMSession:
    """
    각 인스톨러를 독립된 clean state에서 실행하기 위한 컨텍스트 매니저.
    enabled=False 이면 no-op으로 동작한다.

    Example:
        with VMSession() as ok:
            if ok:
                run_installer(...)
    """

    def __init__(
        self,
        enabled: bool = False,
        vm_name: str = VM_NAME,
        snapshot_name: str = VM_SNAPSHOT,
        backend: str = VM_BACKEND,
        boot_wait: int = 30,
    ):
        self.enabled = enabled
        self.vm_name = vm_name
        self.snapshot_name = snapshot_name
        self.backend = _normalize_backend(backend)
        self.boot_wait = boot_wait

    def __enter__(self) -> bool:
        if not self.enabled:
            return True
        ok = restore_snapshot(self.vm_name, self.snapshot_name, self.backend)
        if ok:
            ok = start_vm(self.vm_name, self.boot_wait, self.backend)
        return ok

    def __exit__(self, *_):
        if self.enabled:
            stop_vm(self.vm_name, self.backend)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="VM snapshot controller")
    parser.add_argument('action', choices=['restore', 'start', 'stop', 'cycle'],
                        help='cycle = restore + start (boot wait) + stop')
    parser.add_argument('--vm', default=VM_NAME, required=not VM_NAME,
                        help='VM name (or set AUTOINSTALL_VM_NAME)')
    parser.add_argument('--snapshot', default=VM_SNAPSHOT)
    parser.add_argument('--backend', default=VM_BACKEND,
                        choices=['hyperv', 'virtualbox'])
    parser.add_argument('--wait', type=int, default=30,
                        help='Boot wait seconds for start/cycle (default: 30)')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    if args.action == 'restore':
        sys.exit(0 if restore_snapshot(args.vm, args.snapshot, args.backend) else 1)
    elif args.action == 'start':
        sys.exit(0 if start_vm(args.vm, args.wait, args.backend) else 1)
    elif args.action == 'stop':
        sys.exit(0 if stop_vm(args.vm, args.backend) else 1)
    elif args.action == 'cycle':
        ok = restore_snapshot(args.vm, args.snapshot, args.backend) and start_vm(
            args.vm, args.wait, args.backend
        )
        time.sleep(5)
        stop_vm(args.vm, args.backend)
        sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
