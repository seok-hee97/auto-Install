"""
ClassifyTool.exe vs diec.exe 파리티 검증 스크립트

사용법:
    python tools/verify_diec_parity.py <installer_folder>

필요 환경 (Windows):
    - ClassifyTool.exe: C:\Program Files (x86)\Classify-Tool\ClassifyTool.exe
    - diec.exe:         C:\Program Files\DIE\diec.exe
"""

import os
import sys
import json
import subprocess

CLASSIFY_TOOL_EXE = os.path.join(
    os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'),
    "Classify-Tool", "ClassifyTool.exe"
)
DIEC_EXE = os.path.join(
    os.environ.get('PROGRAMFILES', 'C:\\Program Files'),
    "DIE", "diec.exe"
)

ZIP_TYPE_LIST = ['binary-archive', 'sfx', 'cab']

INSTALLER_TYPE_LIST = [
    'Inno Setup', '7z installer', 'InstallShield', 'NSIS',
    'Advanced installer', 'Setup Factory', 'Microsoft Installer(MSI)',
    'CreateInstall-Overlay', 'Wise Installer', 'Ghost installer',
    'Acronis installer[ZIP]', 'Windows Installer', 'Sony Windows installer',
    'BitRock installer', 'QT installer', 'WIX Toolset installer'
]

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

DIE_SFX_MAP = {
    "7-zip": "7z installer",
    "7zip": "7z installer",
}


def classify_old(file_path: str) -> str:
    try:
        result = subprocess.run(
            [CLASSIFY_TOOL_EXE, file_path],
            capture_output=True, timeout=60
        )
        output = result.stdout.decode('latin-1').split('->')[-1].strip()

        if any(z in output.lower() for z in ZIP_TYPE_LIST):
            return 'zip'
        if "Installer:" in output:
            info = output.split("Installer:")[-1].strip()
            for t in INSTALLER_TYPE_LIST:
                if t in info:
                    return t
        return 'Unknown'
    except subprocess.TimeoutExpired:
        return 'Timeout'
    except Exception as e:
        return f'Error({e})'


def classify_new(file_path: str) -> str:
    try:
        result = subprocess.run(
            [DIEC_EXE, "--json", file_path],
            capture_output=True, timeout=60
        )
        data = json.loads(result.stdout)

        for detect in data.get("detects", []):
            filetype = detect.get("filetype", "").lower()
            if filetype in {"cab", "archive"}:
                return "zip"
            for value in detect.get("values", []):
                vtype = value.get("type", "").lower()
                vname = value.get("name", "").lower()
                if vtype == "sfx":
                    for key, t in DIE_SFX_MAP.items():
                        if key in vname:
                            return t
                    return "zip"
                if vtype == "installer":
                    for key, t in DIE_INSTALLER_MAP.items():
                        if key in vname:
                            return t
        return "Unknown"
    except json.JSONDecodeError:
        return 'ParseError'
    except subprocess.TimeoutExpired:
        return 'Timeout'
    except Exception as e:
        return f'Error({e})'


def run(folder_path: str):
    if not os.path.exists(CLASSIFY_TOOL_EXE):
        print(f"[ERROR] ClassifyTool.exe not found: {CLASSIFY_TOOL_EXE}")
        sys.exit(1)
    if not os.path.exists(DIEC_EXE):
        print(f"[ERROR] diec.exe not found: {DIEC_EXE}")
        sys.exit(1)

    files = [
        os.path.join(r, f)
        for r, _, fs in os.walk(folder_path)
        for f in fs
        if f.lower().endswith(('.exe', '.msi'))
    ]

    if not files:
        print("대상 파일 없음.")
        return

    total = len(files)
    match = 0
    mismatches = []

    for i, fp in enumerate(files, 1):
        old = classify_old(fp)
        new = classify_new(fp)
        is_match = old == new
        if is_match:
            match += 1
        else:
            mismatches.append((os.path.basename(fp), old, new))
        print(f"[{i:3}/{total}] {'OK' if is_match else 'NG'} | {os.path.basename(fp)}")
        print(f"       old={old} | new={new}")

    parity = match / total * 100
    print("\n" + "=" * 60)
    print(f"총 파일: {total}")
    print(f"일치:   {match}  ({parity:.1f}%)")
    print(f"불일치: {total - match}")

    if mismatches:
        print("\n[불일치 목록]")
        print(f"{'파일명':<40} {'old':<30} {'new'}")
        print("-" * 90)
        for fname, old, new in mismatches:
            print(f"{fname:<40} {old:<30} {new}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/verify_diec_parity.py <installer_folder>")
        sys.exit(1)
    run(sys.argv[1])
