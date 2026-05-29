# Auto-Install      

1. 샘플 약 500개.      
1.1. 인스톨러 케이스 분류.         
  > Classify-Tool.exe 사용해서 타입 확인. path : ("Program Files (x86)", "Classify-Tool", "ClassifyTool.exe")     
  > Installer type : Inno Setup, NSIS, Wise Installer, 7z installewr, Microsoft Installer(MSI) ...   
  > ETC (installer type 이 없는 파일도 추가적으로 확보 필요).


2. 7z 압축 해제 지원 케이스 확인 및 분류.     
  > 7z Installer, msi, NSIS 인스톨러 타입 압축 해제 자동화.       
  > 7z.exe 실행파일 활용 / path : ("ProgramFiles", "7-Zip", "7z.exe").            
  > NSIS, msi, 7z installer  

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
- NSIS 설치파일 샘플 137개 압축해제 테스트
  ```NSIS 설치파일
  total_files :  137    <- 전체파일
  successful_install : 116 <- 인스톨러가 1개 있는 파일들
  extract failed :  3  <- 압축해제 실패한 파일
  -------------------------------
  116 / 137
  ```

2.1. 7z 압축해제 성공 케이스.   
  - 압축 해제된 파일 사용.   
    > 압축 해제된 파일 확보.

2.2. 압축해제와 수동 설치파일이 일치하지 않는 케이스.
  - 압축해제는 성공했지만 수동 설치파일과 비교했을 때 제대로된 파일들 확보하지 못했다.
  - 압축해제 성공한 폴더(파일)에서 검증 로직을 추가해서 판단해야 한다.
  - IDEA : 압축해제된 폴더에서 인스톨러 파일 개수 카운트 (분류조건 : 2개 이상).
    > Uninstall.exe 인스톨러 파일 존재하기 때문에 분류 조건 2개 이상으로 지정했다.
  - 압축해제된 파일 확보하고 해당 인스톨러에 대해서 사일런스 모드 실행 및 GUI 자동화 실행한다.

2.3. 7z 압축해제 실패 케이스.
  - 압축 해제 실패 시 예외처리. 
    > 예외처리 후 사일런스 모드로 접근



3. 인스톨러 사일런스 모드 지원 옵션 확인 및 분류.        
  > 사일런스 모드 확인 방법 (setup.exe /? or /help)
  ```bash
  "7z installer": ["/S"],
  "Acronis installer[ZIP]": ["/quiet"],
  "Advanced installer": ["/quiet"]  or ["/exenoui"],      
  "BitRock installer": ["--mode", "unattended"],          
  "CreateInstall-Overlay": ["-silent"],
  "Ghost installer": ["/S"],
  "Inno Setup": ["/VERYSILENT", "/SUPPRESSMSGBOXES"],     
  "InstallShield": ["/s", "/v\"/qn\""],                   
  "Microsoft Installer(MSI)": ["/qn"],                    
  "NSIS": ["/S"],                                         
  "QT installer": ["--accept-licenses", "--default-answer", "--confirm-command install"]
  "Setup Factory": ["/S"],
  "Sony Windows installer": ["/q"],
  "Windows Installer": ["/qn"],
  "Wise Installer": ["/s"],
  "WIX Toolset installer" : ["/q"]
  ```

3.1. 인스톨러 사일런스 모드 설치 성공.
  > 설치된 파일 사용.
  Test 결과 (설치 성공 / 전체파일).
  ```
  Acronis installer[ZIP]:   (0 / 1)
  Advanced installer        (1 / 1)
  BitRock installer         (0 / 1)
  CreateInstall-Overlay     (0 / 1)
  Ghost installer           (1 / 1)    
  Inno Setup                (9 / 10)     
  InstallSheild             (1 / 12)
  QT installer              (0 / 1)     
  Setup Factory             (1 / 14)
  Sony Windows installer    (3 / 3)
  Wise Installer            (10 / 11)
  Windows Installer         (1 / 1)
  ```

