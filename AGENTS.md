# AGENTS

## 프로젝트 개요.

설치파일 설치 자동화 프로그램 -> 설치완료된 포로그램 파일 및 데이터 확보.

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

**결정: DIE (`diec.exe`) subprocess 방식 도입 — Phase 3 ✅ 완료**
- `diec --json <file>` — JSON 출력 파싱으로 교체 (기존 subprocess 패턴 유지)
- 설치 경로: `C:\Program Files\DIE\diec.exe` (환경변수 기반)
- `DIE_INSTALLER_MAP` / `DIE_SFX_MAP` 으로 DIE 출력 → INSTALLER_TYPE_LIST 매핑
- 기존 `Classify-Tool/data.txt` (491건)으로 파리티 검증 권장

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
| `silent_mode.py` terminate/communicate 순서 역전 | `silent_mode.py:84` — communicate 전 terminate 호출로 silent install 항상 실패 | ✅ 수정 완료 |
| `excluded_paths` 하드코딩 | `main.py:73` — config.py 상수 미활용 | ✅ `DIEC_EXE`/`SEVEN_ZIP_EXE` 기반으로 수정 |
| `zip` 타입 잘못된 라우팅 | `main.py` — zip 압축해제 실패 후 silent/GUI 시도 (무의미) | ✅ zip 타입은 압축해제 실패 시 바로 skip |
| `move_file` 비원자적 동작 | `filesystem_monitor.py` — `shutil.copy` + `os.remove` 조합 | ✅ `shutil.move` 단일 호출로 교체 |
| `click_button` "later" 중복 | `gui_install.py:58` | ✅ 중복 제거 |
| `note_file_txt` 경로 하드코딩 | `utils.py` — 상대 경로 `log_files.txt` | ✅ `LOG_FILE` (`C:\Data\log_files.txt`) 사용 |
| `ClassifyTool.exe` 의존성 | `utils.py`, `config.py` | ✅ Phase 3으로 `diec.exe` 교체 |
| `README.md` 내부 노트 공개 | 작업 메모·실험 결과가 공개 레포에 노출 | ✅ 공개용으로 재작성 |

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

## 구현 이력

완료된 구현 단계. 미완료 Phase (4.8~9) 로드맵은 [project_plan.md](../project_plan.md) 섹션 4 참조.

| Phase | 내용 | 위험도 | 상태 |
|-------|------|--------|------|
| 1 | 코드 정리 (config.py, import 정리, 오타 수정) | 낮음 | ✅ 완료 |
| 2 | 로직 버그 수정 + 구버전 파일 삭제 | 중간 | ✅ 완료 |
| 3 | ClassifyTool.exe → DIE(`diec.exe`) 교체 | 높음 | ✅ 완료 |
| 3.5 | 추가 버그 수정 (silent_mode, excluded_paths, zip 라우팅, shutil.move 등) | 중간 | ✅ 완료 |
| 4 | 설치 안정성 개선 (Phase 4 상세 참조) | 높음 | ✅ 완료 |
| 4.5 | 코드 품질 — logging 모듈 도입, 미사용 상수 제거, 데드코드 정리 | 낮음 | ✅ 완료 |
| 4.6 | 리포트 — install_summary.csv 기본 리포트 추가 | 낮음 | ✅ 완료 |
| 4.7 | 즉시·단기 버그 수정 (Phase 4.7 상세 참조) | 낮음 | ✅ 완료 |

---

## Phase 4 상세 — 설치 안정성 개선 ✅ 완료

Phase 1~3.5에서 구조 정리와 DIE 교체는 완료되었지만, 실제 대량 설치 실행에서는 아래 문제가 우선적으로 남아 있다.

### 4.1 파일시스템 모니터링 — move 금지, copy + manifest로 변경 ✅ 완료

- 원본 파일은 이동하지 않고 `C:\Data\collected\<installer_name>\...` 아래로 복사.
- manifest에 원본 경로, 복사 경로, 타입, 상태, 오류, 시각 기록.
- **추가**: worker 스레드로 큐를 실시간 드레인 → 설치 중에도 파일이 즉시 복사됨.

