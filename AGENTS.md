# AGENTS

## 요구사항

- 파일 타입 확인 : 자사 툴 -> 상용 오픈소스
  > ex) magkia : https://github.com/google/magika
  > 그 외 오픈소스 확인.
- 7-zip 압축해제 : PE 파일 -> 7-zip source code?
- pywinauto -> 좀 더 효율적인 방법이 있는지 검토.
- 코드 및 프로젝트 정리.

---

## 검토 결과

### 1. 파일 타입 확인 — ClassifyTool.exe → 오픈소스 교체

**현황**
- `auto_install/utils.py` — `classify_installer()` 함수가 `ClassifyTool.exe` (자사 독립 실행파일) subprocess 호출
- ClassifyTool.exe는 **DIE(Detect It Easy)** 기반으로 제작된 in-house 래퍼 (README.md 참고)

**후보 비교**

| 도구 | 적합성 | 이유 |
|------|--------|------|
| **Magika (Google)** | ❌ 부적합 | 파일 **내용 타입**(JPEG/PDF/Python 등)을 감지하는 도구. NSIS·Inno Setup·Wise Installer를 전부 `pebin`으로 반환 — 설치 프레임워크 구분 불가 |
| **python-magic** | △ 부분적 | NSIS/7z SFX 일부 인식하지만 Inno Setup, InstallShield 등 대부분 놓침 |
| **pefile** | △ 구현 비용 큼 | PE 헤더 파싱 가능하지만 16종 시그니처 직접 구현 필요 |
| **DIE (`diePython`)** | ✅ 최적 | ClassifyTool.exe의 upstream 프로젝트. 동일 시그니처 DB. `pip install diePython`으로 사용 가능. Windows/Linux/macOS 지원 |

> **Magika 불가 이유**: silent 설치 플래그가 프레임워크별로 다름 (`/S`, `/VERYSILENT`, `/qn` 등). Magika는 NSIS와 Inno Setup을 구분하지 못하므로 올바른 플래그 선택 불가.

**결정: DIE (`diePython`) 도입 — Phase 3 예정**
- `pip install diePython` — 외부 exe 없이 Python 코드에서 직접 호출
- 시그니처 파일은 JavaScript `.sg` 형태의 오픈소스
- 기존 `Classify-Tool/data.txt` (491건)으로 파리티 검증

---

### 2. 7-zip 압축해제 — subprocess 유지

**현황**
- `auto_install/extract_zip.py` — `7z.exe x <file> -o<path> -y` subprocess 호출

**후보 비교**

| 방법 | 적합성 | 이유 |
|------|--------|------|
| **py7zr** | ❌ 부적합 | `.7z` 포맷만 지원. NSIS `.exe`, MSI 추출 불가 |
| **libarchive-c** | ❌ 부적합 | NSIS installer 플러그인 없음 |
| **7-zip 소스 직접 통합** | ❌ 과도함 | C++ 빌드 필요, 유지비용 높음 |
| **subprocess to 7z.exe (현행)** | ✅ 유지 | NSIS/MSI 추출은 7z 전용 플러그인 필요. 84.7% 성공률 검증됨 |

**결정: 현행(subprocess) 유지 ✅ 완료**
- NSIS/MSI 추출은 7-zip 내장 플러그인이 필수 — 순수 Python 라이브러리로 대체 불가
- `SEVEN_ZIP_EXE` 경로 중복 → `config.py`로 통합 완료

---

### 3. pywinauto → 대안 검토

**현황**
- `auto_install/gui_install.py` — pywinauto 0.6.8 UIA 백엔드

**후보 비교**

| 도구 | 적합성 | 이유 |
|------|--------|------|
| **pyautogui** | ❌ 부적합 | 좌표 기반 클릭, 창 구조 탐색 불가 |
| **WinAppDriver + Appium** | △ 과도함 | 서버 프로세스 필요, 배치 처리에 오버헤드 큼 |
| **uiautomation** | △ 향후 대안 | 2024년 활발히 유지. COM 에러 처리 더 안정적 |
| **pywinauto (현행)** | ✅ 유지 | 미지의 설치 GUI를 이름으로 탐색하는 고수준 API에 적합 |