3.2. 인스톨러 사일런스 모드 설치 실패.
  > case 1 : 사일런스 모드 지원하지 않는 경우.     
  > case 2 : 사일런스 지원하지만 설치 과정 중 에러가 발생하는 경우.      
  > 설치 실패 시 예외처리 CAPE & GUI 접근.
- subprocess timeout 예외처리 3min(timeout = 180) 적용 확인. 




1. 설치 자동화.
  > CAPE 오픈소스에서 설치 자동화 관련 코드 분석.  
  > GUI 구성요소 전부 파악해서 (Button) click  / dontclik 리스트 나눠놓고 계속 실행.
  > + checkbox, radiobutton, progressbar, ... case 확인 후 처리.


4.1. CAPE 설치 자동화 코드 확인.
- CAPE 자동화 코드 업데이트 해서 적용 고려.
  > CAPE 한국어 구성요소 추가 및 코드 확인.
  > `CAPEv2/analyzer/windows/modules/auxiliary/human.py`.
  > 실행파일 사람처럼 설치 및 실행 (button, dontclick 리스트로 나눠놓음).
  > `CAPEv2/analyzer/windows/modules/packages/zip.py`.
  > path : ("ProgramFiles", "7-Zip", "7z.exe") -> 환경변수로 해당 경로 가져와서 7zip 실행.

4.2. 설치 자동화 툴 확인.
> CAPE나 다른 프로그램에서 사용하는 설치 자동화 툴이 있다면 참고.
- 자동화 툴 사용 시 설치 자동화 구현 잘되는지 확인.

4.3. 설치 자동화 직접 구현.
> GUI 구성요소 컨트톨 해서 자동화.
> keyboard, mouse 외부 입력 사용해서 자동화.


5. 설치된 파일 확보.
> 모니터링 후 설치된 파일  생성 시 파일 확보.

5.1. CAPE 사용 시.
> CAPE API를 사용해 파일 업로드 기능 구현.
> 해당경로 `/opt/CAPE/storage/analyses/{analysis_id}/files/`에서 파일 확보.

5.2. 7zip, 인스톨러 사일런스, GUI 자동화 구현 시.
> 모니터링 후 설치된 파일 생성 시 파일 확보.
> `watchdog` 파이썬 라이브러리 확인.








[feedback]
- 케이스 정리 확실히!! -> 예외케이스 사유를 알아야함
- 예외처리를 subprocess 에서 처리가 가능한지 메서드 추가 확인
- 코드에서 케이스 나눌때도 너무 indent 늘어나게 나누면 힘듬
- 예외케이스 고려해서 정리

















# Auto-Install(backup)      

1. 샘플 약 500개.    
1.1. 인스톨러 케이스 분류.       
> Classify-Tool.exe 사용해서 타입 확인. path : ("Program Files (x86)", "Classify-Tool", "ClassifyTool.exe")    
> Installer type : Inno Setup, NSIS, Wise Installer, 7z installewr, Microsoft Installer(MSI) ...  
> ETC (installer type 이 없는 파일도 추가적으로 확보 필요)


2. 7z 압축 해제 지원 케이스 확인 및 분류.    
> 7z Installer, msi, NSIS 인스톨러 타입 압축 해제 자동화      
> 7z.exe 실행파일 활용 / path : ("ProgramFiles", "7-Zip", "7z.exe")        
> NSIS, msi, 7z installer, Acronsis-Installer[ZIP]
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
> ADD : Acronsis-Installer[ZIP] 인스톨러 파일도 zip 로직에 추가해도 되지 않을까?.
> MAGIX Slideshow Maker.exe 수동 설치 파일 확보 실패헤서 압축해제된 파일과 비교하지 못했다.  

2.1. 7z 압축해제 성공 케이스   
- 압축 해제된 파일 사용   
- (TEST)압축 해제 성공 케이스 중 수동 설치 파일 비교   
  > 수동 설치 파일과  비교해서 매칭된 샘플 / 압축해제된 인스톨러 샘플
  - NSIS (13 / 15)
  - msi ( / 4)
    > 비교 X -> (수동설치 실패)(팝업창)지원되지 않는 16비트 응용 프로그램
  - 7z Installer ( 2 / 5)
    > 수동 설치된 파일과 비교했을 때 2개 일치

