import logging
import os
import subprocess

from config import SEVEN_ZIP_EXE

logger = logging.getLogger(__name__)


def extract_archive(file_path, extract_path, seven_zip_path=SEVEN_ZIP_EXE):

    if not os.path.exists(seven_zip_path):
        logger.error("7-Zip not found at %s", seven_zip_path)
        return False

    try:
        result = subprocess.run(
            [seven_zip_path, "x", file_path, f"-o{extract_path}", "-y"],
            capture_output=True, text=True, timeout=180
        )
        if result.returncode != 0:
            logger.warning("Error extracting %s: %s", file_path, result.stderr)
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.warning("Timeout while extracting %s", file_path)
        return False
    except Exception as e:
        logger.error("Unexpected error extracting %s: %s", file_path, e)
        return False