### 4.2 silent mode — MSI는 `msiexec.exe`로 분리 ✅ 완료

- `msiexec.exe /i <file> /qn /norestart` 사용.
- 반환코드 `3010`(재부팅 필요)도 성공으로 처리.

### 4.3 cleanup — 파일명 키워드 종료 최소화 ✅ 완료

- `terminate_installation_process(pid, file_path)` — PID가 있으면 PID 기반, 없을 때만 키워드 fallback.

### 4.4 GUI 성공 판정 — 강제 종료 성공을 설치 성공으로 보지 않음 ✅ 완료

- `clicked_completion AND process_exited` 두 조건 모두 충족 시에만 성공.
- 강제 종료는 cleanup 전용.
- DANGER_KEYWORDS("uninstall", "remove", "restart now" 등) 버튼은 클릭 건너뜀.
- `check_checkbox`: 상태 확인 후 unchecked일 때만 클릭.
- `step` 변수 섀도잉 버그 수정 (`for i in range(step)`).
- 중복 창 핸들 기반으로 제거.

### 4.5 경로 처리 — 실행 위치 독립화 ✅ 완료 (Phase 3.5)

- `Path(__file__).resolve()` 기반 `PROJECT_ROOT`, `PACKAGE_DIR`.
- `excluded_paths`는 `DIEC_EXE`, `SEVEN_ZIP_EXE`, `DATA_FOLDER`, `PACKAGE_DIR` 기반.

---

## Phase 4.7 — 즉시·단기 버그 수정 ✅ 완료

| 문제 | 위치 | 수정 내용 |
|------|------|-----------|
| `_drain_queue` 레이스 컨디션 — stop_event 설정 후 큐 잔여 이벤트 유실 | `filesystem_monitor.py` | `while True` + Empty 시 stop_event 확인으로 교체. 큐가 완전히 비워진 후에만 worker 종료 |
| `[zip_failed]` 오기록 — 추출 미시도 타입도 실패로 기록 | `main.py` | `EXTRACTABLE_TYPES` 확인 후 실제 시도한 경우에만 `note_file_txt` 호출 |
| `.exe`/`.msi` 외 파일에 `diec.exe` 호출 낭비 | `main.py` | `PROCESSABLE_EXTENSIONS` 사전 필터로 비-PE 파일 즉시 skip |
| Resume 기능 없음 — 중단 시 처음부터 재시작 | `main.py` | `load_completed_files()` — 이전 CSV의 success 파일은 건너뜀 |
| CSV 리포트에 실행 구분자 없음 | `main.py` | `run_id` (YYYYMMDD_HHMMSS) 필드 추가 |
| `close_windows()` DANGER 버튼 미필터 | `utils.py` | `DANGER_KEYWORDS` 필터 적용 |
| `DANGER_KEYWORDS` 중복 정의 | `gui_install.py` | `config.py`로 이동, gui_install에서 import |
| `terminate_installation_process` 미사용 데드코드 | `utils.py` | 제거 |
| `click_button` `"continue"` 중복 | `gui_install.py` | 중복 제거 |
| `EXTRACTABLE_TYPES`, `PROCESSABLE_EXTENSIONS`, `DANGER_KEYWORDS` 파일 내 중복 정의 | 여러 파일 | `config.py`로 통합 |

---

## Phase 4.8 상세 — GUI 설치 단계 개선 ⏳ 예정

> 문제점 분류(Category A~D) 및 배경은 [project_plan.md](../project_plan.md) 섹션 3-1 참조.

### Category A — RadioButton 처리 실패

**근본 원인**

현재 `check_radiobutton()`은 "agree" 키워드 일치 시 즉시 클릭 후 `return`한다.
License Agreement 페이지에는 항상 두 버튼이 공존한다:

```
○ I agree to the terms        ← 클릭해야 함
○ I do not agree to the terms ← 절대 클릭하면 안 됨
```

탐색 순서에 따라 "I do not agree"가 먼저 나오면 아무것도 클릭 안 하고 종료된다.
Setup Factory 케이스에서는 agree → disagree 이중 클릭이 발생하기도 했다:
> "radiobutton도 for 문으로 돌아서 agree 하고 다시 disagree버튼을 눌러버림" (except.md)