2.2. 압축해제 != 수동 설치파일 케이스
  > 검증 기능이 필요
  - NSIS
    - CyberLink_PowerDirector_Downloader.exe | MD5 : eb44b7041d596e4f28036f4ad5719b4f
      > PostBuild.exe, TaskScheduler.exe        

    - Divx Player.exe | MD5 : e1ebaddd9bc93758793658365c06516f
      > Setup.exe / 세부 package ( installer.exe (NSIS))로 구성      
  - msi

  - 7z Installer
    - Comodo Firewall.exe | MD5 : a0163415ae817de66abccaefd56f672d
      > cmdinstall.exe, dragonsetup.exe (NSIS)
    - DWG FastView.exe | MD5 : f3719bdf0c666e219da75be00780ff11
      > Setup.exe, GUninstall.exe, + exe files (WIX Toolset Installer, sfx, .msi파일(Microsoft Compound))
    - NeroCore-26.5.1060.exe | MD5 : 5998dc6d1d7318f4b71f24ffb3a09c6b
      > NeroInstaller.exe , vc_redist.x86.exe (WIX Toolset Installer)

압축해제 후 해당 폴더 (extract_path) 안에
.exe 파일들 중에 인스톨러 추가 동작 진행
classify_tool.exe 사용해서 인스톨러(installer.exe) 파일 확인
그리고 7z, 사일런스, GUI 설치자동화 로직 차례대로 실행
- 의문점: 압축해제해서 확보한 파일에서 인스톨러가 정상적으로 실행이 가능한가??
- CyberLink_PowerDirector_Downloader.exe | MD5 : eb44b7041d596e4f28036f4ad5719b4f
  (인스톨러 파일 존재 x)
- Divx Player.exe | MD5 : e1ebaddd9bc93758793658365c06516f
  (Setup.exe 파일 존재 but 인스톨러 파일이 아님, installer.exe 파일 압축해제 시 .dll, .exe  Uninstaller.exe.nsis)  
> IDEA 1 : 검증 로직: 압축해제된 폴더에서 인스톨러 파일 2개 이상 있다는 건 제대로 설치 되지 않았다는 것 (Uninstall.exe 인스톨러 타입)
> 에외처리 후  사일런스 모드  or gui 설치 자동화
> IDEA 2 : 압축해제된 폴더내 의 $ 파일명 및 폴더명을 가진다??

> 온전한 프로그램 파일을 얻었으면 의존 문제로 프로그램이 실행 안되는건 상관없다.
> 검증 로직 

- IDEA 1 : 압축해제된 폴더 인스톨러 파일 카운트 (분류조건 : 2개 이상)(Uninstall.exe 인스톨러 타입)
  - NSIS
    수동설치 : 0
    압축해제 : 3 (8k downloader, Codec Decoder Pack, Dvix Player)
  - 7z installer
    수동설치 : 0
    압축해제 : 2 (DWG FastView : 4, Comodo Firewall : 2)
  - msi
    압축해제 : 0
  > cyberlink_Downloader 폴더가 잡히질 않았음

- IDEA 2 : 


[etc]
- Acronis installer[ZIP] 해당 인스톨러 타입 -> zip
arhive 파일로 바라보고 압축해제 로직을 적용해도 되지 않을까??
압축해제 시 Acronis installer[ZIP]:   (1 / 1)
파일이 하나밖에 없어서 일반화가 어렵긴함
- 검증 로직(IDEA)
  - 압축해제된 파일에서 인스톨러 파일 카운트 (조건: 2개 이상)
    ```
    IDEA 1 : 압축해제된 폴더 인스톨러 파일 카운트 (분류조건 : 2개 이상)(Uninstall.exe 인스톨러 타입)
    - NSIS
      수동설치 : 0
      압축해제 : 3 (8k downloader, Codec Decoder Pack, Dvix Player)
    - 7z installer
      수동설치 : 0
      압축해제 : 2 (DWG FastView : 4, Comodo Firewall : 2)
    - msi
      압축해제 : 0
    ```
  - 폴더 이름에 $(dollar_sign) 카운트 or 확인(bool)
  - 파일이름에 setup.exe (setup, installer, ...) 설치 파일 관련 파일 이름을 포함하고 있는지 확인

