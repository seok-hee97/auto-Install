import csv
import ctypes
import datetime
import logging
import os
import sys
import time

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


def process_gui_install(file_path, installer_type):
    if installer_type in ('Unknown', 'zip'):
        logger.info("Skipping GUI install (unsupported type): %s", file_path)
        return False
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


def main(path):

    setup_logging()

    if not is_admin():
        logger.warning("경고: 관리자 권한으로 실행하지 않으면 UAC 팝업 처리가 불가능합니다.")

    run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    completed_files = load_completed_files(REPORT_PATH)
    if completed_files:
        logger.info("Resume mode: %d files already completed, skipping them", len(completed_files))

    total_files = 0
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

    def record(stage, result):
        records.append({
            "run_id": run_id,
            "file": file_path,
            "installer_type": installer_type,
            "stage": stage,
            "result": result,
            "elapsed_sec": round(time.time() - t0, 1),
        })

    try:
        for root, dirs, files in os.walk(path):
            for file in files:
                # 확장자 사전 필터 — .exe/.msi 외 파일은 diec.exe 호출 없이 건너뜀
                if os.path.splitext(file)[1].lower() not in PROCESSABLE_EXTENSIONS:
                    continue

                file_path = os.path.join(root, file)

                if file_path in completed_files:
                    logger.info("Skipping (already completed): %s", file_path)
                    skipped_cnt += 1
                    continue

                logger.info("Processing: %s", file_path)
                total_files += 1
                t0 = time.time()
                installer_type = classify_installer(file_path)

                if installer_type in ('Error', 'Timeout'):
                    note_file_txt(file_path, title=f'[classify_failed:{installer_type}] : ')
                    logger.warning("Classification failed, skipping: %s (%s)", file_path, installer_type)
                    record("classify", "failed")
                    continue

                # step 1: Extract archive (EXTRACTABLE_TYPES에 속할 때만 시도)
                if process_seven_zip(file_path, installer_type):
                    success_zip_cnt += 1
                    record("zip", "success")
                    continue
                if installer_type in EXTRACTABLE_TYPES:
                    note_file_txt(file_path, title='[zip_failed] : ')
                    record("zip", "failed")

                # zip 타입은 압축해제만 지원 — silent/GUI 시도 불필요
                if installer_type == 'zip':
                    logger.info("Archive extraction failed, skipping: %s", file_path)
                    continue
                time.sleep(5)

                # step 2: Silent mode
                if process_silent_mode(file_path, installer_type):
                    success_silent_cnt += 1
                    record("silent", "success")
                    continue
                note_file_txt(file_path, title='[silent_failed] : ')
                record("silent", "failed")
                time.sleep(5)

                # step 3: GUI Install
                if process_gui_install(file_path, installer_type):
                    success_gui_cnt += 1
                    record("gui", "success")
                    continue

                note_file_txt(file_path, title='[gui_failed] : ')
                record("gui", "failed")
                time.sleep(5)
                logger.warning("All methods failed: %s", file_path)

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


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = sys.argv[1]
        main(path)
    else:
        print("Usage: python main.py <path>")
        sys.exit(1)