**해결 — DISAGREE_KEYWORDS 추가**

```python
# config.py에 추가
DISAGREE_KEYWORDS_RADIO = [
    "do not agree", "disagree", "decline", "not accept",
    "동의하지 않", "동의 안 함", "거부",
    "ablehnen", "nicht akzeptieren", "stimme nicht zu",
]

# gui_install.py check_radiobutton() 개선
def check_radiobutton(window):
    agree_candidate = None  # 즉시 클릭하지 않고 저장
    try:
        for radiobutton in window.descendants(control_type="RadioButton"):
            text = radiobutton.window_text().lower()
            logger.debug("RadioButton: %s", text)

            if any(k in text for k in DISAGREE_KEYWORDS_RADIO):
                logger.info("Skipping disagree radiobutton: %s", text)
                continue

            if any(k in text for k in AGREE_KEYWORDS):
                agree_candidate = radiobutton  # 마지막 agree 후보 저장

        if agree_candidate:
            agree_candidate.click()
            logger.info("Clicked agree radiobutton: %s", agree_candidate.window_text())

    except Exception as e:
        logger.warning("RadioButton handling error: %s", e)
```

"agree 후보를 저장 후 한 번만 클릭"으로 이중 클릭 버그도 동시에 방지한다.

---

### Category B — UI 구성요소 접근 불가

**근본 원인 3가지**

```
원인 1: 구형 Win32 Controls
  NSIS < 3.x, 구형 InstallShield, Vobsub, starcodec
  → UIA가 접근하는 COM 인터페이스가 구현되지 않음
  → Win32 메시지(WM_CLICK, BM_CLICK) 기반 접근 필요

원인 2: Custom-drawn Controls
  COMODO, DWG FastView, Magic Pic2Ani
  → 표준 컨트롤이 아니므로 UIA/Win32 모두 인식 못 함
  → 화면 좌표 기반 접근이 유일한 수단

원인 3: 권한 레벨 불일치
  UAC 이후 elevated 프로세스의 창
  → 관리자 권한 실행으로 해결 (is_admin() 체크 이미 적용됨)
```

**해결 1 — Win32 백엔드 fallback**

pywinauto의 `win32` 백엔드는 UIA 대신 Win32 메시지를 직접 전송한다.
UIA가 실패하는 구형 컨트롤에서 효과적이다.

```python
# gui_install.py 구조 변경
def gui_install(file_path, step=20):
    # 1차 시도: UIA 백엔드 (현행)
    result = _try_gui_install(file_path, backend="uia", step=step)
    if result:
        return True

    logger.info("UIA failed, retrying with Win32 backend: %s", file_path)

    # 2차 시도: Win32 백엔드
    return _try_gui_install(file_path, backend="win32", step=step)
```

Win32 백엔드에서 달라지는 API:
- `window.descendants(control_type="Button")` → `window.children(class_name="Button")`
- `button.click_input()` → `button.click()` (메시지 기반)

**해결 2 — 키보드 네비게이션 fallback**

UI 요소는 잡히는데 마우스 클릭이 안 되는 경우(Vobsub 등), 키보드로 우회한다.

```python
import pyautogui

def try_keyboard_navigation(window):
    try:
        window.set_focus()
        for _ in range(5):      # Tab으로 포커스 이동
            pyautogui.press('tab')
            time.sleep(0.1)
        pyautogui.press('enter') # 포커스 컨트롤 활성화
        logger.info("Keyboard navigation attempted")
    except Exception as e:
        logger.warning("Keyboard navigation failed: %s", e)
```

**해결 3 — OCR fallback (마지막 수단)**

COMODO, DWG FastView처럼 UIA/Win32 모두 실패하는 custom UI는 화면 좌표 기반으로 접근한다.