2.3. 7z 압축해제 실패 케이스
- 압축 해제 실패 시 예외처리 
  > 예외처리 후 사일런스 모드로 접근
  - NSIS : 실패 케이스 
    `AsfTools310.exe` : [Nsis] 압축파일로 파일을 열 수 없습니다.
    `DVD Genie.exe` : [Nsis] 압축파일로 파일을 열 수 없습니다.
  - msi : 실패 케이스 x
  - 7z installer : 실패 케이스 x


1. 인스톨러 사일런스 모드 지원 옵션 확인 및 분류.
  > 사일런스 모드 확인 방법 (setup.exe /? or /help)
  ```bash
  "Advanced installer": ["/quiet"]  or ["/exenoui"],      
  "BitRock installer": ["--mode", "unattended"],          
  "CreateInstall-Overlay": ["-silent"],
  "Ghost installer": ["/S"],
  "Inno Setup": ["/VERYSILENT", "/SUPPRESSMSGBOXES"],     
  "InstallShield": ["/s", "/v\"/qn\""],                   
  "Microsoft Installer(MSI)": ["/qn"],                    
  "NSIS": ["/S"],                                         
  "QT installer": ["--accept-licenses", "--default-answer", "--confirm-command install"]
  "Setup Factory": ["/S"],
  "Sony Windows installer": ["/q"],
  "Windows Installer": ["/qn"],
  "Wise Installer": ["/s"]
  ```

3.1 인스톨러 사일런스 모드 설치 성공.
  > 설치된 파일 사용

  Test 결과
  ```
  Acronis installer[ZIP]: ( 0 / 1 )
  Advanced installer  (1 / 1)
  BitRock installer (0 / 1)
  CreateInstall-Overlay (0 / 1)
  Ghost installer  (1 / 1)    
  Inno Setup  (9 / 10)     
  InstallSheild (1 / 12)
  QT installer (0 / 1)     
  Setup Factory (1 / 14)
  Sony Windows installer (3 / 3)
  Wise Installer ( 10 / 11)
  Windows Installer (1 / 1)
  ```

Test 결과
(사일런스 모드 설치 성공 / 인스톨러 파일)
  - Inno Setup 샘플 (9 / 10) 설치 확인.
  - Wise Installer 샘플 (10 / 11) 설치 확인.
  - InstallSheild  샘플 (1 / 12) 설치 확인.
  > silent option 전부 지원하지 않음 그리고 미리 확인도 어려움
  > (확인 방법 setup.exe /? or /help)
  > python (subprocess) 코드 작성해서 확장해서 확인 필요

3.2 인스톨러 사일런스 모드 설치 실패.
  > 설치 실패 시 예외처리 CAPE & GUI 접근

Test 결과
(사일런스 모드 설치 성공 / 인스톨러 파일)
  - Inno Setup 샘플 (9 / 10) 설치 확인.
  - Wise Installer 샘플 (10 / 11) 설치 확인.
  - InstallSheild  샘플 (1 / 12) 설치 확인.
  > Inno Setup 예외 케이스 1 (Error opening)
  > Wise Installer 예외 케이스 1












4. 설치 자동화
> CAPE 오픈소스에서 설치 자동화 관련 코드 분석   
> GUI 구성요소 전부 파악해서 (Button) click  / dontclik 리스트 나눠놓고 계속 실행
> + checkbox, radiobutton, progressbar, ... case 확인 후 처리


4.1. CAPE 설치 자동화 코드 확인
- CAPE 자동화 코드 업데이트 해서 적용 고려.
> CAPE 한국어 구성요소 추가 및 코드 확인.
> `CAPEv2/analyzer/windows/modules/auxiliary/human.py`
> 실행파일 사람처럼 설치 및 실행 (button, dontclick 리스트로 나눠놓음)
> `CAPEv2/analyzer/windows/modules/packages/zip.py`
> path : ("ProgramFiles", "7-Zip", "7z.exe") -> 환경변수로 해당 경로 가져와서 7zip 실행

