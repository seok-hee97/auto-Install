import argparse
import csv
import ctypes
import datetime
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import (
    SYS_DRIVE, DATA_FOLDER, SEVEN_ZIP_EXE, DIEC_EXE,
    PACKAGE_DIR, MANIFEST_FILE, COLLECTED_FOLDER,
    PROCESSABLE_EXTENSIONS, EXTRACTABLE_TYPES,
    setup_logging,
)
from extract_zip import extract_archive
from silent_mode import run_silent_install
from gui_install import gui_install
from filesystem_monitor import start_monitoring, stop_monitoring
from utils import classify_installer, verify_folder, note_file_txt

logger = logging.getLogger(__name__)

REPORTS_DIR = os.path.join(DATA_FOLDER, "reports")
REPORT_PATH = os.path.join(REPORTS_DIR, "install_summary.csv")

# tools/ 경로 추가 (Phase 7, 8 모듈 import)
_TOOLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools')
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

# Phase 8: snapshot_diff
try:
    from snapshot_diff import InstallDiff
    _SNAPSHOT_DIFF_AVAILABLE = True
except ImportError:
    _SNAPSHOT_DIFF_AVAILABLE = False

# Phase 7: vm_controller
try:
    from vm_controller import VMSession
    _VM_CONTROLLER_AVAILABLE = True