```python
# pip install pyautogui pytesseract pillow
import pyautogui, pytesseract

BUTTON_KEYWORDS_OCR = ["ok", "next", "install", "finish", "yes", "다음", "설치", "확인", "마침"]

def ocr_click_button() -> bool:
    screenshot = pyautogui.screenshot()
    data = pytesseract.image_to_data(
        screenshot, lang="kor+eng", output_type=pytesseract.Output.DICT
    )
    for i, word in enumerate(data['text']):
        if not word.strip():
            continue
        if any(k in word.lower() for k in BUTTON_KEYWORDS_OCR):
            conf = int(data['conf'][i])
            if conf > 60:  # 신뢰도 임계값
                x = data['left'][i] + data['width'][i] // 2
                y = data['top'][i] + data['height'][i] // 2
                pyautogui.click(x, y)
                logger.info("OCR clicked: '%s' at (%d, %d)", word, x, y)
                return True
    return False
```

OCR 한계: 해상도 의존(1920×1080 기준), 한국어 인식률 상대적으로 낮음, disabled 버튼 구분 불가.
UIA/Win32 모두 실패한 케이스의 마지막 수단으로만 사용한다.

---

### Category C — 윈도우 자체를 못 잡음

**근본 원인**

현재 `get_install_windows()`는 창 제목에 "setup", "install" 등 키워드가 있는 창만 가져온다.
실패하는 경우:

```
케이스 1: 자식 프로세스가 창을 생성
  app.windows() → 부모 프로세스 창만 반환, 자식 창 누락

케이스 2: 창 제목이 제품명만인 경우
  "Sibelius 7", "Cool Edit Pro 2.1" — install 키워드 없음

케이스 3: Language Selection 팝업
  설치 시작 전 나오는 첫 번째 다이얼로그 (키워드 없음)
```

**해결 — 프로세스 트리 기반 창 탐색**

창 제목 키워드 대신 PID를 기준으로 모든 창을 찾는다.
(`pywin32` 패키지 필요: `pip install pywin32`)

```python
import win32gui
import win32process

def get_all_windows_for_process_tree(root_pid: int) -> list:
    """설치파일 프로세스 트리에 속한 모든 창을 반환한다."""
    try:
        proc = psutil.Process(root_pid)
        pid_set = {root_pid} | {c.pid for c in proc.children(recursive=True)}
    except psutil.NoSuchProcess:
        return []

    result = []

    def _enum_callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid in pid_set:
            try:
                app_ref = Application(backend="uia")
                ctrl = app_ref.window(handle=hwnd)
                result.append(ctrl)
            except Exception:
                pass

    win32gui.EnumWindows(_enum_callback, None)
    return result
```

창 제목과 무관하게 설치파일이 만든 모든 창을 캡처한다.
기존 `get_install_windows()` 키워드 탐색과 병합해서 사용한다.

---

### Category D — 설치 후 프로그램 자동 실행

**근본 원인**

```python
process_exited = not psutil.pid_exists(pid)
if clicked_completion and process_exited:
    return True
```

설치 완료 후 프로그램이 자동 실행되면:
- 설치파일 프로세스(`pid`)는 종료 → `process_exited=True`
- 하지만 새 프로세스가 남아 다음 설치 환경을 오염
- 일부 케이스는 설치파일이 업데이터를 자식으로 스폰 후 종료 → 자식이 계속 실행 중

**해결 — 설치 전 PID 스냅샷 + 설치 후 신규 프로세스 종료**

```python
def gui_install(file_path, step=20):
    # 설치 시작 전 실행 중인 모든 PID 기록
    before_pids = set(psutil.pids())

    app = Application(backend="uia").start(file_path)
    pid = app.process

    # ... 설치 루프 ...

    # 설치 완료 후: 새로 생긴 프로세스를 종료
    after_pids = set(psutil.pids())
    new_pids = after_pids - before_pids - {pid}
    for new_pid in new_pids:
        try:
            p = psutil.Process(new_pid)
            logger.info("Terminating post-install process: %s (pid=%d)", p.name(), new_pid)
            terminate_process_tree(new_pid)
        except psutil.NoSuchProcess:
            pass
```

---

### 고정 루프 → 이벤트 기반 대기

현재 구조의 근본 한계:

```
현재: step × sleep(3) = 최소 60초 고정
  → 화면 전환이 2초 만에 끝나도 3초 대기
  → 설치가 10초 걸리면 다음 스텝에서 뒤늦게 처리
```