4.2. 설치 자동화 툴 확인
> CAPE나 다른 프로그램에서 사용하는 설치 자동화 툴이 있다면 참고.
- 자동화 툴 사용 시 설치 자동화 구현 잘되는지 확인.

4.3. 설치 자동화 직접 구현
> GUI 구성요소 컨트톨 해서 자동화
> keyboard, mouse 외부 입력 사용해서 자동화


## Part 2

6. 설치된 파일 확보
> 모니터링 후 설치된 파일  생성 시 파일 확보

6.1 CAPE 사용 시
> CAPE API를 사용해 파일 업로드 기능 구현.
> 해당경로 `/opt/CAPE/storage/analyses/{analysis_id}/files/`에서 파일 확보

6.2 7zip, 인스톨러 사일런스, GUI 자동화 구현 시
> 모니터링 후 설치된 파일 생성 시 파일 확보
> `watchdog` 라이브러리 사용 및 확인




## Goal : Installer.exe -> Program.exe (Auto Install)

1. CAPE 로컬 PC의 파일과 인스톨러에서 설치된 파일을 직접 비교해 파일이 어느정도 비율로 확보가 되는지 파악할 것.  
- 파일 비율 또는 개수에 따라 케이프에서 설치됐는지를 판단해볼 수 있음.  
  > Seperate-Installer.py Data 폴더 안에 Installer Type 별로 폴더로 분리           
  > Data(588(1 file unzip 531 -588)) NSIS : 137개           
  > NSIS 10 30-40% 확보

[feedback]
- 설치실패한 파일 다시한번 체크
- app_cnt, cape_cnt 크기 차이가 나는 이유 (fact(appdata나 그런 파일인지 확인)  -> so What? 나의 해석 및 의견 필요 -> 필요없다??)
- [compare_folder.py] 필요한 정보만 row 로 잘 출력하게 처리



1. CAPE API를 사용해 파일 업로드 기능 구현.
- 타임 아웃, 결과 등은 잘 맞춰둘 것.
  > CAPE submit Timeout(default : 120) : 하지만 항상 120초 이내로 일정하지 않음 분석 시간이 초과할수 있음         
  > 타임아웃 및 예외처리 필요            
 
API 항목
- File Create
  - Rate Limits(RPS: 1/s, RPM: 2/m )
  - Description : Submit a file task to be analyzed by CAPE. Return object will be JSON
```    
curl -F file=@/path/to/file -F machine="VM-Name" -H "Authorization: Token YOU_TOKEN" http://example.tld/apiv2/tasks/create/file/
  Note: machine is optional. Header depends of the config if Token auth is enabled
```

2. CAPE 로컬에서 analysis_id에 따라 설치된 파일을 직접 확보할 것.  
   - 케이프를 사용해 자동 설치된 파일은 하기의 경로에서 확보가 가능함.   
    > /opt/CAPE/storage/analyses/{analysis_id}/files/      
    > 파일명은 SHA-256으로 제공됨. -> 비교            
    - 케이프 웹에서 제공되는 정보는 100%가 아닐 수 있음.        
   - 직접 확보 코드 파이썬.              
   - CAPE API를 사용해 설치된 파일을 직접 확보해도 됨.            
 
3. 이전 단계 완료하면 예외 케이스들 기준 설치 자동화를 해야할 필요가 있음.            
우선 1번 항목부터 확인할 것.  - 분류부터 진행. 우선순위 NSIS 나머지 그다음.             


```bash
sudo cp [옵션] [복사 대상 디렉터리or파일] [복사될 디렉터리or 파일]

cp test.js test_backup.js
cp /hw/js/test.js /backup/js/test.js
```


```bash
sudo cp /opt/CAPE/storage/analyses/{analysis_id}/files/  [dst_path]

```



## Goal : Installer.exe -> program.exe (Auto Install)
- pywinauto - 소프트웨어 테스트 자동화 lib
- Classify-Tool -> DIE(Detect It Easy) 실행파일
- shell 명령어로도 사용가능하긴 함 -> slient  -s 옵션이 있는 설치파일만??    
- Classify-Tool -> 어떤 Installer 인지 파악 후