except ImportError:
    _VM_CONTROLLER_AVAILABLE = False


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def load_completed_files(report_path):
    """이전 실행에서 성공 처리된 파일 경로를 로드해 resume에 활용한다."""
    completed = set()
    if not os.path.exists(report_path):
        return completed
    try:
        with open(report_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("result") == "success":
                    completed.add(row["file"])
    except Exception as e:
        logger.warning("Failed to load completed files: %s", e)
    return completed


def process_seven_zip(file_path, installer_type):
    if installer_type not in EXTRACTABLE_TYPES:
        return False

    extract_path = os.path.join(DATA_FOLDER, os.path.splitext(os.path.basename(file_path))[0])
    if not os.path.exists(extract_path):
        os.makedirs(extract_path)
        logger.info("extract_path: %s", extract_path)

    if not extract_archive(file_path, extract_path):
        logger.warning("Failed to extract: %s", file_path)
        return False

    installer_count = verify_folder(extract_path)
    if installer_count >= 2:
        logger.warning("Folder may not have been properly extracted (%d installers): %s",
                       installer_count, extract_path)
        return False
    return True


def process_silent_mode(file_path, installer_type):
    return run_silent_install(file_path, installer_type, timeout_sec=180)


def process_gui_install(file_path, installer_type, use_snapshot_diff=False):
    if installer_type in ('Unknown', 'zip'):
        logger.info("Skipping GUI install (unsupported type): %s", file_path)
        return False

    if use_snapshot_diff and _SNAPSHOT_DIFF_AVAILABLE:
        with InstallDiff() as diff:
            result = gui_install(file_path)
        new_files = diff.result()
        if new_files:
            logger.info("InstallDiff: %d new files from %s", len(new_files), file_path)
        return result

    return gui_install(file_path)


def write_report(records):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    fieldnames = ["run_id", "file", "installer_type", "stage", "result", "elapsed_sec"]
    write_header = not os.path.exists(REPORT_PATH)
    try:
        with open(REPORT_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerows(records)
        logger.info("Report written: %s", REPORT_PATH)
    except Exception as e:
        logger.error("Failed to write report: %s", e)


# ---------------------------------------------------------------------------
# Phase 9: parallel zip phase
# ---------------------------------------------------------------------------

def _zip_worker(file_path, run_id):
    """zip 추출 전용 워커 — ThreadPoolExecutor에서 병렬 실행."""
    t0 = time.time()
    installer_type = classify_installer(file_path)
    elapsed = round(time.time() - t0, 1)

    if installer_type in ('Error', 'Timeout'):
        note_file_txt(file_path, title=f'[classify_failed:{installer_type}] : ')
        logger.warning("Classification failed: %s (%s)", file_path, installer_type)
        return {
            'record': {'run_id': run_id, 'file': file_path, 'installer_type': installer_type,
                       'stage': 'classify', 'result': 'failed', 'elapsed_sec': elapsed},
            'installer_type': installer_type,
            'zip_success': False,
            'skip_sequential': True,  # 분류 실패 → silent/GUI 건너뜀
        }

    if installer_type in EXTRACTABLE_TYPES:
        zip_ok = process_seven_zip(file_path, installer_type)
        elapsed = round(time.time() - t0, 1)
        if not zip_ok:
            note_file_txt(file_path, title='[zip_failed] : ')
        return {
            'record': {'run_id': run_id, 'file': file_path, 'installer_type': installer_type,
                       'stage': 'zip', 'result': 'success' if zip_ok else 'failed',
                       'elapsed_sec': elapsed},
            'installer_type': installer_type,
            'zip_success': zip_ok,
            # zip 전용 타입(zip)이 실패하면 silent/GUI 건너뜀
            'skip_sequential': zip_ok or installer_type == 'zip',
        }

    # 추출 불필요 → sequential 단계(silent/GUI)로 넘김
    return {
        'record': None,
        'installer_type': installer_type,
        'zip_success': False,
        'skip_sequential': False,
    }


def parallel_zip_phase(file_paths: list, run_id: str, max_workers: int) -> tuple:
    """
    분류 + zip 추출을 병렬로 실행한다.
    Returns: (zip_records, pending_sequential)
        zip_records     — csv에 기록할 결과 목록
        pending_sequential — (file_path, installer_type) sequential 단계 대상
    """
    zip_records = []
    pending = []

    logger.info("Parallel zip phase: %d files, %d workers", len(file_paths), max_workers)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_zip_worker, fp, run_id): fp for fp in file_paths}
        for future in as_completed(futures):
            res = future.result()
            if res['record']:
                zip_records.append(res['record'])
            if not res['skip_sequential']:
                pending.append((futures[future], res['installer_type']))

    return zip_records, pending


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main(path, workers=1, snapshot_diff=False, vm_name='', vm_snapshot='Clean-State',
         vm_backend='hyperv', vm_boot_wait=30):

    setup_logging()

    if not is_admin():
        logger.warning("경고: 관리자 권한으로 실행하지 않으면 UAC 팝업 처리가 불가능합니다.")

    if snapshot_diff and not _SNAPSHOT_DIFF_AVAILABLE:
        logger.warning("--snapshot-diff 요청됐지만 snapshot_diff 모듈을 찾을 수 없습니다. 무시합니다.")
        snapshot_diff = False

    # Phase 7: VM 모드 설정
    use_vm = bool(vm_name) and _VM_CONTROLLER_AVAILABLE
    if use_vm:
        logger.info("VM 모드 활성화: %s / %s / backend=%s", vm_name, vm_snapshot, vm_backend)
    elif vm_name and not _VM_CONTROLLER_AVAILABLE:
        logger.warning("--vm-name 지정됐지만 vm_controller 모듈을 찾을 수 없습니다. VM 모드 비활성.")

    run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    completed_files = load_completed_files(REPORT_PATH)
    if completed_files:
        logger.info("Resume mode: %d files already completed, skipping them", len(completed_files))

    skipped_cnt = 0
    success_zip_cnt = 0
    success_silent_cnt = 0
    success_gui_cnt = 0
    records = []

    excluded_paths = [
        os.path.dirname(DIEC_EXE),
        os.path.dirname(SEVEN_ZIP_EXE),
        DATA_FOLDER,
        str(PACKAGE_DIR),
    ]

    collection_name = os.path.splitext(os.path.basename(os.path.abspath(path)))[0] or "default"
    observer, monitor = start_monitoring(
        SYS_DRIVE, COLLECTED_FOLDER, excluded_paths, MANIFEST_FILE, collection_name
    )

    try:
        # -------------------------------------------------------------------
        # 파일 수집 — 확장자 필터 + resume 스킵
        # -------------------------------------------------------------------
        pending_files = []
        for root, dirs, files in os.walk(path):
            for file in files:
                if os.path.splitext(file)[1].lower() not in PROCESSABLE_EXTENSIONS:
                    continue
                file_path = os.path.join(root, file)
                if file_path in completed_files:
                    logger.info("Skipping (already completed): %s", file_path)
                    skipped_cnt += 1
                    continue
                pending_files.append(file_path)

        total_files = len(pending_files)
        logger.info("Total files to process: %d", total_files)

        # -------------------------------------------------------------------
        # Phase 9: zip 단계 — workers > 1 이면 병렬, 아니면 순차
        # -------------------------------------------------------------------
        if workers > 1:
            zip_records, sequential_pending = parallel_zip_phase(
                pending_files, run_id, max_workers=workers
            )
            for r in zip_records:
                records.append(r)
                if r['stage'] == 'zip' and r['result'] == 'success':
                    success_zip_cnt += 1
        else:
            sequential_pending = []
            for file_path in pending_files:
                t0 = time.time()
                installer_type = classify_installer(file_path)

                def record(stage, result, _fp=file_path, _it=installer_type, _t0=t0):
                    records.append({
                        'run_id': run_id, 'file': _fp,
                        'installer_type': _it,
                        'stage': stage, 'result': result,
                        'elapsed_sec': round(time.time() - _t0, 1),
                    })

                if installer_type in ('Error', 'Timeout'):
                    note_file_txt(file_path, title=f'[classify_failed:{installer_type}] : ')
                    logger.warning("Classification failed, skipping: %s (%s)",
                                   file_path, installer_type)
                    record("classify", "failed")
                    continue

                if process_seven_zip(file_path, installer_type):
                    success_zip_cnt += 1
                    record("zip", "success")
                    continue

                if installer_type in EXTRACTABLE_TYPES:
                    note_file_txt(file_path, title='[zip_failed] : ')
                    record("zip", "failed")

                if installer_type == 'zip':
                    logger.info("Archive extraction failed, skipping: %s", file_path)
                    continue

                sequential_pending.append((file_path, installer_type))

        # -------------------------------------------------------------------
        # Silent + GUI 단계 — 항상 순차 실행 (VM 모드 시 인스톨러별 clean state)
        # -------------------------------------------------------------------
        for file_path, installer_type in sequential_pending:
            t0 = time.time()
            logger.info("Processing: %s", file_path)

            def _record(stage, result, _fp=file_path, _it=installer_type, _t0=t0):
                records.append({
                    'run_id': run_id, 'file': _fp,
                    'installer_type': _it,
                    'stage': stage, 'result': result,
                    'elapsed_sec': round(time.time() - _t0, 1),
                })

            # Phase 7: VM 모드 — 각 인스톨러를 clean state에서 실행
            vm_ctx = VMSession(
                enabled=use_vm,
                vm_name=vm_name,
                snapshot_name=vm_snapshot,
                backend=vm_backend,
                boot_wait=vm_boot_wait,
            ) if use_vm else None
            vm_ok = vm_ctx.__enter__() if vm_ctx else True

            if not vm_ok:
                logger.error("VM 복원 실패, 건너뜀: %s", file_path)
                _record("vm", "failed")
                if vm_ctx:
                    vm_ctx.__exit__(None, None, None)
                continue

            try:
                time.sleep(5)

                if process_silent_mode(file_path, installer_type):
                    success_silent_cnt += 1
                    _record("silent", "success")
                    continue
                note_file_txt(file_path, title='[silent_failed] : ')
                _record("silent", "failed")
                time.sleep(5)

                if process_gui_install(file_path, installer_type, use_snapshot_diff=snapshot_diff):
                    success_gui_cnt += 1
                    _record("gui", "success")
                    continue

                note_file_txt(file_path, title='[gui_failed] : ')
                _record("gui", "failed")
                time.sleep(5)
                logger.warning("All methods failed: %s", file_path)

            finally:
                if vm_ctx:
                    vm_ctx.__exit__(None, None, None)

        logger.info("-------------------------------")
        logger.info("skipped (resumed)  : %d", skipped_cnt)
        logger.info("total_files        : %d", total_files)
        logger.info("success_zip        : %d", success_zip_cnt)
        logger.info("success_silent     : %d", success_silent_cnt)
        logger.info("success_gui        : %d", success_gui_cnt)
        logger.info("-------------------------------")

        write_report(records)

    finally:
        stop_monitoring(observer, monitor)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="auto-Install: Windows installer batch automation"
    )
    parser.add_argument('path', help='Folder containing installer files (.exe / .msi)')
    parser.add_argument(
        '--workers', type=int, default=1, metavar='N',
        help='Parallel workers for zip extraction phase (default: 1, sequential)'
    )
    parser.add_argument(
        '--snapshot-diff', action='store_true',
        help='Enable pre/post install filesystem diff via snapshot_diff (Phase 8)'
    )
    parser.add_argument(
        '--vm-name', default='', metavar='NAME',
        help='VM name for clean-state snapshot mode (Phase 7, requires vm_controller)'
    )
    parser.add_argument(
        '--vm-snapshot', default='Clean-State', metavar='SNAPSHOT',
        help='VM snapshot name to restore before each installer (default: Clean-State)'
    )
    parser.add_argument(
        '--vm-backend', default='hyperv', choices=['hyperv', 'virtualbox'],
        help='VM hypervisor backend (default: hyperv)'
    )
    parser.add_argument(
        '--vm-boot-wait', type=int, default=30, metavar='SEC',
        help='Seconds to wait after VM start before installing (default: 30)'
    )
    args = parser.parse_args()
    main(
        args.path,
        workers=args.workers,
        snapshot_diff=args.snapshot_diff,
        vm_name=args.vm_name,
        vm_snapshot=args.vm_snapshot,
        vm_backend=args.vm_backend,
        vm_boot_wait=args.vm_boot_wait,
    )
