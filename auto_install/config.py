import os

SYS_DRIVE = os.environ.get('SYSTEMDRIVE', 'C:') + "\\"
DATA_FOLDER = SYS_DRIVE + "Data"

SEVEN_ZIP_EXE = os.path.join(
    os.environ.get('PROGRAMFILES', 'C:\\Program Files'), "7-Zip", "7z.exe"
)
CLASSIFY_TOOL_EXE = os.path.join(
    os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), "Classify-Tool", "ClassifyTool.exe"
)

ZIP_TYPE_LIST = ['binary-archive', 'sfx', 'cab']

INSTALLER_TYPE_LIST = [
    'Inno Setup', '7z installer', 'InstallShield', 'NSIS',
    'Advanced installer', 'Setup Factory', 'Microsoft Installer(MSI)',
    'CreateInstall-Overlay', 'Wise Installer', 'Ghost installer',
    'Acronis installer[ZIP]', 'Windows Installer', 'Sony Windows installer',
    'BitRock installer', 'QT installer', 'WIX Toolset installer'
]

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
