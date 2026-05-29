import os
import subprocess

from config import SEVEN_ZIP_EXE


def extract_archive(file_path, extract_path, seven_zip_path=SEVEN_ZIP_EXE):

    if not os.path.exists(seven_zip_path):
        print(f"Error: 7-Zip not found at {seven_zip_path}")
        return False

    try:
        result = subprocess.run(
            [seven_zip_path, "x", file_path, f"-o{extract_path}", "-y"],
            capture_output=True, text=True, timeout=180
        )
        if result.returncode != 0:
            print(f"Error extracting {file_path}: {result.stderr}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print(f"Timeout occurred while extracting {file_path}")
        return False
    except Exception as e:
        print(f"Unexpected error occurred while extracting {file_path}: {e}")
        return False