**결정: 현행(pywinauto) 유지 + 로직 버그 수정 ✅ 완료**

`gui_install.py` 반환값 로직 역전 버그 수정 완료:
```python
# 수정 전 (버그)
if ret_process:
    return False   # 프로세스 정상 종료됐는데 False 반환
return True        # 프로세스를 못 찾은 경우 True 반환 (반대)

# 수정 후
if ret_process:
    return True    # 정상 종료 = 성공
return False       # 프로세스를 찾지 못함 = 실패
```

향후 안정성 문제 발생 시 `uiautomation` 라이브러리로 교체 검토.

#### pywinauto 실행 환경 요구사항

pywinauto 자체는 Python venv에서 별도 설정 없이 동작하지만, **설치파일 GUI 자동화** 용도에서는 Windows 실행 환경 수준의 3가지 조건이 필수다.

**문제 1: UAC / 권한 — 가장 치명적**

대부분의 설치파일은 실행 시 관리자 권한을 요구한다. UAC 프롬프트는 별도의 **Secure Desktop** 위에서 실행되므로 pywinauto를 포함한 어떤 자동화 도구도 접근 불가능하다.

```
[설치파일 실행] → [UAC 프롬프트 (Secure Desktop)] → pywinauto 접근 불가 → 자동화 중단
```

**해결:**
- Python 스크립트 자체를 관리자 권한으로 실행
- VM 환경에서 UAC 완전 비활성화 (`ConsentPromptBehaviorAdmin=0`)

**문제 2: Interactive Desktop Session 필요**

| 실행 환경 | 동작 |
|-----------|------|
| 물리 PC / VM 콘솔 직접 접속 | ✅ 정상 |
| RDP 연결 (창 열린 상태) | ✅ 정상 |
| RDP 창 최소화 / 연결 해제 | ❌ 실패 (`SetCursorPos` 오류) |
| Windows 서비스로 실행 | ❌ 완전 불가 |
| SSH 원격 실행 | ❌ 완전 불가 |
| Task Scheduler (비인터랙티브) | ❌ 불가 |

RDP 환경에서 자동화 실행 시 **VNC 사용 권장** — 클라이언트 연결 해제 후에도 데스크톱 세션 유지됨.

**문제 3: 권한 레벨 불일치**

pywinauto는 자신과 동일하거나 낮은 권한의 프로세스만 제어 가능하다. 설치파일이 UAC 후 관리자 권한으로 올라가면 일반 유저 권한의 pywinauto에서 `window.descendants()` 등이 실패한다.

**권장 실행 환경:**

| 방식 | UAC 제어 | 격리 | 비용 | 권장 용도 |
|------|----------|------|------|-----------|
| VMware | ✅ | ✅ | 유료 | — |
| **Hyper-V + 스냅샷** | **✅** | **✅** | **무료 (내장)** | **대량 배치 처리 (권장)** |
| Windows Sandbox | ✅ | ✅ | 무료 (내장) | 개발/테스트 |
| 전용 Windows 머신 | ✅ | ❌ | — | 소규모 실행 |

**권장: Hyper-V + 스냅샷** — Windows 10/11 Pro에 기본 내장, PowerShell로 스냅샷 복원 자동화 가능:

```powershell
# 배치 실행 전 clean state 복원
Restore-VMCheckpoint -VMName "AutoInstall" -Name "Clean-State"
Start-VM -Name "AutoInstall"

# 완료 후 다시 초기화
Stop-VM -Name "AutoInstall" -Force
Restore-VMCheckpoint -VMName "AutoInstall" -Name "Clean-State"
```

```
[Hyper-V VM]
  ├── Windows 10/11
  ├── UAC 비활성화 (ConsentPromptBehaviorAdmin=0)
  ├── VM 콘솔 직접 접속 상태 유지 (또는 VNC)
  └── 관리자 권한으로 Python 실행:
       cmd.exe → 관리자 권한으로 실행 → python main.py <path>
```