Case 분류

## Installer Types

- NSIS         
- [Inno Setup](https://jrsoftware.org/isinfo.php)         
- MSI         
- WISE Installer     
- [Cabinet(file format))](https://en.wikipedia.org/wiki/Cabinet_(file_format))             
- InstallSheild     
- [(wiki)List of installation software](https://en.wikipedia.org/wiki/List_of_installation_software)     

## 방법1 (slience 옵션)     
- 파이썬으로 경로 먼저 받기 (python auto-instlal.py (path value))      
  - path 파일일때 , 폴더일때 (os.listdir) <- 근데 요건 1차원까지만.      
- Classify-Tool -> 어떤 Installer 인지 파악(어떤 Installer Type을 사용했는지)         
- shell 명령어로도 사용가능하긴 함 -> slient  -s 사일런스 옵션이 있는 설치파일            
  (확인사항 : 해당 Installer에서 설치파일을 만들 때 기본적으로 사일런스 옵션을 주는지 확인필요)           
  (해당 Installer에서 사일런스 옵션을 지원하는지 (그리고 사일런스 옵션의 종류 및 사용방법 (옵션이 다양할 수 있음)))    
- 해당 Installer에 맞는 명령어 옵션 넣고 설치 후 -> watchdog로 모니터링   
  (event 발생 -> Action (새로 설치된 파일들 Installed Data 폴더로 Shutil.move python lib ))   

- NSIS
  ```
  .\installer.exe /S
  ```
- [Inno Setup](https://jrsoftware.org/isinfo.php)
  ```
  .\installer.exe /SILENT 
  ``` 
- WISE Installer

- Cabinet

- InstallSheild
  ```
  .\installer.exe  /s
  .\installer.exe  /s /v/qn  # basic MSI install parameters
  ```

- WIX Toolset's
  ```
  .\installer.exe  /q
  /q ; /quiet ; /s ; /silent
  ```

- Advacned Installer
  ```
  .\installer.exe  /exenoui
  ```

- MSI (Microsoft Installer) -> silent 모드 지원
  ```
  msiexec /i <path to msi> /qn /norestart
  installer.msi /quiet
  .\installer.msi /qb!          (e.g) .\SibSetup.msi /qb!
  ```
- [(msdn)Microsoft Standard Installer command-line options](https://learn.microsoft.com/en-us/windows/win32/msi/standard-installer-command-line-options)
- [(msdn)msiexec](https://learn.microsoft.com/ko-kr/windows-server/administration/windows-commands/msiexec)
- [(stackoverflow)MSI패키지 자동 설치](https://stackoverflow.com/questions/8560166/silent-installation-of-an-msi-package)
- [Silently Install EXE and MSI setup applications (Unattended) - How To Guide](https://www.advancedinstaller.com/silent-install-exe-msi-applications.html)
- [EXE 또는 MSI 설치 프로그램 - 귀하의 비즈니스에 가장 적합한 것은? | 차이점 및 권장 사항](https://www.advancedinstaller.com/exe-vs-msi-installer.html)

## 방법2
GUI로 접근
case 나눠서 실행과정 진행
일단 case 하나 정해서 진행
(일단 목적 어떻게든 Next(다음)으로 넘어가서 Install(설치) 하는거임)
(해당 버튼들 이름이 있는지 확인 , 그다음 해당 버튼이 활성화(enable) 되어있는지 확인 -> 확인되면 바로바로 클릭)
(프로그래스바: 100프로 되면 기다리지 않고 바로 다음 페이지로 넘어갈 걸로 추정)(일단 while 문으로 처리)


- pywinauto
- [pywinauto docs](https://pywinauto.readthedocs.io/en/latest/getting_started.html)
- PyInspect - 위젯 요솔르 GUI로 확인하기



## Installer Types
- NSIS
- [Inno Setup](https://jrsoftware.org/isinfo.php)
- MSI
- WISE Installer
- Cabinet
- InstallSheild



## After Install (Detect change) use python lib
- Monitoring script -> file change -> move to Data folder
- Watchdog lib
- [(docs)Watchdog](https://pythonhosted.org/watchdog/)
- [[Python]PyQt5, Watchdog을 이용한 파일 데이터 실시간 전송 프로그램 만들기](https://glow153.tistory.com/19)
- [(풍류의 데이터 분석)[Python]파일/생성 모니터링](https://windflex.wordpress.com/2017/11/02/python-%ED%8C%8C%EC%9D%BC%EC%83%9D%EC%84%B1-%EB%AA%A8%EB%8B%88%ED%84%B0%EB%A7%81/)
```
pip install watchdog
```
- [Magika(함께해요 파이썬 생태계)](https://wikidocs.net/231310)


## Reference

- Installer
- [(wiki)List of installation software](https://en.wikipedia.org/wiki/List_of_installation_software)
- [Silently Install EXE and MSI setup applications (Unattended) - How To Guide](https://www.advancedinstaller.com/silent-install-exe-msi-applications.html)

- python
- [Argparse](https://wikidocs.net/73785)
- [Python-Command-Line Arguments](https://www.tutorialspoint.com/python/python_command_line_arguments.htm)
- [python csv, writing headers only once](https://stackoverflow.com/questions/28325622/python-csv-writing-headers-only-once)

- pywinauto
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


- 7-zip
- [Using os.system in python to run external programs](https://www.tech-artists.org/t/using-os-system-in-python-to-run-external-programs/3290)
- [7zip Commands from Python](https://stackoverflow.com/questions/11067097/7zip-commands-from-python)

- watchdog
- [(medium)Python:Event Monitoring with watchdogs](https://pravash-techie.medium.com/python-event-monitoring-with-watchdogs-86125f946da6)
- [(API Reference) watchdog.events](https://python-watchdog.readthedocs.io/en/stable/api.html#module-watchdog.events)
- [(pypi)watchdog](https://pypi.org/project/watchdog/)



- AutoIT
- [(Q):powershell script to automate s/w installation (A):Use AutoIT ](https://forums.powershell.org/t/powershell-script-to-automate-s-w-installation/9143)
- ETC
- [Silent Install Buidler](https://www.silentinstall.org/)
- [(WikiDocs)레벨업 파이썬](https://wikidocs.net/book/4170)
- [Avoid using shell=true in python subprocess module](https://medium.com/@acharya.vikash/avoid-using-shell-true-in-python-subprocess-module-e95fed487f19)








# Memo

[0905], [0906]
- CAPE
  - CAPE에서 auto-install -> drop file 항목에 있는 파일들이 실제로 설치했을 때랑 같은건지 확인
  - CAPE에서 설치가 안되는 케이스들 확인
- 가상환경 설치해서 확인 -> 가상환경에서 확인하는 이유?? -> 비정상 파일이 있을수 있어서 ??
  - 설치파일들 확인해달라고
- Same folder에서 Installer Type에 따라 분류
  - `Seperate-Installer.py`
  - Installer Type 확인 (Classify-Tool.exe 사용해서 출력)
  - 해당 Install Type 폴더로 파일 옮기기(Shutil.move)










## Install Case (in test-sample folder)

case 1 : `Codec Installer.exe` (NSIS)
- app.start
- 설치마법사 인트로, Next(Button)
- License Agreement (checkbox.toggle), Next(Button)
- Choose Component (Install option)(패스함), Next(Button)
- Choose Install Location (설치경로)(패스함), Next(Button)
- Additional Optaion check(패스함), Install(Button) .click_input() 메서드 사용( 이건 좀더 사람처럼 눌러주는거)
- Installing (progress bar) (while 문처리), Next(Button)
- Complete Install , (Run program)checkbox.toggle() Finish (Button)

case 2 :  `Free Screen Recorder.exe` (Inno Setup(5.1.10))
- Setup 팝업창 (This will Free Screen Recorder. Do you wish to continue?) (예(Y), 아니요(N))
- 설치마법사 인트로, Next(Button)
- Select Destiantion Locaion , Next
- Select Start Menu Folder, Next
- Select Addiional Task, Next
- Ready Install , Install 
- progressbar,
- compelte Install, (Run program)checkbox.toggle() Finish (Button)

case 3 : `SmartLock_1.3.0a_Setup.exe` (NSIS)
- 설치마법사 인트로, 다음 >
- 사용권 계약 위 사항에 동의합니다 / 동의하지 않습니다. (RadioButton) ,  다음 >(Button)
- 설치 위치 선택()  , 설치(Button)
- 스마트락 1.3.a 실행하기 (체크박스), 마침(Button)

case 4 :  `TPAKTOR.exe` (Wise Installer)
- 설치마법사 인트로, Next >
- SOFTWARE LICENSING, Next > 
- Destiantion folder(설치 경로), Next (Button)
- Addiional option, Next (Button)
- Addiional option, Next (Button)
- Next (Button)
- Prograss bar window 
- Finish

case 5 : `곰녹음기.exe` (NSIS)
- 설치마법사 인트로 , "다음 >" (Button)
- 약관 동의, (scroll 구성요소 확인 필요(Page Down 키로도 처리 가능)), 동의함 (Button)
- 구성요소 선택, "다음 >" (Button)
- 설치폴더(찾아보기...), 설치  (Button)
- 설치 진행 프로그래스바
- 곡녹음기 설치 완료, 곰녹음기 실행하기(checkbox.toggle()) / 마침 (Button)


case 6 : `SibSetup.msi` (MSI)
- Setup Wizard Intro, Next
- End-User Licesne Agreement 스크롤 막대(ScrollBar),
  I accept the terms in the License Agreement (Checkbox) -> Next (Button) 활성화
- Destination Fodler (설치경로), Next(Button)
- 설치 페이지,  Install(Button)
- Installing, (ProgressBar)<- Value로 접근  //추가설치 팝업창(6a063b5.msi)
- Complete, Finish (Button)


case  : `녹음마법사.exe`  ZIP 파일






## VMware WorkStation            
- [Downlaod Window10](https://www.microsoft.com/en-us/software-download/windows10)
- [Windows 10용 ISO 파일 만들기](https://support.microsoft.com/ko-kr/windows/windows-10%EC%9A%A9-iso-%ED%8C%8C%EC%9D%BC-%EB%A7%8C%EB%93%A4%EA%B8%B0-38547366-1dcb-7afd-1726-9eb222d72705)
- [VMware Workstation download](https://vmware-workstation.informer.com/download/#downloading)
- [VMWare 가상머신 파일 공유 및 복사](https://www.wookoa.com/2024/01/how-to-share-and-copy-vmware-virtual-machine-files.html)




## CAPE
- [CAPE Sandbox](https://capev2.readthedocs.io/en/latest/index.html)
- CASE 1 : 설치 완료 후 프로그램 실행 - 100% 아님.
- CASE 2 : 설치 완료 - 샘플 미확보.
- CASE 3 : 설치 실패 - 실패.
- 설치 후 실행되더라도 드롭 파일로 온전히 확보가 안 되는 케이스가 있음.
- 해당 케이스는 프로세스 덤프에서 설치된 파일 중 실행 파일 확보가 가능함.
- 케이프를 사용해 자동 설치된 파일은 하기의 경로에서 확보가 가능함.
  (케이프에만 결과가 안 보일 뿐 설치된 파일은 확보가능함.)
> /opt/CAPE/storage/analyses/{analysis_id}/files/
> 파일명은 SHA-256으로 제공됨.
- 케이프 웹에서 제공되는 정보는 100%가 아닐 수 있음.

### Result
[NSIS-Test]     
- NSIS 샘플 137개 (전체 샘플 500개 중)     
- CAPE Sandbox 및 수동 설치 결과 비교 (105개)  
  > 샘플 137 -> 105 (CAPE Submit fail & Install fail)      
  > 샘플 64 match_pe_percent : 0 / 샘플 41 match_pe_percent > 0           
  > 샘플 33 (match_pe_percent > 0.6)         
[결론]            
- 인스톨러 중 30-40% 만 설치파일 확보      
  > CAPE만으로는 설치파일 확보가 어려움         
