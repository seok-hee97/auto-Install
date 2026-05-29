# Auto-Install

- 7zip 지원 파일 포맷.
  ```bash
  ZIP 	: SFX
  BZ2 	: Archive
  RAR 	: Archive, SFX
  ARJ 	: Archive, SFX
  Z	    : Archive
  LZH 	: Archive
  7Z  	: Archive, SFX, Installer
  CAB 	: Archive, SFX
  NSIS  :	Archive, Installer
  LZMA  :	Archive
  LZMA86:	Archive
  XZ    : Archive
  PPMD  : Archive
  MSLZ  :	Archive, SFX
  XAR 	: Archive
  MSI   :	Archive, Installer
  AR    :	Archive
  CPIO  :	Archive
  TAR   :	Archive
  GZ    :	Archive, SFX
  ```

## 10 / 2 까지 테스트 결과
테스트 결과 단순히 카운트 ?? X

- idea 1 : Installer type별
- idea 2 : step별(step1 : extract_archvie, step2 : run_silent_mode, step3 : gui_install) 

- `auto_install.py` : main py 파일

- `extrac_seven_zip.py` :  7zip 압축 해제
- `filesystemMointor.py` :  모니터링 함수 기능 추가
- 모니터링 후 파일 이동 및 복사 함수 추가
방법 1 : shutil.move() or shtuil.copy()
> shutil.move() 실행중인 파일이거나 권한으로 이동 불가 가능성 있어 shutil.copy ,copytree 적용
> 복사 후 파일 삭제 등 하는게 나을듯
방법 2 : 생성된 파일 경로 리스트 및 텍스트파일로 받다가 옮기기 

- `gui_install.py` :
- for loop로 step별로 동작하게 해놓았는데
  > 중간에 멈춤 for loop 안에 if continue 추가함
- 예외처리 및 gui 구성요소 조건 추가 필요
- 설치 완료 및 진행 후 인터넷 사이트 or 프로그램 실행
> 인터넷 사이트

설치 성공/실패 여부 확인 로직
> 1.for loop Step 끝나면 설치성공 -> 그전에 에러로 예외처리되면 실패
> 2.설치화면 관련 팝업창이 뜨는지 확인(+FINISH or completed 버튼 누를때 확인)
> 3 프로그램 실행파일 확인 및 레지스트리 확인

gui_install() 함수 개선
> GUI window는 잡혔는데 버튼 및 구성요소가 안잡힌듯 하다.
> 추가적으로 확인 및 테스트 (gui_install.py로 테스트 가능)


- `silent_mode.py` : 설치파일 실행파일 설치 py
silent mode로 실행 후

- `util.py` : 여러가지 함수 모음 py


[feedback0930]
tool.py -> utils.py (rename)
압축해제 // 성공

- step1 : extract_zip
  > 지금 verify_folder 검증 코드 들어가 있음

- step2 : silent_mode
  > verify_folder 기능 추가
  > GUI control for loop(step = 20) -> while Loop & 종료조건 
  > 기능별로 나눠 놓는 것이 좋음
  > close_window() 기능 따로  Threading.thread() 형태로 돌리는 것이 좋음
  > close_window() 하면서 설치 화면 확인!! check!!

- step3 : gui_install
  > verify_folder 기능 추가
  > GUI control for loop(step = 20) -> while Loop & 종료조건 
  





#7zip/silent_install test
total_files :  374
successful_install : 313
-------------------------------
313 / 374

 





### Reference
python         
- [Argparse](https://wikidocs.net/73785)
- [Python-Command-Line Arguments](https://www.tutorialspoint.com/python/python_command_line_arguments.htm)
- [python csv, writing headers only once](https://stackoverflow.com/questions/28325622/python-csv-writing-headers-only-once)
- [Python | os.path.relpath() method](https://www.geeksforgeeks.org/python-os-path-relpath-method/)

pywinauto           
- [pywinauto docs](https://pywinauto.readthedocs.io/en/latest/getting_started.html)
- [pywinauto docs(Waiting for Long Operations)](https://pywinauto.readthedocs.io/en/latest/wait_long_operations.html#application-mㅜethods)
- [pywinauto docs(Methods available to each different control type)](https://pywinauto.readthedocs.io/en/latest/controls_overview.html)
- [(Medium)Automating Windows GUIs with Pywinauto : A Practical Guide](https://naveenrk22.medium.com/automating-windows-guis-with-pywinauto-a-practical-guide-eebd86fdabe6)
- [pywinauto(issue)(waiting for the element availability&Visibility)](https://github.com/pywinauto/pywinauto/issues/936)
- [pywinauto(issue)(Slider bar value() function returns 0.0 in one use case and 50.0 in other use case )](https://github.com/pywinauto/pywinauto/issues/726)
- [pywinauto7-안정적인 자동화](https://skillmemory.tistory.com/entry/pywinauto-7-%EC%95%88%EC%A0%95%EC%A0%81%EC%9D%B8-%EC%9E%90%EB%8F%99%ED%99%94)
- [How to check if Progress Bar is completed in Pywinauto](https://stackoverflow.com/questions/67409844/how-to-check-if-progress-bar-is-completed-in-pywinauto)
  ```python
  app.Form1.child_window(auto_id="ProgressBar1").legacy_properties()['Value'] == "100%"
  ```


7-zip          
- [Using os.system in python to run external programs](https://www.tech-artists.org/t/using-os-system-in-python-to-run-external-programs/3290)
- [7zip Commands from Python](https://stackoverflow.com/questions/11067097/7zip-commands-from-python)
- [7zip Supported formats](https://documentation.help/7-Zip/formats.htm)

watchdog           
- [Python:Event Monitoring with watchdogs](https://pravash-techie.medium.com/python-event-monitoring-with-watchdogs-86125f946da6)
- [(pypi)watchdog](https://pypi.org/project/watchdog/)
- [API Reference(watchdog)](https://python-watchdog.readthedocs.io/en/stable/api.html#module-watchdog.events)