**관리자 권한 체크 — `main.py` 적용 완료 ✅**
```python
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

# main() 진입 시 경고 출력
if not is_admin():
    print("경고: 관리자 권한으로 실행하지 않으면 UAC 팝업 처리가 불가능합니다.")
```

| 조건 | 현재 코드 | 필요 조치 |
|------|-----------|-----------|
| Python venv | ✅ 문제없음 | — |
| 관리자 권한 실행 | ✅ 체크 추가됨 | 수동으로 관리자 권한 실행 |
| UAC 비활성화 (VM) | ❌ 코드 없음 | VM 레지스트리 설정 |
| Interactive Session | ❌ 확인 없음 | VM 콘솔/VNC 환경 필수 |
| Secure Desktop UAC 팝업 | ❌ 처리 불가 | UAC 비활성화로만 우회 가능 |

#### pywinauto 코드 개선 방향

**개선 1: `uiautomation` fallback 추가 — 향후 적용 예정**

pywinauto가 COM 오류로 실패할 경우 `uiautomation`(yinkaisheng)으로 재시도:

```
현재: pywinauto → 실패 → 끝
개선: pywinauto → COM 오류 시 uiautomation fallback → 실패 → Response File 시도 → 끝
```

```python
# pip install uiautomation
import uiautomation as auto

def gui_install_uia_fallback(file_path):
    button_keywords = ["next", "install", "finish", "ok", "다음", "설치", "마침"]
    for _ in range(30):
        for ctrl in auto.GetRootControl().GetChildren():
            for btn in ctrl.GetChildren():
                if btn.ControlTypeName == "ButtonControl":
                    if any(k in btn.Name.lower() for k in button_keywords):
                        btn.Click()
        time.sleep(2)
```

**개선 2: `time.sleep()` → CPU 이벤트 기반 대기 — 향후 적용 예정**

현재 코드는 고정 sleep으로 다음 화면 전환을 감지한다. 설치 속도에 따라 너무 짧거나 너무 길어 신뢰성이 낮다.

```python
# 현재 (취약)
time.sleep(5)
if check_installation_window(): ...

# 개선 — 프로세스 CPU 안정화 감지
def wait_for_installer_idle(proc, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            if proc.cpu_percent(interval=1) < 2.0:
                return True
        except psutil.NoSuchProcess:
            return True
    return False
```

**개선 3: Response File — GUI 자동화 자체를 우회 — 향후 적용 예정**

Inno Setup / InstallShield는 응답 파일 기록·재생을 지원한다. GUI 없이 완전 무인 설치 가능:

```python
# Inno Setup — /SAVEINF로 응답 파일 생성 후 /LOADINF로 재사용
subprocess.run([file_path, "/SAVEINF=response.inf", "/VERYSILENT"])
subprocess.run([file_path, "/LOADINF=response.inf", "/VERYSILENT"])

# InstallShield — -r로 기록, -s로 재생
subprocess.run([file_path, "-r", "-f1response.iss"])
subprocess.run([file_path, "-s", "-f1response.iss"])
```

적용 대상: `silent_mode.py`의 `run_silent_install()` 확장 시 Inno Setup / InstallShield 항목에 추가.

---

### 4. 코드 및 프로젝트 정리

**발견된 문제 및 처리 현황**

