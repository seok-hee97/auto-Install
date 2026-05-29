import os
import time
import sys
import ctypes

from config import SYS_DRIVE, DATA_FOLDER, SEVEN_ZIP_EXE, DIEC_EXE
from extract_zip import extract_archive
from silent_mode import run_silent_install
from gui_install import gui_install
from filesystem_monitor import start_monitoring, stop_monitoring
from utils import classify_installer, verify_folder, note_file_txt


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def process_seven_zip(file_path, installer_type):

    extractable_type = ['7z installer', 'Microsoft Installer(MSI)', 'NSIS', 'Acronis installer[ZIP]', 'zip']

    if installer_type not in extractable_type:
        print("not support archvie format!")
        return False

    extract_path = os.path.join(DATA_FOLDER, os.path.splitext(os.path.basename(file_path))[0])
    if not os.path.exists(extract_path):
        os.makedirs(extract_path)
        print("extract_path : ", extract_path)

    ret_zip = extract_archive(file_path, extract_path)

    if ret_zip:
        installer_count = verify_folder(extract_path)
        if installer_count >= 2:
            print(f"Folder {extract_path} may not have been properly extracted. Installer count: {installer_count}")
            return False
        return True
    else:
        print(f"Failed to extract {file_path}")
        return False


def process_silent_mode(file_path, installer_type):
    return run_silent_install(file_path, installer_type, timeout_sec=180)


def process_gui_install(file_path, installer_type):

    except_type_list = ['Unknown', 'zip']

    if installer_type in except_type_list:
        print(f"Unknown installer type or no gui_install available for: {file_path}")
        return False

    return gui_install(file_path)


def main(path):

    if not is_admin():
        print("경고: 관리자 권한으로 실행하지 않으면 UAC 팝업 처리가 불가능합니다.")

    total_files = 0
    success_zip_cnt = 0
    success_silent_cnt = 0
    success_gui_cnt = 0

    excluded_paths = [
        os.path.dirname(DIEC_EXE),
        os.path.dirname(SEVEN_ZIP_EXE),
        os.path.join(os.getcwd(), "auto_install")
    ]

    observer, monitor = start_monitoring(SYS_DRIVE, DATA_FOLDER, excluded_paths)

    try:
        for root, dirs, files in os.walk(path):
            for file in files:
                file_path = os.path.join(root, file)
                print(f"Processing: {file_path}")

                total_files += 1
                installer_type = classify_installer(file_path)

                # step 1: Extract archive
                if process_seven_zip(file_path, installer_type):
                    success_zip_cnt += 1
                    continue
                note_file_txt(file_path, title='[zip_failed] : ')

                # zip 타입은 압축해제만 지원 — silent/GUI 시도 불필요
                if installer_type == 'zip':
                    print(f"Archive extraction failed, skipping: {file_path}")
                    continue
                time.sleep(5)

                # step 2: Silent mode
                if process_silent_mode(file_path, installer_type):
                    success_silent_cnt += 1
                    continue
                note_file_txt(file_path, title='[silent_failed] : ')
                time.sleep(5)

                # step 3: GUI Install
                if process_gui_install(file_path, installer_type):
                    success_gui_cnt += 1
                    continue

                note_file_txt(file_path, title='[gui_failed] : ')
                time.sleep(5)

                print(f"Failed to process: {file_path}")

        print("-------------------------------")
        print("total_files : ", total_files)
        print("success_zip_cnt :", success_zip_cnt)
        print("success_silent_cnt :", success_silent_cnt)
        print("success_gui_cnt :", success_gui_cnt)
        print("-------------------------------")
    finally:
        stop_monitoring(observer, monitor)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = sys.argv[1]
        main(path)
    else:
        print("Usage: python script_name.py <path>")
        sys.exit(1)