CPU 안정화 대기로 교체하면 설치 속도에 동적으로 적응한다 (개선 2, 이미 설계됨).
추가로 창 제목 변경을 감지해 화면 전환 시점을 정확히 포착할 수 있다:

```python
def wait_for_window_change(pid: int, current_titles: set, timeout=15) -> bool:
    """창 제목이 바뀔 때까지 대기한다."""
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(0.5)
        try:
            new_titles = {w.window_text() for w in get_all_windows_for_process_tree(pid)}
            if new_titles != current_titles:
                return True
        except Exception:
            pass
    return False
```

---

### 개선 후 아키텍처

```
[현재]
gui_install()
  └── for step in range(20):              ← 고정 60초
        sleep(3)
        app.windows() + 키워드 필터       ← 제목 기반, 자식 누락
        click_button()                    ← UIA만
        check_radiobutton()               ← agree 탐색만
        check_checkbox()                  ← 첫 번째만
        wait_for_progress(timeout=30)     ← 고정

[개선 후]
gui_install()
  ├── before_pids = snapshot()            ← 신규 프로세스 추적
  ├── 1차: UIA 백엔드
  │     └── _install_loop()
  │           ├── get_all_windows_for_process_tree()   ← PID 기반
  │           ├── wait_for_cpu_idle() or wait_for_window_change()
  │           ├── click_button()
  │           ├── check_radiobutton()     ← DISAGREE_KEYWORDS 추가
  │           ├── check_checkbox()        ← 전체 순회
  │           └── wait_for_progress()
  ├── [실패 시] 2차: Win32 백엔드         ← 구형 컨트롤 대응
  ├── [실패 시] 3차: OCR fallback         ← custom UI 대응
  └── 완료 후: 신규 프로세스 종료         ← 설치 후 실행 프로그램 정리
```

---

### 우선순위별 구현 계획

| 우선순위 | 항목 | 예상 효과 | 구현 난이도 | 필요 패키지 |
|---------|------|----------|------------|------------|
| 1 | RadioButton DISAGREE_KEYWORDS 추가 | 높음 (가장 빈번한 실패) | 낮음 | 없음 |
| 2 | 설치 전후 PID 스냅샷 + 신규 프로세스 종료 | 높음 (오탐 제거) | 낮음 | 없음 (psutil 기존 사용) |
| 3 | `check_checkbox` 전체 순회로 수정 (`break` 위치 조정) | 중간 | 낮음 | 없음 |
| 4 | Win32 백엔드 fallback | 높음 (구형 컨트롤 대응) | 중간 | 없음 (pywinauto 기존 사용) |
| 5 | PID 트리 기반 창 탐색 | 중간 (자식 프로세스 캡처) | 중간 | `pywin32` |
| 6 | CPU-idle 기반 적응형 대기 | 중간 (속도 개선) | 중간 | 없음 (psutil 기존 사용) |
| 7 | OCR fallback | 낮음 (마지막 수단) | 높음 | `pyautogui`, `pytesseract` |

우선순위 1~3은 코드 수정만으로 즉시 적용 가능하며, except.md에 반복 기록된 케이스의 과반을 해결할 것으로 예상한다.

---

## backup/ 검토 결과 — Phase 5 반영 대상

`backup/` 및 `backup/Tool/`에는 과거 실험 문서, 로그, 비교 CSV, 임시 스크립트가 남아 있다. 대부분은 현 코드에 직접 병합하기보다 **검증 기준과 리포트 기능**으로 재구성하는 것이 맞다.

### 확인된 과거 업무 이력

