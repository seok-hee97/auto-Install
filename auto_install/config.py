import os
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = Path(__file__).resolve().parent

SYS_DRIVE = os.environ.get('SYSTEMDRIVE', 'C:') + "\\"
DATA_FOLDER = SYS_DRIVE + "Data"
LOG_FILE = os.path.join(DATA_FOLDER, "log_files.txt")
COLLECTED_FOLDER = os.path.join(DATA_FOLDER, "collected")
MANIFEST_FILE = os.path.join(DATA_FOLDER, "manifest.jsonl")

SEVEN_ZIP_EXE = os.path.join(
    os.environ.get('PROGRAMFILES', 'C:\\Program Files'), "7-Zip", "7z.exe"
)
DIEC_EXE = os.path.join(
    os.environ.get('PROGRAMFILES', 'C:\\Program Files'), "DIE", "diec.exe"
)

INSTALLER_TYPE_LIST = [
    'Inno Setup', '7z installer', 'InstallShield', 'NSIS',
    'Advanced installer', 'Setup Factory', 'Microsoft Installer(MSI)',
    'CreateInstall-Overlay', 'Wise Installer', 'Ghost installer',
    'Acronis installer[ZIP]', 'Windows Installer', 'Sony Windows installer',
    'BitRock installer', 'QT installer', 'WIX Toolset installer'
]

# DIE type="Installer" name → INSTALLER_TYPE_LIST 매핑 (소문자 키)
DIE_INSTALLER_MAP = {
    "nsis": "NSIS",
    "inno setup": "Inno Setup",
    "installshield": "InstallShield",
    "wix": "WIX Toolset installer",
    "wise installer": "Wise Installer",
    "wise": "Wise Installer",
    "advanced installer": "Advanced installer",
    "setup factory": "Setup Factory",
    "bitrock": "BitRock installer",
    "createinstall": "CreateInstall-Overlay",
    "ghost installer": "Ghost installer",
    "ghost": "Ghost installer",
    "acronis": "Acronis installer[ZIP]",
    "windows installer": "Windows Installer",
    "sony": "Sony Windows installer",
    "qt installer": "QT installer",
    "qt": "QT installer",
    "msi": "Microsoft Installer(MSI)",
}

# DIE type="SFX" name → INSTALLER_TYPE_LIST 매핑 (소문자 키)
DIE_SFX_MAP = {
    "7-zip": "7z installer",
    "7zip": "7z installer",
}

RUN_LOG_FILE = os.path.join(DATA_FOLDER, "run.log")


def setup_logging():
    os.makedirs(DATA_FOLDER, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(RUN_LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


SILENT_COMMANDS = {
    "7z installer": ["/S"],
    "Acronis installer[ZIP]": ["/quiet"],
    "Advanced installer": ["/quiet"],
    "BitRock installer": ["--mode", "unattended"],
    "CreateInstall-Overlay": ["-silent"],
    "Ghost installer": ["/S"],
    "Inno Setup": ["/VERYSILENT", "/SUPPRESSMSGBOXES"],
    "InstallShield": ["/s"],
    "Microsoft Installer(MSI)": ["/qn"],
    "NSIS": ["/S"],
    "QT installer": ["--accept-licenses", "--default-answer", "--confirm-command", "install"],
    "Setup Factory": ["/S"],
    "Sony Windows installer": ["/q"],
    "Windows Installer": ["/qn"],
    "Wise Installer": ["/s"],
    "WIX Toolset installer": ["/q"]
}