| 문제 | 위치 | 상태 |
|------|------|------|
| 상수 분산 (`SEVEN_ZIP_EXE`, `CLASSIFY_TOOL_EXE` 등) | `extract_zip.py`, `utils.py`, `main.py` | ✅ `config.py`로 통합 |
| Star import (`from utils import *`) | `main.py`, `extract_zip.py`, `silent_mode.py`, `gui_install.py`, `filesystem_monitor.py` | ✅ 명시적 import로 교체 |
| 중복 `import time` | `main.py`, `utils.py`, `silent_mode.py` | ✅ 제거 완료 |
| Dead code | `utils.py` 주석 처리된 파싱 로직 | ✅ 제거 완료 |
| 구버전 파일 | `auto_install/main1016.py`, `auto_install/filesystem_monitor1016.py` | ✅ 삭제 완료 |
| filesystem_monitor Queue 패턴 미적용 | `filesystem_monitor.py` | ✅ Queue 패턴 병합 완료 |
| `gui_install` 반환값 버그 | `gui_install.py` | ✅ 수정 완료 |
| 관리자 권한 체크 없음 | `main.py` | ✅ `is_admin()` 추가 |
| 오타 | `requriements.txt` → `requirements.txt` | ✅ 수정 완료 |
| `requirements.txt` 위치 | `auto_install/requirements.txt` (하위) | ✅ 프로젝트 루트로 이동 |
| `auto_install/__init__.py` 없음 | — | ✅ 패키지 마커 추가 |
| 독점 실행파일 git 추적 | `Classify-Tool/` 8개 파일 | ✅ git rm --cached 완료 |
| 상용 설치파일 git 추적 | `test-sample/` 12개 파일 | ✅ git rm --cached 완료 |
| 내부 노트·로그 git 추적 | `auto_install/` 내 `.md`, `.txt`, `.ipynb`, 구버전 | ✅ git rm --cached 완료 |
| `close_windows` clicks 리스트 콤마 누락 | `utils.py` — `"close"` 뒤 `,` 없음 → 문자열 연결 버그 | ✅ 수정 완료 |
| `check_radiobutton` 콤마 누락 + 로직 버그 | `gui_install.py` — `"확인"` 뒤 `,` 없음, 항상 첫 번째 버튼 클릭 | ✅ 수정 완료 |
| `classify_installer()` 중복 | `utils.py`, `Tool/` 스크립트들 | ⏳ Phase 4 예정 |

**Python 문자열 연결 버그 설명 (수정 완료)**

Python은 리스트 내 인접한 문자열 리터럴을 자동으로 이어붙인다:

```python
# 버그 — 콤마 없음
clicks = ["close"   # ← 콤마 없음
          "취소"]   # "close취소"로 연결됨 → "close" 버튼을 절대 클릭 못함

# 수정
clicks = ["close",  # ← 콤마 추가
          "취소"]
```

`check_radiobutton` 로직 버그도 함께 수정:

```python
# 버그 — 매칭 여부와 무관하게 항상 첫 번째 라디오버튼 클릭
for radiobutton in ...:
    for radio_button in radiobutton_list:
        if radio_button in radiobutton_text:
            radiobutton.click(); break
    radiobutton.click()  # ← 이 줄이 항상 실행됨
    break

# 수정 — 키워드 매칭 시에만 클릭 후 즉시 반환
for radiobutton in ...:
    for radio_button in radiobutton_list:
        if radio_button in radiobutton_text:
            radiobutton.click()
            return
```

**프로젝트 폴더 구조 (정리 후)**

```
auto-Install/                        # 프로젝트 루트
├── .gitignore
├── AGENTS.md
├── LICENSE
├── README.md
├── requirements.txt                 # ← 루트로 이동 (표준 위치)
└── auto_install/                    # 소스 패키지
    ├── __init__.py                  # ← 패키지 마커 추가
    ├── config.py                    # 신규 — 경로·상수 통합
    ├── main.py                      # 진입점
    ├── utils.py                     # 공통 유틸리티
    ├── extract_zip.py               # 7-zip 압축해제
    ├── silent_mode.py               # 사일런트 설치
    ├── gui_install.py               # GUI 자동화
    └── filesystem_monitor.py        # 파일시스템 모니터링
```

**실행 방법**

```bash
# auto_install/ 디렉토리 안에서 실행
cd auto_install
python main.py <installer_folder_path>

# 또는 프로젝트 루트에서
python auto_install/main.py <installer_folder_path>
```

---

## 구현 순서

| Phase | 내용 | 위험도 | 상태 |
|-------|------|--------|------|
| 1 | 코드 정리 (config.py, import 정리, 오타 수정) | 낮음 | ✅ 완료 |
| 2 | 로직 버그 수정 + 구버전 파일 삭제 | 중간 | ✅ 완료 |
| 3 | ClassifyTool.exe → DIE(`diePython`) 교체 | 높음 | ⏳ 예정 |
| 4 | Tool/ 디렉토리 정리 | 낮음 | ⏳ 예정 |