| 항목 | 근거 파일 | 현재 반영 방향 |
|------|-----------|----------------|
| NSIS 압축해제 실험 | `backup/NSIS-ZIP-Test.md`, `backup/Tool/extract-archive.py`, `backup/Tool/NSIS-compare-zip1.csv` | 압축해제 성공 여부만 보지 않고 SHA-256/PE 매칭률로 품질 검증 |
| 7z installer 압축해제 한계 | `backup/Tool/7z-installer-compare-zip.csv` | 7z 추출 성공 후에도 설치 결과와 불일치할 수 있음을 리포트 |
| CAPE 단독 수집 한계 | `backup/summary.md`, `backup/Tool/README.md` | CAPE는 보조 비교 기준으로만 사용, 주 수집은 VM 내 copy+manifest |
| SHA-256 비교 로직 | `backup/Tool/compare-folder.py`, `backup/Tool/hashcheck.py` | `tools/compare_collected_files.py` 형태로 재작성 |
| 설치 타입별 silent 성공률 | `backup/summary.md`, `backup/Tool/test.md` | installer type별 성공률/실패 사유 리포트 추가 |
| GUI 자동화 케이스 기록 | `backup/summary.md`의 test-sample case | 버튼/체크박스/라디오/프로그레스 처리 정책 문서화 및 테스트 케이스화 |
| CAPE API 초안 | `backup/Tool/cape-api.py`, `backup/Tool/folder-copy.py` | 즉시 제품 코드화하지 않고 optional integration 후보로 유지 |

### 주요 결론

1. **압축해제 성공 = 설치 산출물 확보 성공이 아님**
   - NSIS는 일부 샘플에서 높은 매칭률을 보였지만, 다운로드러/번들러/중첩 설치파일 케이스는 압축해제 산출물과 실제 설치 산출물이 크게 다르다.
   - `verify_folder()`의 “인스톨러 파일 2개 이상이면 의심” 로직은 계속 유지하되, 최종 판단은 파일 hash/PE 매칭률로 보강한다.

2. **CAPE만으로는 목표 산출물 확보가 부족함**
   - 과거 NSIS 실험에서 CAPE 결과만으로는 설치 파일 확보율이 낮았다.
   - CAPE는 자동 설치 대체재가 아니라 비교/보조 수집 경로로 둔다.

3. **installer type별 전략이 달라야 함**
   - Inno Setup/Wise는 silent 성공률이 상대적으로 높았다.
   - InstallShield/Setup Factory/BitRock/QT 등은 silent 실패와 GUI fallback 가능성을 전제로 해야 한다.
   - MSI는 `msiexec` 분리가 필수이며, embedded MSI/추가 MSI 팝업 케이스를 별도 기록해야 한다.

4. **GUI 자동화는 버튼명 리스트만으로 부족함**
   - 과거 케이스에 checkbox, radiobutton, scroll, progressbar, 실행 체크박스 해제 등이 반복적으로 등장한다.
   - `click list`와 함께 `dontclick list`, 완료 버튼, 실행 옵션 checkbox 해제 정책을 분리해야 한다.

Phase 5/6 세부 계획은 [project_plan.md](../project_plan.md) 섹션 4 중기 참조.

---

## Phase 3 상세 — ClassifyTool.exe → DIE(`diec.exe`) ✅ 완료

### 교체 내용

`diec.exe --json <file>` subprocess 방식 채택 (기존 패턴 유지, Python 추가 의존성 없음).

`config.py` 변경:
- `CLASSIFY_TOOL_EXE` 제거
- `DIEC_EXE` 추가 (`C:\Program Files\DIE\diec.exe`)
- `DIE_INSTALLER_MAP` / `DIE_SFX_MAP` 추가 (DIE 출력 → INSTALLER_TYPE_LIST 매핑)
- `LOG_FILE` 추가 (`C:\Data\log_files.txt`)

`utils.py` `classify_installer()` 교체:

```python
# DIE JSON 출력 파싱
result = subprocess.run([DIEC_EXE, "--json", file_path], capture_output=True, timeout=60)
data = json.loads(result.stdout)

for detect in data.get("detects", []):
    filetype = detect.get("filetype", "").lower()
    if filetype in {"cab", "archive"}:
        return "zip"
    for value in detect.get("values", []):
        if value["type"].lower() == "sfx":
            # 7-Zip SFX → "7z installer", 그 외 → "zip"
        if value["type"].lower() == "installer":
            # DIE_INSTALLER_MAP으로 name 매핑
```

### 검증 권장

- `Classify-Tool/data.txt` (491건) 분류 결과와 비교하여 100% 파리티 목표
- 검증 완료 후 로컬 `Classify-Tool/` 디렉토리 삭제 가능

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
