import csv
import ctypes
import logging
import os
import sys
import time

from config import (
    SYS_DRIVE, DATA_FOLDER, SEVEN_ZIP_EXE, DIEC_EXE,
    PACKAGE_DIR, MANIFEST_FILE, COLLECTED_FOLDER,
    setup_logging,
)
from extract_zip import extract_archive
from silent_mode import run_silent_install
from gui_install import gui_install
from filesystem_monitor import start_monitoring, stop_monitoring
from utils import classify_installer, verify_folder, note_file_txt

logger = logging.getLogger(__name__)

REPORTS_DIR = os.path.join(DATA_FOLDER, "reports")


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def process_seven_zip(file_path, installer_type):

    extractable_type = ['7z installer', 'Microsoft Installer(MSI)', 'NSIS', 'Acronis installer[ZIP]', 'zip']

    if installer_type not in extractable_type:
        return False

    extract_path = os.path.join(DATA_FOLDER, os.path.splitext(os.path.basename(file_path))[0])
    if not os.path.exists(extract_path):
        os.makedirs(extract_path)
        logger.info("extract_path: %s", extract_path)

    ret_zip = extract_archive(file_path, extract_path)

    if ret_zip:
        installer_count = verify_folder(extract_path)
        if installer_count >= 2:
            logger.warning("Folder may not have been properly extracted (%d installers): %s",
                           installer_count, extract_path)
            return False
        return True
    else:
        logger.warning("Failed to extract: %s", file_path)
        return False


def process_silent_mode(file_path, installer_type):
    return run_silent_install(file_path, installer_type, timeout_sec=180)


def process_gui_install(file_path, installer_type):

    except_type_list = ['Unknown', 'zip']

    if installer_type in except_type_list:
        logger.info("Skipping GUI install (unsupported type): %s", file_path)
        return False

    return gui_install(file_path)


def write_report(records):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    report_path = os.path.join(REPORTS_DIR, "install_summary.csv")
    fieldnames = ["file", "installer_type", "stage", "result", "elapsed_sec"]
    write_header = not os.path.exists(report_path)
    try:
        with open(report_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerows(records)
        logger.info("Report written: %s", report_path)
    except Exception as e:
        logger.error("Failed to write report: %s", e)


def main(path):

    setup_logging()

    if not is_admin():
        logger.warning("경고: 관리자 권한으로 실행하지 않으면 UAC 팝업 처리가 불가능합니다.")

    total_files = 0
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
        for root, dirs, files in os.walk(path):
            for file in files:
                file_path = os.path.join(root, file)
                logger.info("Processing: %s", file_path)

                total_files += 1
                t0 = time.time()
                installer_type = classify_installer(file_path)

                if installer_type in ('Error', 'Timeout'):
                    note_file_txt(file_path, title=f'[classify_failed:{installer_type}] : ')
                    logger.warning("Classification failed, skipping: %s (%s)", file_path, installer_type)
                    records.append({"file": file_path, "installer_type": installer_type,
                                    "stage": "classify", "result": "failed",
                                    "elapsed_sec": round(time.time() - t0, 1)})
                    continue

                # step 1: Extract archive
                if process_seven_zip(file_path, installer_type):
                    success_zip_cnt += 1
                    records.append({"file": file_path, "installer_type": installer_type,
                                    "stage": "zip", "result": "success",
                                    "elapsed_sec": round(time.time() - t0, 1)})
                    continue
                note_file_txt(file_path, title='[zip_failed] : ')

                # zip 타입은 압축해제만 지원 — silent/GUI 시도 불필요
                if installer_type == 'zip':
                    logger.info("Archive extraction failed, skipping: %s", file_path)
                    records.append({"file": file_path, "installer_type": installer_type,
                                    "stage": "zip", "result": "failed",
                                    "elapsed_sec": round(time.time() - t0, 1)})
                    continue
                time.sleep(5)

                # step 2: Silent mode
                if process_silent_mode(file_path, installer_type):
                    success_silent_cnt += 1
                    records.append({"file": file_path, "installer_type": installer_type,
                                    "stage": "silent", "result": "success",
                                    "elapsed_sec": round(time.time() - t0, 1)})
                    continue
                note_file_txt(file_path, title='[silent_failed] : ')
                time.sleep(5)

                # step 3: GUI Install
                if process_gui_install(file_path, installer_type):
                    success_gui_cnt += 1
                    records.append({"file": file_path, "installer_type": installer_type,
                                    "stage": "gui", "result": "success",
                                    "elapsed_sec": round(time.time() - t0, 1)})
                    continue

                note_file_txt(file_path, title='[gui_failed] : ')
                time.sleep(5)
                logger.warning("All methods failed: %s", file_path)
                records.append({"file": file_path, "installer_type": installer_type,
                                "stage": "gui", "result": "failed",
                                "elapsed_sec": round(time.time() - t0, 1)})

        logger.info("-------------------------------")
        logger.info("total_files    : %d", total_files)
        logger.info("success_zip    : %d", success_zip_cnt)
        logger.info("success_silent : %d", success_silent_cnt)
        logger.info("success_gui    : %d", success_gui_cnt)
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