---

## Phase 3 상세 — ClassifyTool.exe → DIE(`diePython`)

### 교체 방법

```bash
pip install diePython
```

`utils.py`의 `classify_installer()` 교체 대상:

```python
# 현재 — ClassifyTool.exe subprocess
result = subprocess.run([CLASSIFY_TOOL_EXE, file_path], capture_output=True, timeout=60)
output = result.stdout.decode('latin-1').split('->')[-1].strip()

# 교체 후 — diePython 직접 호출
import dielib

def classify_installer(file_path: str) -> str:
    die = dielib.Scanner()
    result = die.scan(file_path)
    # result를 파싱해 INSTALLER_TYPE_LIST 매핑
    ...
```

또는 `diec.exe` subprocess 방식 (기존 패턴 유지):

```python
DIEC_EXE = os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), "DIE", "diec.exe")

result = subprocess.run([DIEC_EXE, "--json", file_path], capture_output=True, timeout=60)
output = json.loads(result.stdout)
```

### 검증

- `Classify-Tool/data.txt` (491건) 분류 결과와 비교하여 100% 파리티 목표
- 교체 완료 후 `Classify-Tool/` 로컬 디렉토리 삭제

---

## 오픈소스 공개 검토

### 라이센스

**MIT License 채택** — 모든 의존성과 호환.

| 의존성 | 라이센스 | 호환 |
|--------|---------|------|
| pywinauto | LGPL-2.1 | ✅ (동적 사용) |
| psutil | BSD-3-Clause | ✅ |
| watchdog | Apache-2.0 | ✅ |
| 7-Zip (외부 호출) | LGPL + unRAR | ✅ (외부 툴, 임베딩 아님) |
| diePython (예정) | MIT | ✅ |

### 공개 전 처리 완료 항목

| 항목 | 조치 |
|------|------|
| `Classify-Tool/` (독점 실행파일, DLL) | git rm --cached 완료 → `.gitignore` 추가 |
| `test-sample/` (타사 상용 소프트웨어) | git rm --cached 완료 (이미 .gitignore에 있었음) |
| 로그/출력 파일 (`log_files*.txt` 등) | git rm --cached 완료 → `.gitignore` 패턴 추가 |
| 내부 분석 데이터 (`Tool/*.csv`, `*.xlsx`) | git rm --cached 완료 → `.gitignore` 추가 |
| 개인정보 (`README.md` 담당자 실명) | 제거 완료 |
| `requriements.txt` 오타 | `requirements.txt`로 git mv 완료 |
| LICENSE 파일 없음 | `LICENSE` (MIT) 추가 완료 |
| `AGENTS.md` git 제외 | `.gitignore`에서 제거 → 추적 가능 상태 |
| Phase 1–2 코드 정리 | `config.py` 신규, star import 제거, 버그 수정, 구버전 파일 삭제 |

### 공개 전 잔여 항목

| 항목 | 조치 |
|------|------|
| `Classify-Tool/` 로컬 파일 삭제 | Phase 3 (diePython 교체) 완료 후 삭제 |
| `git filter-repo`로 이진 파일 히스토리 정리 | 선택적 — 공개 전 필요 시 수행 |
| README.md 공개용 재작성 | 내부 작업 노트 제거, 설치 방법·사용법 추가 |

### 실행 환경 (VM 권장 방식)

| 목적 | 권장 |
|------|------|
| 개발/테스트 | Windows Sandbox (기본 내장, 무료) |
| 소규모 실행 | 전용 Windows 머신 (UAC 비활성화) |
| **대량 배치 처리** | **Hyper-V + 스냅샷** (Windows Pro 내장, 무료) |
| **멀티 플랫폼 호스트** | **VirtualBox 또는 VMware** (macOS/Linux/Windows 모두 지원) |

Hyper-V는 Windows 호스트 전용. macOS/Linux 호스트에서는 VirtualBox(무료) 또는 VMware 사용.
