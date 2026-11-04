# GMK Yuru / Shima Rin rice

현재 사용하는 Sway rice의 설정 원본과 운영 안내다. 확인일: **2026-11-04**.
시마린 배경, GMK Yuru의 크림·버건디·민트를 바탕으로 Ubuntu Mono·D2Coding 고정폭 UI·터미널과 실제 프로그램 출력을 사용한다.
ASCII 느낌은 문자 정렬·짧은 Bash 프롬프트·얇은 경계로 만들고, 장식용 코드 라벨이나 대시보드는 넣지 않는다.

## 현재 구성

| 부분 | 구성과 적용 상태 |
| --- | --- |
| Sway / SwayFX | 1px 직각 경계, 비활성은 어두운 자주빛·활성은 낮은 채도의 청록색. inner gap 6 / outer gap 2. 기존 타일링·입력·게임·전체화면 설정 유지. |
| Waybar | 하단 26px, 좌우 24px·아래 12px 여백의 플로팅 배치. 왼쪽 숫자 workspace, 오른쪽 접히는 트레이·Codex·Grok 남은 한도·시각과 기본 마이크 음소거 시 빨간 마이크 빗금 아이콘 표시. Adwaita의 `microphone-disabled-symbolic.svg` 사용. |
| Kitty / Bash | Ubuntu Mono, Yuru 16색, 불투명도 0.75, Kitty blur 켬. Bash는 경로와 `$`/`#` 프롬프트. 새 셸부터 반영. |
| Rofi | 13pt. 입력·일반 행은 어두운 배경에 크림 글자, 선택은 민트 배경에 먹색 글자. |
| GTK3 / GTK4 | Adwaita 기반 CSS, Ubuntu Mono·D2Coding 10.5pt(14px), dark 선호. 아이콘은 Yuru, 커서는 Adwaita. |
| Thunar | GTK 테마와 상세 목록·경로 입력창 사용. 비활성 창의 메뉴바 남은 폭도 같은 배경색으로 통일. |
| Qt5 / Qt6 | Ubuntu Mono·D2Coding 10.5pt·고정폭 Ubuntu Mono 11pt, Fusion 팔레트와 버전별 QSS. 공통 환경 키는 `QT_QPA_PLATFORMTHEME=qt5ct`. |
| Dunst / Fcitx5 / gtklock | 알림·입력 후보창·잠금 UI의 색과 글꼴 통일. MSI에는 현재 ASCII 배경의 정지 장면·시계·입력창, LG는 완전한 검정. 실제 세션 lock/unlock은 미검증. |
| swaynag | 종료 확인·설정 오류 UI. warning/error 색과 글꼴을 기본 설정에 연결. 다음 실행부터 적용. |
| Code - OSS | 기존 설정에 UI 색·폰트 병합. JSONC·별도 프로필은 자동 병합 대상에서 제외. |
| Firefox | 직각 UI·Ubuntu Mono/D2Coding 14px와 시마린 새 탭. **사용 중인 프로필은 다음 정상 재시작에 새 글꼴 반영**. 별도 프로필 가로·세로 실렌더 확인. |
| Chrome | 네이티브 테마의 탭·툴바·주소창 색과 시마린 새 탭 배경. 파일 설치 완료, 최초 테마 선택은 아래 절차 필요. |
| ChatGPT 데스크톱 | 공식 Appearance 설정의 배경·글자·민트 강조와 UI/코드 폰트. 네이티브 설정 저장 도구 제공. |
| Steam | Millennium CSS 테마. 라이브러리·설정의 먹색/크림·민트·공통 UI 글꼴과 직각 컨트롤, 상점/커뮤니티 웹 색상. |
| Discord | BetterDiscord Yuru Kitty. 프사를 유지한 고정폭 UI·먹자주 반투명 배경·민트 강조. Nitro 프로필/장식과 미디어 보존. |
| btop | CPU·GPU·VRAM·RAM·프로세스. 2초 갱신, 직각 테두리·민트 그래프. |
| cava | 기본 출력 소리를 민트색 막대로 표시. 터미널 배경·투명도 유지. |
| Usage | CodexBar CLI를 사용하는 자체 GTK3 창. Codex·Grok 한도와 초기화 시간, 5분 갱신. |
| 배경 | 겨울 호수 컨셉 1을 실제 문자 격자로 렌더. 복원 캐릭터만 alpha 합성. 작은 저대비 글자, 마우스 입력 없음. |

GPU Screen Recorder UI의 내부 팔레트는 현재 자동 적용 범위에 포함하지 않는다.
전체 Sway reload나 실행 중 앱의 일괄 종료 없이 적용했다. **OS 재부팅·재로그인 검증은 아직 하지 않았다.**

Kitty는 `kitty.conf` 마지막의 `yuru-theme.conf` 값이 우선한다. 템플릿의
`dynamic_background_opacity yes`를 유지해야 새 창에서도 이후 불투명도를 변경할 수 있다.
`pkill -USR1 -x kitty`로 열린 프로세스 전체에 설정을 다시 읽히며, 불투명한
framebuffer로 시작한 기존 창은 투명도를 켜려면 정상 종료 후 다시 실행해야 한다.
`activate.py apply`는 설치된 effects.conf의 Kitty blur 규칙을 새 창과 기존 창에 동일하게 적용한다.
2026-10-31 실제 세션의 Kitty 9개에서 재읽기 후 effective-config 갱신과 SwayFX의
기존 창 blur 명령 성공을 확인했다. 개별 창의 렌더링 불투명도는 직접 조회하지 않았다.

## 팔레트

색과 기본 글꼴의 원본은 [`palette.json`](palette.json)이다.

| 용도 | 값 |
| --- | --- |
| 배경 / 면 | `#1E191F` / `#2A222B` |
| 주소창 입력 포커스 면 | `#35383C` (`focus_surface`) |
| 창 경계 / 활성 창 경계 | `#493842` / `#597B77` (`window_border` / `window_border_focused`) |
| 글자 / 밝은 글자 | `#E1DBD1` / `#EAECF0` |
| 선택·강조 | `#88D4CC` |
| 경계 | `#712F3E` |
| 보조 글자 | `#A69A9F` |
| 오류·부족 상태 | `#D58C97` |
| 터미널·코드 글꼴 | Ubuntu Mono (`font`), 한글은 D2Coding (`fallback_font`) |
| UI 글꼴 | Ubuntu Mono (`browser_font`) + D2Coding, Firefox·GTK·Qt·알림·후보창 등에 적용 |

## 설정 위치

```text
yuru/
├── palette.json             색·글꼴·ANSI 16색
├── wallpapers.json          현재 배경 선택
├── templates/               앱별 설정과 Usage 소스
├── assets/                  배경 원본·보정본·업스케일본·생성 프롬프트
├── theme.py                 생성·설치·업데이트·복원
├── activate.py              현재 세션의 시각 설정 반영
├── install_codexbar.py      고정 버전 CLI 설치와 SHA256 확인
├── install_fonts.py         한글 fallback용 D2Coding Regular/Bold 설치
├── test_theme.py            설치·복원 검증
├── test_usage.py            한도 응답·타임아웃 검증
├── verify_firefox.py        격리 Firefox UI·본문 분리·재실행 검증
├── verification/            검증 기록과 화면
└── build/                   재생성 산출물, Git 제외
```

이 폴더가 rice의 원본이다. `build/`나 설치된 CSS를 직접 고치기보다 palette·templates를 수정한다.
기존 [`sway-desktop/`](../sway-desktop/README.md)는 세션 시작·입력·화면·게임 설정과 활성 symlink 경로를 유지한다.
`theme.py`는 symlink를 교체하지 않고 그 대상에 설정을 설치한다.

| 항목 | 설치 위치 |
| --- | --- |
| Sway appearance·배경·Bash·Usage | `~/.local/share/yuru-theme/` |
| 앱 설정 | `~/.config/` 아래 앱별 디렉터리 |
| btop | `~/.config/btop/btop.conf`, `themes/yuru.theme` |
| cava | `~/.config/cava/config` |
| Usage 실행 명령 | `~/.local/bin/yuru-usage` |
| Rofi 실행 항목 | `~/.local/share/applications/yuru-{usage,btop}.desktop` |
| Firefox | 선택된 프로필의 `chrome/yuru.css`, `yuru-content.css`, 새 탭 배경 두 장, userChrome/userContent import와 `user.js` flag |
| 원본 백업·설치 기록 | `~/.local/state/yuru-theme/`, Git 제외 |

현재 호스트의 적용 기록은 private-configs의 `hosts/hanusearch/docs/yuru-theme.md`에 있다.
다른 호스트에서는 DP-5/DP-6, Qt 경로와 시작 훅을 먼저 검토한다.

비활성 창은 기존 테두리 색이 앱의 면 색과 같아 경계가 묻혔다. 창 경계는 별도 팔레트 키로
지정해 팝업에도 은은한 1px 선을 남기며, 앱 내부의 버건디·민트 강조색과 독립적으로 조정한다.
`client.focused_inactive`와 `client.unfocused`에 같은 기본 선을 쓰고 활성 창만 청록색으로 구분한다.
원본은 `templates/sway/appearance.conf`이며 마지막 Sway include에서 다음 세션에도 읽는다.
현재 설치본 갱신은 `python theme.py update --live --only .local/share/yuru-theme/sway.conf`,
현재 세션의 시각 설정 적용은 기존 `python activate.py apply`를 따른다.
2026-10-31 설치본을 읽는 격리 Sway·GTK 앱을 두 번 새로 실행해 활성·비활성 창 네 변의
색과 1px 폭을 확인했다. [경계 미리보기](verification/native-window-borders.png),
[검증 범위](verification/window-borders.json). 실제 데스크톱 재시작·재부팅·재로그인은 수행하지 않았다.

## 배경

선택 원본은 [`wallpapers.json`](wallpapers.json), 출력은 `build/wallpaper*.png`다.

| 화면 | 현재 이미지 | 크기 / 배치 |
| --- | --- | --- |
| DP-6 가로 | [waifu2x 2× 가로](assets/wallpaper-retouched_waifu2x_noise0_scale2x.png) | 3876×1624 → 3440×1440, `fill` |
| DP-5 세로 | [waifu2x 2× 세로](assets/wallpaper-portrait-retouched_waifu2x_noise0_scale2x.png) | 1624×3870 → 1440×3440, `fill` |

built-in imagegen으로 만든 원본에서 풍경·옷 주름·마을 등의 디테일을 유지하며
얼룩과 튀는 빛을 약하게 보정했고, 사용자가 waifu2x로 2× 업스케일했다.
위 파일을 2026-10-31 실제 배경에 적용했다. 두 이미지 비율이 화면과 조금 달라 `fill`에서 가장자리가 일부 잘릴 수 있다.

현재 ASCII 캐릭터의 재생성 입력인 **1× 보정 원본**과 프롬프트는 남긴다:
[가로 원본](assets/wallpaper-retouched.png) / [프롬프트](assets/wallpaper-retouched-prompt.txt),
[세로 원본](assets/wallpaper-portrait-retouched.png) / [프롬프트](assets/portrait-wallpaper-retouched-prompt.txt).
[retouch 생성 기록](assets/retouched-wallpapers.json)의 이전 참조는 파일이 아니라 Git 커밋·SHA로 기록한다.
현재 정적 fallback·브라우저 새 탭 두 장의 크기·SHA는 [검증 기록](verification/monitors.json)에 있다.

2026-11-01 미사용 초기/soft 가로·세로 4장과 해당 프롬프트·생성 기록 5개, 중복 컴파일
미리보기 2장을 삭제했다. 총 11개·12.98MiB이며 Git 이력은 유지한다.
[삭제 목록·SHA·복원 기준](verification/wallpaper-cleanup.json)을 따른다. 예를 들어 초기 가로는
`git restore --source=6d5d35b -- assets/wallpaper.png`로 복원한다.
현재 `scene_assets.json`의 RGB·alpha·문자 격자, `wallpapers.json`의 fallback/새 탭,
1× 보정 입력, 선택한 겨울 호수 컨셉과 실제 검증 캡처는 유지했다.
컴파일러는 기본 실행에서 중복 PNG를 만들지 않는다. 필요할 때만
`python compile_ascii_reference.py --preview /tmp/yuru-reference.png`로 검토본을 생성한다.
정리 후 테마 build·ASCII 재컴파일의 바이트 일치·19개 테스트·설치본 SHA를 확인했다.
실행 중 앱이나 설정을 바꾸지 않았고 재시작·재로그인·재부팅도 수행하지 않았다.

## 잠금화면

MSI(`DP-5`)에는 현재 세로 ASCII 겨울 호수·복원 시마린의 정지 장면을 표시한다.
시계·날짜·입력창은 얼굴 위쪽 하늘의 직각 패널에 둔다. LG OLED(`DP-6`)와
MSI 외 출력은 배경·시계·입력·인증 메시지를 표시하지 않고 검정을 유지한다.
`config.ini`의 기존 `monitor-priority=DP-5;`, `follow-focus=false`와 Super+L·절전 전
`~/.config/sway/scripts/lock` → gtklock 경로를 유지한다. 다음 잠금부터 적용하며
데스크톱을 다시 읽거나 사용 중인 세션을 잠글 필요는 없다.

원본은 `templates/gtklock/style.css`, GTK3/4 템플릿의 마지막 출력 보호 규칙,
`gtklock_output_names.c`다. `theme.py build`는 기존 `ascii_wallpaper.render_still`로
1440×3440 배경을 만들고 gtklock **5.x** 모듈을 컴파일한다. 빌드에는 기존 ASCII 런타임 외에
C 컴파일러·pkgconf·GTK3 개발 헤더가 필요하다. 배경/모듈은 `.config/gtklock/`에 설치하며
재생성 산출물은 Git에서 제외한다. 설치기는 기존 config의 다른 키·모듈을 보존해 이름
보정 모듈 경로만 추가하고, 기존 백업·SHA·복원 journal로 모든 파일을 관리한다.

공통 GTK 사용자 CSS는 앱 CSS보다 우선하므로 예전의 `window#DP-5, window#DP-6`
검정 규칙에서 MSI를 제외해야 그림이 보인다. 또 gtklock 5.0은 hotplug의 `monitor-added`
시점에 연결 이름을 한 번 읽어, 이름이 늦게 도착하면 창이 무명으로 남는다. 모듈은 GTK의
`monitors-changed`와 초기 idle에서 **동일한 GdkMonitor**의 이름을 다시 지정한다.
그 전에는 `yuru-lock` 클래스의 무명/비MSI 창을 사용자 CSS에서 검게 보호한다.
이 모듈은 기본 `~/.config/gtklock/config.ini`의 첫 `monitor-priority`를 읽고
재연결된 MSI로 기존 gtklock 포커스 함수를 호출해 입력창도 되돌린다.
인증·세션 잠금 코드는 변경하지 않는다.

```sh
python theme.py update --live \
  --only .config/gtklock/style.css \
  --only .config/gtklock/background.png \
  --only .config/gtklock/yuru-output-names.so \
  --only .config/gtklock/config.ini \
  --only .config/gtk-3.0/yuru.css \
  --only .config/gtk-4.0/yuru.css
python verify_gtklock.py
```

검정을 복원하려면 잠금 CSS의 MSI `background-image`를 `none`으로 바꾸고, 두 GTK
템플릿 마지막 검정 보호 선택자에 `window#DP-5`도 추가한 뒤 위 선택 갱신을 실행한다.
연결 이름 보정은 그대로 유지한다. 테마 전체를 설치 전으로 복원할 때는 기존
`python theme.py restore --live`가 config 원본을 되돌리고 추가한 배경·모듈을 제거한다.

검증(2026-11-04): 설치본을 두 개의 새 격리 CPU Sway에서 gtklock 5.0.0으로 시작해
잠금 획득·키 입력, MSI 하늘/캐릭터의 정지 장면 픽셀 일치와 LG 전체 픽셀 검정을 확인했다.
두 가상 출력 disable/enable 후에도 스타일·키 입력·LG 검정이 유지됐다. 격리 출력은
HEADLESS 이름이므로 검사에서 CSS 출력 이름만 매핑한다. 설치·복원/ASCII 테스트
49개와 GTK3/4 파싱·Sway 시각 설정 검증은 2026-11-02 기록 그대로다.
[MSI 화면](verification/gtklock-msi.png) · [검증 범위와 SHA](verification/gtklock.json).
실제 사용자 세션 잠금/해제·PAM 인증·OS 재부팅·재로그인·물리 모니터 재연결은 수행하지
않았다. 파일 저장·기존 실행 경로와 격리 앱 재실행 검증을 실제 시스템 재시작과 구분한다.

## ASCII 배경

선택한 [1번 겨울 호수 컨셉](verification/concept-winter-lake.png)의 산·숲·마을·호수 반사·
눈 난간을 실제 고정폭 문자로 그린다. **배경 사진을 깔고 ASCII 필터를 덧씌우지 않는다.**
`compile_ascii_reference.py`가 승인된 컨셉을 오프라인에서 글리프 모양과 비교해 문자·RGB 잉크·
재질의 520×162 격자로 컴파일한다. [`assets/winter-lake-glyphs.json`](assets/winter-lake-glyphs.json)에
입력 SHA와 격자를 저장한다. 런타임 `ascii_landscape.py`는 이 명시적인 셀만 읽으며,
컨셉 이미지나 원본 장면의 배경 RGB는 읽어 그리지 않는다. 단색 바탕 위에 글자만 그린
[인물 없는 배경](verification/ascii-scenery.png)과 [문자 프레임](verification/ascii-frame.txt)을 확인할 수 있다.

캐릭터만 선택한 복원 RGB를 alpha 마스크로 합성한다. ImageGen으로 다시 그린 컷아웃·
CUNet 확대·사진 위 문자 overlay 경로는 폐기했다. `build_character_mattes.py`는 고정된
SwinIR 보존 기준과 수동 외곽/GrabCut으로 alpha만 만든다. 마스크 생성은 RGB를 바꾸지
않으며, 경계 약 1 source-pixel을 보수적으로 제외한다. 현재 RGB 복원 조합은 아래를 따른다.
[원본·어두운/밝은 바탕의 마스크 검사](verification/character-mattes.png).

[`scene_assets.json`](scene_assets.json)은 가로·세로별 복원 RGB·동일 크기의 마스크·
문자 격자를 선택한다. 가로 3876×1624·세로 1624×3870을 각각 화면에 한 번 cover-fit해
오른쪽·아래에 사각 컷아웃의 절단면을 띄우지 않는다. 세로 배경은 같은 문자 크기로 호수의
왼쪽/중앙을 배치하고 하늘은 미세 문자·별로 구성한다. 호수 아래는 원본 하단을 화면
끝까지 연속 배치한다. 컨셉과 픽셀 단위로 동일한 그림은 아니다.

현재 RGB는 원래 1× 보정 그림의 Real-ESRGAN 애니 ×4 복원 결과를 25% 반영한
보존 조합이다. 저장 크기는 가로 3876×1624·세로 1624×3870으로 유지한다. 추론·혼합·
선택 근거와 재생성·복원은 아래 **시마린 확대 재검토와 선택**을 따른다.

작은 글자로 이뤄진 풍경을 위해 격자를 340×106에서 **520×162**로 세분화했다. 3440×1440
기준 글자 크기는 약 15.9px에서 10.4px로 35% 작아졌고 격자 셀 수는 약 2.34배다.
종이색 대비 잉크 강도 0.76은 유지한다. **마우스 이동·클릭·파동 모듈을 제거**했으며
배경 창의 입력 영역은 비어 있다. 눈만 느리게 8fps로 움직이고 전체화면 출력에서는
최대 약 2초 뒤 그리기를 멈춘다.

```sh
python wallpaper_control.py install
~/.local/bin/yuru-wallpaper start
~/.local/bin/yuru-wallpaper status
# 실행 중인 버전 갱신: stop → install → start
~/.local/bin/yuru-wallpaper stop
# 설치와 자동 시작까지 제거해 정적 fallback으로 복원
python wallpaper_control.py restore
# 검토·검증
python ascii_wallpaper.py --preview
python ascii_wallpaper.py --render /tmp/yuru.png --width 3440 --height 1440
python -m unittest test_ascii_wallpaper test_wallpaper_control
python verify_ascii_wallpaper.py
```

런타임 패키지는 `python-gobject`, `python-cairo`, `gtk3`, `gtk-layer-shell`, Ubuntu Mono다.
확대 재생성은 PyTorch·timm·OpenCV·NumPy·Spandrel 환경의 `upscale_scene.py`, 마스크는
OpenCV·NumPy·Pillow 환경의 `build_character_mattes.py --preview`, 컨셉 컴파일은
동일 환경의 `compile_ascii_reference.py`를 사용한다. 실행 중 GPU 추론은 없다.
`~/.local/share/yuru-ascii/`에 렌더러·격자 배치 모듈·팔레트·선택 자산을 설치하며
`~/.local/bin/yuru-wallpaper`가 기본 실행기다.

`~/.config/sway/config.d/95-yuru-ascii.conf`의 exec_always가 기존 include에서 다음 세션에도
시작한다. layer-shell background에서 swaybg 위·Waybar와 앱 창 아래에 표시하며 키보드 포커스·화면 예약
영역을 사용하지 않는다. 런타임 잠금·준비 신호로 중복 실행과 조기 성공 보고를 막는다.
설치 SHA·로그는 `~/.local/state/yuru-ascii/`에 저장하고 외부 편집은 자동 덮어쓰지 않는다.
설치 실패는 되돌린다. 정적 fallback·브라우저 새 탭의 `wallpapers.json`은 별도로 유지하며
stop/restore 시 기존 정적 배경이 드러난다.

2026-11-01: **21개 테스트**로 원본 RGB를 빨강으로 바꿔도 배경이 바뀌지 않음, 인물 표본
픽셀 보존·인물 밖 투명도, ASCII 범위·재질, 입력 핸들러 부재, 이관·복원·외부 편집·중복
실행을 확인했다. 두 번의 새 격리 Sway에서 입력 비활성화·실제 앱 클릭/포커스·전체화면
정지/재개·가상 출력 크기 변경/재연결을 확인했다. 실제 호스트에서 새 기본 버전 설치·재실행·
중복 시작, 설치 SHA·준비 신호, 기존 swaybg·출력 설정 보존과 SwayFX config validate를 확인했다.
[검증 기록](verification/ascii-wallpaper.json), [가로](verification/ascii-landscape.png),
[세로](verification/ascii-portrait.png). OS 재부팅·재로그인·물리 모니터 재연결은 미검증이다.

### 세로 배경 반복 수정

2026-11-01 하단·오른쪽에서 같은 무늬가 되풀이되던 원인은 `ascii_landscape.py`의
하늘 strip modulo 샘플링과 전경 마지막 5줄 복제였다. 세로 하늘은 좌표별 미세 문자·별로
구성하고, 호수 아래는 원본 하단 30%를 남은 화면 높이까지 한 번만 연속 배치한다.
잉크는 이웃 셀 사이에서 보간하고 문자는 원래 글리프 중에서 선택해 통째로 같은 행이
늘어나지 않게 했다. 오른쪽 샘플링 범위도 원본 안에 유지한다.

하단 마지막 40줄의 고유 행은 기존 5개에서 40개가 됐고, 5줄 주기 동일 행 쌍은 35개에서
0개가 됐다. 하늘 순서를 바꿔도 세로에 strip 무늬가 옮겨오지 않는 회귀 검사를 추가했다.
21개 테스트·새 격리 Sway 두 번·기본 경로 설치 후 배경 앱 재실행·설치 SHA·출력 크기를
확인했다. 가로 배경 전체 픽셀, 두 방향 캐릭터 RGBA·글자 크기와 Waybar·그림자는 유지했다.
[수정한 세로 화면](verification/ascii-portrait.png) · [검증 기록](verification/portrait-layout.json).
기존 자동 시작 include를 사용하며 이전 배치로 복원하려면 이 수정 커밋을 되돌린 뒤
stop → install → start 순서로 기본 실행본을 갱신한다. OS 재부팅·재로그인·물리 모니터
재연결은 미수행이며 앱 재실행·저장 구조 확인과 구분한다.

### 시마린 확대 재검토와 선택

2026-11-01 HAT_SRx2·2xLexicaSwinIR·RealESRGAN_x4plus_anime_6B를 같은 가로·세로 1×
보정 RGB에서 실제 실행했다. 모든 결과를 공통 2× 좌표로 맞추고 같은 alpha·ASCII 배경으로
실제 표시 크기의 얼굴·앞머리·옷을 비교했다. HAT와 Lexica는 기존 SwinIR와 차이가 작았고,
애니 모델 100%는 가장 또렷하지만 피부·붓터치를 셀 채색처럼 평탄하게 바꿨다.

선택은 **애니 ×4 복원 결과 25% + SwinIR 보존 기준 75%**다. 애니 결과를 float RGB에서
area 축소해 공통 2×로 맞춘 뒤 RGB8에서 혼합한다. 40%도 비교했으나 25%가 볼의 색 변화와
붓터치를 더 남기면서 머리·옷 경계를 개선했다. 원출력 세 모델과 강도 비교의 차이를
[비교판](verification/character-upscale-comparison.png)·[가로/세로 전후](verification/character-upscale-before-after.png)에서
확인할 수 있다. 이 그림에 대한 시각 선택이며 고해상도 정답이나 보편적인 품질 순위는 아니다.

```sh
# PyTorch·OpenCV·NumPy·Spandrel 환경에서 같은 1× 입력부터 재생성
python upscale_scene.py --model anime --source assets/wallpaper-retouched.png \
  --preserve-base assets/wallpaper-landscape-swinir.png --restoration-strength 0.25 \
  --output assets/wallpaper-landscape-restored.png
python upscale_scene.py --model anime --source assets/wallpaper-portrait-retouched.png \
  --preserve-base assets/wallpaper-portrait-swinir.png --restoration-strength 0.25 \
  --output assets/wallpaper-portrait-restored.png
```

`upscale_scene.py`는 모델 SHA를 확인하고 float32·192px 타일·32px 문맥 여백으로 추론한다.
기존 `swinir` 기본 경로는 보존 기준 재생성용이며 비교용 `--model hat`·`--model lexica`도
같은 도구를 사용한다. HAT의 공식 Drive가 확인 페이지를 요구하면 공식 체크포인트를
`~/.cache/yuru-upscale-candidates/HAT_SRx2.pth`에 저장한다. 실행 전 고정 SHA 검사를 거친다.
모델·입력·출력 SHA와 최종 명령은 [생성 기록](assets/scene-upscale.json), 후보별 추론·선택·
검증은 [비교 기록](verification/character-upscale.json)에 있다. 기존 SwinIR 두 장은 합성 기준과
`build_character_mattes.py`의 정확한 마스크 재생성 입력이므로 미사용 파일이 아니다.

기존 캐릭터 alpha와 520×162 문자 격자는 재생성하지 않았다. 두 방향 모두 배경 픽셀과
출력 캐릭터 alpha가 교체 전후 바이트 단위로 같음을 확인했다. 얼굴 전용 생성/보정,
별도 sharpen·색 재매핑은 추가하지 않았고 실행 중 GPU 추론도 없다. 19개 테스트·새 격리
Sway 두 번·밝고 어두운 바탕의 경계·현재 기본 경로 설치/배경 앱 재실행·설치 SHA를 확인했다.
Waybar·그림자·출력 설정은 유지했다. OS 재부팅·재로그인·물리 모니터 재연결은 미수행이다.

캐릭터만 이전 SwinIR로 복원하려면 `scene_assets.json`의 두 RGB 경로를 각각
`assets/wallpaper-landscape-swinir.png`, `assets/wallpaper-portrait-swinir.png`로 바꾸고
위의 stop → install → start 순서로 갱신한다. alpha·격자·정적 fallback은 그대로 사용한다.

## 아이콘

[`templates/icons/Yuru`](templates/icons/Yuru)는 직접 작성한 SVG 39종과 내부 symlink 별칭
26개로 구성한다. 민트 폴더·크림 문서·버건디 세부 표시와 직각 도구 아이콘을 사용한다.
폴더·파일 종류·장치·상태·터미널·파일 관리자·시스템 모니터가 대상이며,
Thunar·Kitty·btop 실행 아이콘에도 같은 도안을 연결했다. 앱 브랜드와 작은 symbolic 버튼은
설치된 Adwaita → AdwaitaLegacy → hicolor에서 이어받는다.
[freedesktop 아이콘 테마 규격](https://specifications.freedesktop.org/icon-theme/latest/)의
상속 구조를 사용하며, 다른 테마의 SVG를 복제하거나 시스템 패키지를 수정하지 않는다.
Rofi와 Dunst의 기존 아이콘 숨김 설정, Waybar의 빨간 마이크 표시는 유지한다.

`theme.py`의 build·install/update가 팔레트를 반영해 `~/.local/share/icons/Yuru/`에 설치한다.
GTK3/4 settings.ini의 `gtk-icon-theme-name=Yuru`, Qt5/6의 `[Appearance] icon_theme=Yuru`도
함께 관리한다. Qt 키는 [qt5ct 원본](https://github.com/desktop-app/qt5ct/blob/master/src/qt5ct-qtplugin/qt5ctplatformtheme.cpp)의
설정 읽기 경로를 따른다. 파일 설치 후 현재 세션의 아이콘 preference만 반영할 때는:

```sh
python activate.py apply --icons-only
```

gsettings의 `org.gnome.desktop.interface icon-theme`을 저장하며 원래 값은 기존 runtime 백업에
추가한다. 이후 새 GTK/Qt 앱과 로그인에서 저장한 설정을 읽는다. 실행 중인 앱이 아이콘을
캐시하면 작업을 저장한 뒤 해당 앱을 정상 재시작한다. 전체 원복은 아래 복원 순서의
`activate.py restore-settings` → `theme.py restore`를 따른다. 원래 icon-theme preference와
설정 파일을 복원하며 새로 설치했던 아이콘 파일도 제거한다.

2026-11-01 검증: `python verify_icons.py`를 두 번 새로 실행해 65개 이름을
16/24/32/48px에서 GTK3로 검색·렌더하고 GTK4의 65개 이름 검색을 확인했다.
현재 디스플레이에 연결한 GTK3/4의 새 probe도 각각 두 번 모두 기본 Yuru 선택과
설치된 폴더 경로를 읽었다. `python verify-qt-routing.py`는 격리 Qt5/6 probe를 각각
두 번 시작해 Yuru 선택·폴더와 상속 아이콘 렌더·기존 Fusion 팔레트와 폰트를 확인한다.
설치·복원 등 기존 32개 테스트와 GTK CSS·Bash·Sway 구문 검증도 통과했다.
사용자의 기존 앱·데스크톱·OS 재시작 및 재로그인은 수행하지 않았다.

[아이콘 미리보기](verification/native-icons.png), [GTK 검색·렌더 결과](verification/icons.json),
[현재 GTK 설정 확인](verification/icons-active.json), [Qt 재실행 결과](verification/icons-qt.json).

마우스 커서는 Adwaita 기본값을 사용한다. 2026-11-04 사용자 요청으로 별도 커서 작업을
롤백해 생성기·도안·검증 자료와 설치 파일 121개를 제거하고, GTK·Sway·로그인/서비스 환경을
복원했다. 나머지 Yuru 테마와 최초 설치 백업은 유지한다. 현재 seat와 새 GTK 프로세스,
새 Bash·서비스 환경 및 시작 파일, 기존 65개 테스트를 확인했다. 실제 OS 재부팅·재로그인은
수행하지 않았다.

## Firefox UI

2026-11-01 북마크 드롭다운 선택 가독성 수정: 폴더 안의 `menu`·`menuitem`도
툴바 버튼과 같은 `.bookmark-item` 클래스를 사용한다. 기존 `#PersonalToolbar .bookmark-item`
hover 규칙의 ID 우선순위가 선택 항목의 민트 배경을 surface로 덮어 먹색 글자만 남겼다.
툴바의 hover·padding/border·키보드 포커스 규칙을 `toolbarbutton.bookmark-item`으로 제한해
하위 메뉴의 기본 간격과 민트/먹색 선택 색쌍을 보존한다. 네이티브 appearance는 변경하지 않는다.

격리 Firefox의 실제 포인터 hover로 수정 전 어두운 글자/어두운 배경을 재현했다.
수정 후 두 번 새 실행에서 북마크 항목·하위 폴더·우클릭 메뉴의 민트 배경/먹색 글자,
비활성 항목의 muted 글자, 앱 메뉴 hover와 주소창 선택 색쌍을 확인했다.
기존 폰트·새 탭·검색 handoff·사이트 본문 검사도 통과했다.
[북마크 메뉴 미리보기](verification/native-firefox-bookmark-menu.png),
[상태별 검증](verification/firefox.json)의 `dropdowns`를 참고한다.
활성 프로필의 관리 CSS만 선택 갱신했으며 기존 import와 journal SHA가 일치한다.
사용자 Firefox 완전 종료 후 정상 시작에 적용된다. 실제 사용자 프로필 재시작·
OS 재부팅·재로그인은 미검증이며 복원은 아래 기존 theme restore 순서를 따른다.

기본 Firefox의 둥근 모양을 색상만 덮던 초기 CSS를 수정했다.
32px 탭 레일과 36px 주소창 줄, 직각 탭·주소창·북마크·메뉴를 사용한다.
선택 탭은 2px 민트 아래 선으로 표시한다. 기본 탭 outline, 탭·북마크 줄의 구분선,
주소창과 내부 아이콘의 평상시 테두리를 제거하고 배경색으로 영역을 구분한다.
주소창 입력 포커스는 회색 면과 민트 커서로 표시한다.
북마크바는 주소창 줄과 같은 `surface` 배경을 사용한다.
추천 목록의 선택은 민트 면을 사용한다. 다른 버튼의 키보드 포커스는 얇은 민트 outline이다.
여러 탭 선택의 outline, 탭 닫기·고정·오디오 표시와 사이트 보안 표시는 그대로 사용한다.

2026-11-01 정리: 기존 CSS는 탭의 `border`만 지워 기본 `outline`이 남았고,
주소창 안 `.urlbar-page-action`은 툴바 버튼 선택자에 포함되지 않아 작은 테두리가 남았다.
기본 `--toolbarbutton-outline`을 끄고 키보드 포커스를 별도 유지한다.
주소창 줄은 기본 컨테이너 여백과 추가 상하 padding이 겹치던 것을 정리했다.
검색 엔진 화살표와 겹쳐 보이던 `a`는 Firefox가 font-size: 0으로 숨기는 내부 보조 문자였다.
공통 14px 글자 크기 지정에서 `.urlbar-visually-hidden`을 제외해 기본 숨김 처리를 유지한다.
격리 프로필의 두 번 시작에서 탭 32px·주소창 줄 36px와 여러 탭 선택 표시,
주소창 입력·추천 목록, 새 탭 검색 handoff와 사이트 본문 스타일 보존을 확인했다.
보조 문자의 0px 크기, 12px 화살표와 엔진 메뉴 열기·닫기, 두 툴바의 동일 배경도 확인했다.
사용자 프로필에는 관리 파일만 갱신하며 다음 정상 시작에 적용된다.
사용 중인 Firefox 재시작·OS 재부팅·재로그인은 수행하지 않았다.

2026-11-01 주소창 돌출 수정: Firefox Nova의 추천 목록은 입력 배경을 상하좌우
8px 확장한다. 36px 툴바에서는 배경 위쪽이 탭 줄을 침범했다(격리 실행에서 y=34 → 26).
`--urlbar-background-overhang-open`을 `:root`에서 0px로 설정해 입력 배경과 추천 목록의
파생 여백을 함께 맞췄다. 입력 자체의 열림 확장 변수도 0px로 고정한다.
주소창 높이·추천 목록의 기본 앵커와 검색 기능은 유지한다.
격리 프로필의 두 번 시작에서 1280×800·909×731 창의 목록 열기 전후 입력 좌표 일치,
배경 위쪽의 툴바 침범 없음과 목록 배경의 좌우 정렬을 확인했고 기존 32개 테스트가 통과했다.
[작은 창의 입력·추천 목록](verification/native-firefox-focus-compact.png)도 일반 실행에서 캡처했다.
활성 프로필의 `chrome/yuru.css`만 선택 갱신하며 import·활성화 flag·설치 SHA를 확인했다.
사용 중인 Firefox는 종료하지 않았으므로 실제 프로필은 완전 종료 후 정상 시작해야 반영된다.
실제 사용자 프로필 재시작·OS 재부팅·재로그인은 미검증이다.

UI 글꼴은 **영문 Ubuntu Mono + 한글 D2Coding 1.4.0 Regular**이다.
기존 고정폭·터미널 느낌을 유지하고 한글은 나눔바른고딕 계열의 D2Coding으로 연결한다.
`install_fonts.py`가 공식 릴리스 ZIP의 고정 SHA256을 검사하고 일반판 Regular/Bold와
`D2Coding-LICENSE.txt`만 `~/.local/share/fonts/yuru/`에 설치한다. 리거처판은 설치하지 않는다.
Ubuntu Mono는 시스템 `ttf-ubuntu-font-family` 패키지를 사용한다. 기존 Sarasa는 다른 앱에서
쓸 수 있으므로 유지한다. 별도 서비스·자동 시작은 필요 없다.

`palette.json`의 `font`는 터미널·코드, 기존 `browser_font` 키는 공통 UI에 사용하며
둘 다 Ubuntu Mono다. `fallback_font`는 D2Coding이다. Firefox·새 탭은 14px,
GTK·Qt 기본 UI는 10.5pt(96dpi에서 14px), 다른 도구는 기존 크기를 유지한다.
CSS에는 글꼴 목록을 명시하고 `~/.config/fontconfig/conf.d/60-yuru-fonts.conf`에도
Ubuntu Mono의 누락 글리프를 D2Coding에서 찾는 규칙을 설치한다. 터미널이 별도로 조회하는
일반 monospace도 Ubuntu Mono → D2Coding 순서다. Qt fixed font·GTK `.monospace`는
Ubuntu Mono를 유지하면서 같은 한글 fallback을 사용한다. 일반 사이트 본문 CSS는 바꾸지 않는다.

폰트 설치 후 기존 `theme.py update --live` 경로로 생성물을 갱신하고
`python activate.py apply --fonts-only`로 현재 세션의 글꼴만 반영한다.
외부 편집 때문에 전체 update가 거부되면 `--only`에 검토한 대상만 지정한다.
이 호스트에서는 기존 Kitty 편집을 보존하며 Firefox CSS 두 개·GTK3/4 설정/CSS·Qt5/6 설정/QSS·
Fontconfig·Code 글꼴 설정·Sway 제목·Waybar·Rofi·Dunst·Fcitx·gtklock·Usage·swaynag 및
설치된 Steam CSS를 선택 갱신했다. ChatGPT는 `python chatgpt_theme.py apply`로
같은 Ubuntu Mono UI/코드 글꼴을 저장하며 시스템 Fontconfig가 한글 fallback을 제공한다.

`--fonts-only`는 gsettings의 font-name·monospace-font-name을 영구 저장하고 Sway 제목 글꼴,
Waybar·Dunst·Fcitx UI를 다시 읽힌다. 배경 명령이나 Kitty reload는 실행하지 않는다.
Firefox는 완전 종료 후 정상 시작, 글꼴을 캐시한 다른 앱도 정상 재시작하면 새 설정을 읽는다.
다음 로그인에도 기존 설정 검색·include 경로와 사용자 Fontconfig로 자동 적용된다.
전체 원복은 기존 ChatGPT restore → runtime preference restore → theme restore 순서를 따른다.
Fontconfig도 journal의 설치 전 상태로 복원한다. UI만 이전 Sarasa로 되돌리려면
`browser_font`를 설치된 `Sarasa Mono K`로 바꾸고 같은 대상만 갱신한 뒤 fonts-only를 실행한다.

검증(2026-11-01): 설치·복원/ChatGPT 테스트, GTK3/4 CSS·Bash·Sway 구문 통과.
현재 디스플레이의 새 GTK3/4 probe 각각 두 번에서 실제 영문 Ubuntu Mono·한글 D2Coding을
확인했다. 14px에서 영문 `i`/`M` 7px·한글 `한` 14px로 기존 1:2 정렬을 유지했다.
격리 Qt5/6 각각 두 번에서 실제 라틴/한글 face·fixed Ubuntu Mono·누락 글리프 없음을,
격리 Firefox 두 번에서 실제 Ubuntu Mono/D2Coding·14px/400을 확인했다.
주소창·메뉴·검색 handoff·일반 사이트 글꼴 보존도 통과했다.
[설치/현재 GTK 결과](verification/fonts.json), [Qt 결과](verification/icons-qt.json)를 참고한다.
사용자 Firefox·ChatGPT 전체 재시작, OS 재부팅·재로그인은 수행하지 않았다.

```sh
python install_fonts.py
doas pacman -S --needed wtype  # 격리 Wayland의 실제 키 입력 검증용
python verify_firefox.py  # build 후 실행, 현재 브라우저와 별도의 임시 프로필 사용
```

[상단 UI 미리보기](verification/native-firefox.png), [메뉴 미리보기](verification/native-firefox-menu.png),
[검증 결과](verification/firefox.json). 모두 개인정보 없는 테스트 프로필의 로컬 문서·샘플 북마크다.
메뉴 검증 캡처의 주소창 사선은 자동화 Firefox의 경고이며 일반 실행 캡처에는 없다.

상단 UI는 `chrome://browser/content/browser.xhtml`의 userChrome CSS로 적용한다.
새 탭은 `about:newtab`·`about:home`만 대상으로 하는 별도 userContent CSS를 사용한다.
바탕화면과 같은 시마린 배경 위 왼쪽에 520×40px 직각 검색창을 두고,
큰 Firefox 로고·피드·위젯·날씨 영역은 숨긴다. 설정 버튼은 민트/먹색 직각 버튼으로 유지한다.
창이 세로로 길면 `wallpapers.json`의 세로 배경을 자동 선택한다.
원래 검색 엔진과 주소창 검색 handoff는 유지한다.

[새 탭 가로 미리보기](verification/native-firefox-newtab.png),
[새 탭 세로 미리보기](verification/native-firefox-newtab-portrait.png).
[주소창 입력·추천 목록 포커스](verification/native-firefox-focus.png)는 실제 키 입력으로 연 테스트 화면이다.
사이트 본문 글꼴과 둥근 버튼이 바뀌지 않는지 별도 검증했다.
알 수 없는 기존 userContent.css가 있으면 자동 설치에서 제외하고, 테마가 만든 import는 다음 업데이트에도 유지한다.
현재 프로필의 파일 설치 후에는 Firefox를 완전히 종료하고 정상 실행해야 새 CSS를 읽는다.
이 작업에서는 사용 중인 브라우저를 종료하지 않았다.
원복은 아래 theme restore 절차를 사용하며, 별도 설치한 폰트 파일은 자동 삭제하지 않는다.
다른 앱에서 사용하지 않으면 위 사용자 폰트 디렉터리의 `D2Coding-Regular.ttf`·`D2Coding-Bold.ttf`·`D2Coding-LICENSE.txt`를 제거하고 `fc-cache -f`로 갱신한다.

Mozilla의 내부 UI 선택자에 의존하므로 Firefox 대규모 갱신 뒤 `verify_firefox.py`로 다시 확인한다.
[Mozilla의 userChrome 설명](https://support.mozilla.org/en-US/kb/contributors-guide-firefox-advanced-customization),
[D2Coding 원본](https://github.com/naver/d2-coding-font).

## Steam

Steam은 자체 Chromium UI라 GTK/Qt 테마를 읽지 않는다.
[Millennium](https://docs.steambrew.app/users/index)의 CSS 테마로 라이브러리·설정·팝업의
먹색 배경, 크림 글자, 민트 선택선, 공통 UI 글꼴, 직각 컨트롤을 적용한다.
Firefox와 같이 툴바·본문·입력 면을 구분하고, 가는 자주빛 경계와 버건디 메뉴 구분선을 사용한다.
검색은 회색 면으로 포커스를 표시하며 드롭다운·주소줄·열린 메뉴도 별도로 테마를 적용한다.
하단은 긴 사각 테두리 없이 하나의 레일과 민트 다운로드 상태를 사용한다.
게임 이미지·카드 배치와 오류·보안·실행 상태의 의미는 유지한다. 상점/커뮤니티에는 별도 CSS로
배경·메뉴·입력창만 적용한다. 임의 외부 사이트는 웹 패치 대상에 포함하지 않는다.
테마에는 JavaScript가 없다. Big Picture·게임 오버레이·친구 채팅 전체는 아직 실렌더 미검증이다.

현재 설치 도구는 단일 데스크톱 사용자가 있는 Arch x86_64의 네이티브 `steam` 패키지용이다.
Flatpak/Snap은 지원하지 않는다.
`base-devel`·`doas`와 한 번 실행한 Steam이 필요하다. 공식 안정판 **3.6.2**의 압축 파일,
라이선스와 pacman hook을 고정 SHA256으로 확인한 뒤 로컬 Arch 패키지를 만들어 설치한다.
해당 버전의 [공식 hook](https://github.com/SteamClientHomebrew/Millennium/blob/v3.6.2/packages/arch/millennium.install)은
Steam의 `ubuntu12_{32,64}/libXtst.so.6`를 `/usr/lib/millennium`의 로더에 연결한다.
일반 Steam 실행에서도 적용되며 `/usr/bin/steam` 수정이나 로그인 자동 실행은 필요 없다.
공식 hook이 다른 사용자도 검사하고 옛 launcher 패치도 복구하므로, 설치 도구는 다른 데스크톱
계정·기존 타 로더·`steam.millennium.bak`·`LD_PRELOAD` launcher가 있으면 먼저 검토하도록 거부한다.

```sh
python install_millennium.py
python install_fonts.py  # 공통 한글 fallback 폰트가 없는 새 호스트에서만
# 이미 Yuru가 설치되어 있는 경우 Steam 파일 세 개만 추가/갱신한다.
python theme.py update --live \
  --only .local/share/Steam/millennium/themes/yuru/skin.json \
  --only .local/share/Steam/millennium/themes/yuru/client.css \
  --only .local/share/Steam/millennium/themes/yuru/web.css
```

처음 Yuru 전체를 설치할 때는 기존 `theme.py install`이 위 파일도 포함한다.
Steam을 완전히 종료·재실행한 뒤 Steam → Millennium → Themes에서 **Yuru**를 선택한다.
선택은 `~/.config/millennium/config.json`의 `themes.activeTheme="yuru"`에 저장되고
`general.injectCSS=true`여야 한다. 이 가변 설정은 `theme.py`의 파일 SHA 관리에 포함하지 않는다.
색·폰트 원본은 기존 `palette.json`이고, CSS 원본은 `templates/steam/`이다.
갱신 후에는 Steam을 정상 재실행한다. 설치 도구는 고정판 복원용이므로 기존의 더 새 버전을
그대로 유지하려는 경우 다시 실행하지 않는다. 프레임워크 업그레이드는 UI 호환성을 확인하며 진행한다.

원복은 Millennium에서 **Default**를 선택한 뒤 기존 theme restore 절차를 따른다.
프레임워크까지 제거하려면 Steam을 완전히 종료하고 `doas pacman -R millennium-bin`을 실행한다.
pacman hook이 두 로더 링크를 제거하며, 다음 Steam 실행은 기본 클라이언트를 사용한다.
Steam 계정·게임·대화 디렉터리는 복사하거나 제거하지 않는다.

디자인·구조 점검(2026-11-01): 로컬 Firefox 테마, [Adwaita 헤더 구현](https://github.com/tkashkin/Adwaita-for-Steam/blob/master/adwaita/css/main/headerbar/navigation.css),
[SpaceTheme의 헤더·진행 표시](https://github.com/SpaceTheme/Steam/tree/main/src/css/steam)와
[Mozilla의 간격 토큰 지침](https://firefox-source-docs.mozilla.org/code-quality/lint/linters/stylelint-plugin-mozilla/rules/use-design-tokens/space.html)을 대조했다.
기존안은 32px 탭의 글자가 위에 붙고 아래에만 7px이 남았고, wrapper의 색과 실제 채움 색을 혼동했다.
이후 CSS를 컴포넌트 단위로 통합했다. 제목줄과 탭줄은 한 면을 사용하고, 48px 행 안의 32px 탭을
상하 8px로 배치하며 글자·별도 선택선을 수직 정렬한다. 빈 주소줄 placeholder는 높이를 없앴다.
실제 주소줄은 40px 행 안의 32px 전체 폭 필드와 하단 경계 하나를 사용한다.

검색의 실제 DialogInput은 flex wrapper 안에 있어 border-box·최소 폭을 함께 지정한다.
고정 카드 안의 자동 생성 커버·웹 본문은 네이티브 글꼴 metrics를 유지하고 컨트롤만 palette의 공통 UI 글꼴을 사용한다.
메뉴는 실제 popup 자식의 강한 native 규칙과 키보드 focus·disabled·삭제 상태까지 다룬다.
업데이트 상태 문구 wrapper는 투명하고, 3px 트랙의 색 변수만 바꿔 native `--percent`와 `::after`
채움·애니메이션을 유지한다. 빈 다운로드 hero의 파란 placeholder·multiply tint를 제거한다.
상점은 legacy CSS 외에 현재 v7 navigation의 별도 그라데이션과 검색 구조도 대상으로 한다.

사용 중인 Steam을 조작하지 않는 컴포넌트 일괄 검증:

```sh
python theme.py build
node verify_steam.mjs
```

설치된 Steam의 `library.css`·`sp.css`와 생성 CSS를 별도 프로필의 headless Chrome에 함께 로드한다.
777/1280/1600px에서 탭의 상하 여백·글자 중앙 정렬, 주소 길이와 무관한 필드 폭, 검색 입력 크기,
키보드 focus·hover·disabled, 진행률 0/34/75/100%의 실제 pseudo-element 폭과 문구 영역을 검사한다.
짧은/긴 메뉴의 내용 폭·선택 배경과 무관하게 외곽선이 유지되는지, 설치/실행/비활성 액션의 의미 색도 포함한다.
인라인 메뉴는 실제 border를 사용한다. 별도 CEF 팝업 창은 내용 기반 창 크기 계산에서 layout border의
오른쪽이 잘리는 것을 실제 일반 Steam에서 확인해, 창 크기에 영향을 주지 않는 viewport paint layer로
외곽선을 그린다. 항목 배경이 그 선을 덮거나 글자 길이가 외곽선을 밀어낼 수 없게 한다.
2026-11-01: 이 레이아웃·상태 검사 **150개**, 설치·복원·Usage·ChatGPT 테스트 **34개** 통과.
계정이 없는 fixture·[레이아웃 검증](verification/steam-layout.json)·[컴포넌트 화면](verification/steam-layout.png)은
실제 Steam 재시작 검증과 구분한다. [실제 앱 검증·남은 범위](verification/steam.json).
Steam 대규모 업데이트 후에는 내부 CSS module 이름과 실제 화면도 다시 확인한다.
OS 재부팅·재로그인·게임 실행 검증은 미수행이다.

## Discord

현재 Kitty와 같은 고정폭 글꼴·80% 불투명도·SwayFX blur를 쓰는 BetterDiscord 테마다.
프사·서버 이미지·역할색·답장·리액션을 유지하며 메뉴와 설정은 읽기 쉬운 불투명 면을 쓴다.
설치·종료 후 갱신·복원, Nitro/유료 기능별 처리 경계와 **실제 검증/미검증 범위**는
[Discord 테마 안내](docs/discord.md)에서 관리한다.

## Chrome과 추가 앱

Chrome은 [공식 네이티브 테마 형식](https://developer.chrome.com/docs/extensions/develop/ui/themes)을 사용한다.
JavaScript·웹사이트 접근 권한이 없는 색상/배경 전용 테마이며, 파일은 theme install/update에서
`~/.local/share/yuru-theme/chrome/`에 설치한다. 브라우저 UI 글꼴·모서리와 일반 웹사이트는 변경하지 않는다.
새 탭은 가로 PNG 한 장을 사용하며 Firefox처럼 세로 배경을 자동 선택하지 않는다.

최초 선택은 Chrome의 `chrome://extensions` → 개발자 모드 → **압축해제된 확장 프로그램을 로드합니다**에서
위 디렉터리를 선택한다. 이는 [Chrome의 공식 개발용 설치 경로](https://developer.chrome.com/docs/extensions/get-started/tutorial/hello-world#load-unpacked)다.
`build/` 대신 설치된 고정 경로를 사용해야 재생성 때 경로가 없어지지 않는다.
팔레트 갱신 뒤에는 같은 Load unpacked 절차로 설치 디렉터리를 다시 선택한다.
복원할 때는 먼저 Chrome 설정 → 모양 → 기본값으로 재설정을 사용한 뒤 theme restore를 실행한다.
Chrome이 테마를 캐시하므로 파일 삭제만으로 선택 해제가 끝났다고 판단하지 않는다.
Chrome 156의 격리 프로필에서 네이티브 패키징은 통과했지만, 사용자 프로필에서 선택·실렌더·재실행은 미검증이다.

ChatGPT 데스크톱 앱은 [공식 Appearance 설정](https://learn.chatgpt.com/docs/app/settings)을 사용한다.
`chatgpt_theme.py`는 앱 번들을 패치하지 않고 네이티브 설정 키만 저장하며,
기존 설정과 사용자 변경을 보존하는 적용·복원 절차를 제공한다.
적용은 `python chatgpt_theme.py apply`, 복원은 `python chatgpt_theme.py restore`다.
색은 `templates/chatgpt/theme.json`에서 팔레트 토큰으로 관리한다.
도구는 설치된 `codex app-server`의 버전 검사와 `config/batchWrite`로
`~/.codex/config.toml`의 `desktop.appearanceTheme`·`desktop.appearanceDarkChromeTheme`만 변경한다.
두 키의 원래 값은 `~/.local/state/yuru-theme/chatgpt-before.json`에 0600으로 보관하고,
사용자가 나중에 변경한 테마는 자동 덮어쓰기·복원을 거부한다. 계정·대화·전체 설정은 백업하지 않는다.
UI를 다시 읽기 전에는 실행 중 화면 반영이 끝났다고 판단하지 않는다.

Discord의 [공식 커스텀 색상 테마](https://support.discord.com/hc/en-us/articles/207260127-How-to-Change-Discord-Color-Themes-and-Customize-Appearance-Settings)는
Nitro가 필요하며 글꼴·직각 모서리까지 임의 CSS로 바꾸는 기능은 아니다.
이 작업에서 별도 클라이언트 수정 도구를 설치하거나 구독을 변경하지 않는다.

GPU Screen Recorder UI 1.14.1은 자체 렌더러이며 `main.tint_color`가 Red/Green/Blue 세 가지뿐이다.
HEX 값을 넣어도 Yuru 색이 되지 않는다. 글꼴은 기존 GNOME font-name을 읽지만,
배경·선택·텍스트 색 전체 적용에는 [소스](https://git.dec05eba.com/gpu-screen-recorder-ui/) 패치와 업데이트 때 재빌드가 필요하다.
현재 패키지·녹화 데몬은 유지한다.

## cava

`cava`를 실행하면 btop과 같은 단색 민트(`#88D4CC`) 막대를 표시한다.
2칸 막대·1칸 간격, 자동 폭·스테레오·60fps이며 10초 무음이면 절전한다.
`noise_reduction=35`로 기본값 77보다 낙하 지연과 잔상을 줄였다.
2026-11-01 동일한 1kHz 신호를 끊는 FIFO 비교에서 10% 높이까지 약 0.55초 → 0.34초로
단축됨을 확인했고, 저장한 기본 config로 두 번 새로 실행·정상 종료했다.
원래 감쇠로 되돌리려면 템플릿 값을 77로 바꾸고 아래 선택 갱신 후 `r` 또는 재실행한다.
이 조정에서 OS 재부팅·재로그인·장치 재연결은 수행하지 않았다.
배경은 터미널 기본값을 사용해 Kitty의 Yuru 배경·불투명도·blur를 그대로 따른다.
별도 글꼴 지정은 필요 없으며 실행한 터미널의 Ubuntu Mono를 사용한다.

원본은 `templates/cava/config`, 색은 `palette.json`이다. `theme.py`가
`~/.config/cava/config`에 설치하고 기존 config는 로컬 설치 기록에 백업한다.
[공식 설정](https://github.com/karlstav/cava/blob/master/example_files/config)의
PipeWire `source=auto`로 기본 출력의 monitor를 사용하며 장치 이름을 고정하지 않는다.
마이크를 시각화하지 않으며 로그인 자동 실행·별도 서비스는 추가하지 않는다.

```sh
python theme.py update --live --only .config/cava/config
cava
```

새 실행마다 저장한 설정을 읽는다. 실행 중이면 `r`로 다시 읽거나 `q`로 종료한 뒤
다시 실행한다. 전체 테마 원복은 아래 복원 절차를 따르며 cava의 설치 전 config도 복구한다.
패키지 자체는 제거하지 않는다.

2026-11-01: 기본 경로로 실제 cava 1.0.0을 두 번 새로 시작해 민트 truecolor 출력,
터미널 배경 보존, 실제 재생 소리에 반응하는 막대와 PipeWire 기본 출력 monitor의
active 연결, `q` 정상 종료를 확인했다. 별도 Sway/Kitty의
[화면](verification/native-cava.png)은 가독성을 위해 배경 불투명도를 1로 캡처했다.
[검증 기록](verification/cava.json). 설정 저장과 앱 재실행은 확인했으나
OS 재부팅·재로그인·오디오 장치 재연결·실행 중 기본 출력 전환은 검증하지 않았다.

## Waybar 트레이

Yuru 초기 표시 목록에서 빠졌던 트레이를 한도 표시 왼쪽에 복원했다.
회색 `<`를 클릭하면 아이콘이 왼쪽으로 펼쳐지고 손잡이는 민트 `>`로 바뀐다.
`>`를 다시 클릭하면 접힌다. 커서를 옮겨도 열림 상태와 시계·한도 표시의 위치는 유지한다. 아이콘은 원래 색상과
16px 크기·8px 간격을 사용하고 우클릭 메뉴는 먹색·크림·민트와 직각 경계를 따른다.
입력 대기·연타 방지 시간은 없으며 펼침 애니메이션도 0ms다.

원본은 `templates/waybar/config.jsonc`의 `group/tray-drawer`·`group/tray-handle`·`custom/tray`·`custom/tray-open`·`tray`와
`templates/waybar/style.css`다. Waybar 기본 drawer를 사용해 별도 트레이 앱·서비스는 없다.
화살표는 주변 한도·시계와 같은 Ubuntu Mono 12px의 실제 `<`·`>` 문자다.
중앙 배치 SVG 대신 글꼴의 기준선을 사용하며, drawer의 실제 열림 상태에 따라 CSS로
두 문자 중 하나만 폭을 갖도록 한다. 별도 토글 스크립트나 상태 파일은 없다.
적용은 아래 **btop과 AI 사용량**의 Waybar 선택 갱신·재읽기 명령을 따른다.
SVG 손잡이로 복원하려면 이 작업의 config/CSS·SVG 템플릿·theme.py 설치 목록 변경을
함께 되돌려 build 후 이전 네 파일 선택 갱신 명령으로 적용한다.
테마 전체 복원은 아래 **복원**을 따른다.
트레이만 숨기려면 템플릿의 `modules-right`에서 `group/tray-drawer`를 제거하고 같은 명령으로 갱신한다.
기존 Sway의 `swaybar_command waybar`가 다음 로그인에도 저장된 설정을 읽는다.

Waybar 0.15.0의 drawer는 GTK가 추가로 보내는 더블·트리플클릭 이벤트까지 토글해
빠른 두 번째 클릭에서 상태가 어긋났다. 애니메이션을 0ms로 꺼도 재현했다.
[`patches/waybar-clicks.patch`](patches/waybar-clicks.patch)는 실제 `GDK_BUTTON_PRESS`만
처리하도록 조건 하나를 고친다. [`install_waybar.py`](install_waybar.py)는 공식 0.15.0 소스의
SHA256을 확인하고 기존 Arch 패키지와 같은 런타임 기능으로 사용자 영역에 빌드한다.

```sh
# 시스템 Waybar와 런타임 의존성이 설치된 Arch에서 소스 빌드 도구 준비
doas pacman -S --needed base-devel meson ninja glib2-devel wayland-protocols cmake
python install_waybar.py
```

실행 파일은 `~/.local/lib/yuru-waybar/0.15.0-yuru-clicks1/waybar`, 기본 명령은
`~/.local/bin/waybar` symlink다. 기존 로그인 PATH의 `~/.local/bin` 우선순위로 일반 실행과
Sway 자동 시작에 동일하게 적용한다. 설치 기록은 실행 파일·라이선스·패치 SHA를 보관한다.
이번 호스트에서는 누락된 빌드 도구만 임시 디렉터리에 풀어 빌드했고 시스템 패키지를 교체하지 않았다.
다른 기본 Waybar 파일이나 설치 후 편집된 파일은 설치·제거 도구가 덮어쓰지 않는다.
원복은 `python install_waybar.py --remove`와 셸의 `hash -r` 후 Waybar를 새로 실행한다.
다음 실행은 `/usr/bin/waybar`를 사용한다. 이 사용자 실행 파일은 theme.py의 전체 테마 복원과 별도로 제거한다.
시스템 Waybar를 갱신한 뒤에는 해당 이벤트 수정의 포함 여부를 확인해 사용자 override 유지 여부를 결정한다.

2026-11-01: 격리 D-Bus·headless Sway에서 Waybar 0.15.0을 두 번 새로 실행해
클릭으로 왼쪽 펼침·재클릭으로 접힘, `<`/`>` 전환과 커서 이동 후 열림 유지,
우측 표시의 픽셀 위치 유지·아이콘으로 이동한 뒤 우클릭 메뉴 선택을 확인했다.
설치된 수정본에서 8회 연속 클릭과 2·3·8·9·20회 빠른 입력 묶음의 홀짝 상태가 모두 일치했고,
수정 전 시스템 실행 파일에서는 두 번째 빠른 클릭의 상태 불일치를 재현했다.
현재 세션에서도 Waybar를 실제 종료·새 실행해 기본 설치 경로 로드, 두 출력의 26px 높이와
Discord·Steam·Fcitx5 등 트레이 항목 등록을 확인했다. 설치 SHA와 자동 시작 구조를 확인했으며
OS 재부팅·재로그인·모니터 재연결은 수행하지 않았다.
[접힘](verification/waybar-tray-collapsed.png) · [펼침](verification/waybar-tray-expanded.png) ·
[메뉴](verification/waybar-tray-menu.png)는 샘플 한도·아이콘을 사용한 격리 화면이다.
[검증 기록](verification/waybar-tray.json).

2026-11-01 문자 손잡이 검증: 격리 Waybar를 두 번 새로 실행해 문자 렌더·방향 전환,
연속 클릭·메뉴·오른쪽 내용 위치 보존을 확인했다. 실제 세션도 기본 설정으로 재시작해
두 출력에 적용했다. 설정 저장·기존 자동 시작 경로는 확인했으며 OS 재부팅·재로그인은 미수행이다.
[접힘](verification/waybar-tray-mono-collapsed.png) · [펼침](verification/waybar-tray-mono-expanded.png) ·
[검증 기록](verification/waybar-tray-mono.json).

### 플로팅 배치

하단의 밝은 ASCII 무늬·캐릭터가 불투명 Waybar에서 잘리는 경계를 줄이기 위해,
2026-11-01 선택한 플로팅 컨셉을 기본 배치에 적용했다. 높이 26px·직각·불투명 색과
모듈 배치는 유지하고 좌우 24px·아래 12px를 띄운다. 배경이 바 아래와 양옆으로 이어지며
배경 페이드나 반투명 처리는 추가하지 않았다. `templates/waybar/config.jsonc`의
`margin-left`, `margin-right`, `margin-bottom`이 저장된 원본이다. 기본 exclusive zone은
바와 아래 여백을 합친 38px를 예약해 앱 창과 겹치지 않는다.

변경·복원은 위 여백 값을 수정하거나 세 키를 제거한 뒤 아래 Waybar 선택 갱신·재읽기
명령을 사용한다. 최초 설치 전 전체 설정 복원은 기존 `theme.py restore` 절차를 따른다.
기존 `swaybar_command waybar` 시작 경로가 같은 설정을 읽으므로 별도 실행기를 추가하지 않는다.

검증(2026-11-01): 격리 D-Bus·Sway의 가로/세로 두 출력에서 Waybar를 두 번 새로
실행해 픽셀 차이 범위가 좌우 24px·아래 12px·높이 26px와 일치하고, 아래 여백이 원래
배경과 동일함을 확인했다. 앱의 작업 영역은 38px를 예약했다. 현재 세션도 Waybar를
종료·새 실행해 기본 config/CSS, 가로 3392px·세로 1392px 폭과 26px 높이, 설치 SHA를
확인했다. 배경 프로세스와 출력 설정은 유지했다. OS 재부팅·재로그인·물리 모니터
재연결은 미수행이다. [가로](verification/waybar-floating-landscape.png) ·
[세로](verification/waybar-floating-portrait.png)는 샘플 한도를 사용한 격리 실제 화면이며,
[검증 기록](verification/waybar-floating.json)에 실제 수행 범위를 저장했다.

2026-11-01 후속 그림자: [SwayFX의 layer 효과](https://github.com/wlrfx/swayfx#new-configuration-options)로
Waybar에만 반경 8px·검정 alpha `55`(약 33%)·아래 2px 그림자를 추가했다. GTK 창 밖에서
잘릴 수 있는 CSS 그림자 대신 컴포지터가 바깥쪽에 그린다. 원본은 `templates/sway/effects.conf`,
설치본은 `~/.local/share/yuru-theme/effects.conf`이며 기존 SwayFX include가 다음 세션에도
읽는다. 일반 창·ASCII 배경의 그림자는 꺼진 상태를 유지한다. 현재 세션에 선택 적용하려면:

```sh
python theme.py update --live --only .local/share/yuru-theme/effects.conf
swaymsg shadow_blur_radius 8
swaymsg shadow_color '#00000055'
swaymsg shadow_offset 0 2
swaymsg 'layer_effects "waybar" shadows enable'
pkill -USR2 -x waybar
```

그림자 색·반경은 layer 생성 시 반영되므로 Waybar도 재생성한다. 그림자만 복원하려면
템플릿의 마지막 명령을 `shadows disable`로 바꿔 선택 갱신하고 같은 disable 명령을 IPC로 적용한다.
실제 설치된 SwayFX·Waybar의 격리 두 출력에서 바를 두 번 새 실행해 그림자 on/off 픽셀을
비교했고, 바 내용·26px 높이·24/12px 여백 보존과 아래 그림자가 화면 끝 전에 사라짐을 확인했다.
현재 세션도 효과 파일 SHA·SwayFX 설정 검증·Waybar 프로세스 재실행 후 두 출력의 실제 layer
그림자 상태를 확인했다. [하단 가로](verification/waybar-shadow-landscape-detail.png) ·
[하단 세로](verification/waybar-shadow-portrait-detail.png) · [검증 기록](verification/waybar-shadow.json).
OS 재부팅·재로그인·물리 모니터 재연결은 미수행이다.

2026-11-01 창 겹침: Waybar의 `layer`를 `top`에서 `bottom`으로 바꿨다.
[layer-shell의 순서](https://github.com/swaywm/wlr-protocols/blob/master/unstable/wlr-layer-shell-unstable-v1.xml)에 따라
floating 창이 바 위를 덮으며, 타일 창은 기존 exclusive zone 38px를 계속 피한다.
ASCII 배경도 bottom에 두면 시작 순서에 따라 바를 가리므로 `ascii_wallpaper.py`는
background를 사용한다. SwayFX의 기존 2초 간격 출력 조회에서 fallback `swaybg`가
ASCII 앞에 생긴 경우에만 ASCII surface를 다시 만들어 위로 올린다. 정적 배경 재실행·
출력 재생성에도 바는 별도 레이어에 남고, ASCII 종료 시 기존 정적 배경이 드러난다.
기존 Waybar 시작 경로와 `95-yuru-ascii.conf` 자동 시작을 그대로 사용한다.

```sh
python theme.py update --live --only .config/waybar/config.jsonc
python wallpaper_control.py install
yuru-wallpaper stop
yuru-wallpaper start
pkill -USR2 -x waybar
```

바를 다시 창 위로 올리려면 템플릿의 `layer`를 `top`으로 바꾸고 위 선택 갱신과
Waybar 재읽기를 실행한다. ASCII의 background 배치는 유지해도 된다. ASCII 자체의
전체 제거·정적 배경 복원은 기존 `yuru-wallpaper restore` 절차를 따른다.

검증(2026-11-01): 격리 SwayFX의 가로·세로 출력에서 Waybar/ASCII를 시작 순서를
바꿔 두 번 실행했다. 실제 픽셀로 floating 창의 바 가림·타일 창의 38px 예약·바 표시와
그림자를 확인했고, 정적 배경 재실행 후 ASCII 복구와 가상 출력 disable/enable 후
바 표시도 확인했다. 기존 테마·ASCII·설치/복원 테스트 48개가 통과했다.
별도 stock Sway 실행에서도 ASCII 입력 통과·포커스·전체화면 중 애니메이션 정지/재개·
크기 변경·가상 출력 재연결 회귀 검사를 통과했다.
현재 세션은 ASCII 프로세스 재시작과 Waybar SIGUSR2 surface 재생성 후 두 출력의
실제 레이어·바 크기·그림자·출력 설정 보존을 IPC로 확인했다.
[검증 기록](verification/waybar-layer.json). 설정 저장과 기존 자동 시작 구조는 확인했으며
실제 OS 재부팅·재로그인·물리 모니터 재연결은 수행하지 않았다.

## Waybar 서비스

트레이 `<` 옆에 `+` 손잡이를 둔다. `+`를 누르면 서비스 이름이 왼쪽으로 나오고 손잡이는 민트 `-`가 된다. `-`를 다시 누르면 접힌다. 시계와 한도 표시의 자리는 그대로다. 이름은 켬/끔 버튼이다. 민트 칸은 실제로 접속되는 상태, 흐린 글자는 꺼진 상태, 분홍 글자는 일부만 올라왔거나 확인에 실패한 상태다. 창은 뜨지 않는다. 이름 위에 커서를 올리면 Codex·Grok 한도처럼 툴팁이 뜬다. 꺼져 있으면 첫 줄이 `꺼짐`이고 이어서 `detail`의 접속 위치가 나온다. 민트일 때는 `켜짐` 다음에 통과한 소켓·앱·업스트림이 나온다. 분홍일 때는 첫 줄이 깨진 단계이고, 이어서 소켓, 앱 유닛, 업스트림 포트가 각각 어떤 상태인지 나온다.

버튼 목록은 `templates/waybar/services.json` 하나다. 빌드가 이 목록으로 Waybar 모듈을 만든다. 서비스를 더하려면 그 파일에 항목을 추가하고 아래 선택 갱신과 Waybar 재읽기를 실행한다. CSS와 손잡이는 그대로다.

`socket` 항목은 사용자 systemd 소켓을 켜고 끈다. `app`은 그 소켓 뒤에서 실제로 듣는 유닛이고, `upstream`은 그 유닛의 IPv4 `host:port`다. 켤 때는 앱을 먼저 시작하고 이어서 소켓을 시작한다. 끌 때는 `stop`에 적힌 유닛을 멈추고, enable 상태는 바꾸지 않는다. 민트는 소켓이 켜져 있고, 앱이 있으면 앱도 켜져 있고, 업스트림이 있으면 그 포트가 듣고 있을 때다. 소켓만 켜져 앱이 죽어 있으면 분홍이다. 이때 누르면 끄지 않고 빠져 있는 쪽을 다시 시작한다. 상태 조회는 포트를 직접 접속하지 않고 커널의 listen 표만 본다. `forge`의 앱은 `stable-diffusion.service`, 업스트림은 `100.68.74.109:7861`이다. `chat`의 앱은 Open WebUI인 `electric.service`, 업스트림은 `100.68.74.109:3000`이다. 두 앱은 로그인 때 켜지 않는다. 소켓이 로그인 때 다시 열리는 것은 기존 enable 설정 그대로다. 그래서 로그인 직후 소켓만 살아 있으면 버튼은 분홍이고, 툴팁은 앱이 꺼져 있으며 업스트림이 연결을 거부한다고 말한다. `forge.local`과 `chat.local`은 이 소켓으로 들어온 연결을 업스트림으로 넘긴다. 업스트림이 거부하면 페이지는 Bad Gateway다. `electric.service`는 기존 설정으로 Forge 앱도 함께 끌어올린다. Forge 소켓까지 켜지지 않았으면 forge 버튼은 분홍으로 남고, 툴팁은 소켓이 꺼져 있다고 말한다. `command` 항목은 `status`가 `on` 또는 `off` 한 줄을 출력하는 명령을 호출한다. `ppwork`는 `ppwork on`, `ppwork off`, `ppwork status`다.

실행 파일은 `~/.config/waybar/scripts/service-toggle.py`, 목록 사본은 `~/.config/waybar/services.json`이다. 상태 조회는 30초마다 한다. 버튼을 누른 뒤에는 그 주기를 기다리지 않고 바로 다시 읽는다. 앱이 방금 켜져 포트가 아직 없으면 분홍과 `아직 연결 안 됨`으로 있다가, 다음 조회에서 포트가 들으면 민트로 바뀐다.

## btop과 AI 사용량

Rofi에서 **btop (Yuru)**와 **Usage**로 실행한다. 터미널 명령은 `btop`, `yuru-usage`다.
두 창은 필요한 때 열어 타일로 배치한다. Waybar에는 Codex·Grok 남은 한도를 상시 표시한다.

Waybar 모듈은 기존 `sway-desktop/config/waybar/scripts/`를 사용하며 60초마다 갱신한다.
Codex는 로컬 세션의 마지막 한도 기록을 읽고, Grok은 주간 한도를 조회해 3분 캐시한다.
Grok proxy가 사용 비율을 생략하면 설치된 `~/.local/share/yuru-theme/usage.py`의 CodexBar 수집기를
재사용한다. 생략된 비율을 임의로 0으로 계산하지 않으며, 조회 실패는 `?`로 표시한다.
툴팁에는 초기화 시각만 표시한다. Codex 한도가 여럿이면 한도별로 한 줄씩 표시하며,
조회할 수 없으면 `초기화 시각 확인 불가`로 표시한다. 모델 요청은 보내지 않는다.
복원 시 base desktop의 scripts와 아래 CodexBar CLI·Usage 설치를 먼저 준비한다.

Waybar 구성 변경은 템플릿에서 수정한 뒤 다음처럼 선택 갱신한다.

```bash
python theme.py update --live --only .config/waybar/config.jsonc --only .config/waybar/style.css
pkill -USR2 -x waybar
```

사용량을 숨기려면 템플릿의 `modules-right`에서 `custom/codex`·`custom/grok`를 제거하고 같은 명령으로 갱신한다.
2026-11-01 두 실제 provider 조회와 Waybar 프로세스 재실행 후 표시를 확인했다.
fallback 회귀 5개와 공용 Usage 검증 7개가 통과했고 GTK3 CSS를 파싱했다.
Sway의 기존 Waybar 시작 경로와 설치 기록 SHA를 확인했으며 OS 재부팅·재로그인은 수행하지 않았다.

btop 1.4.7의 GPU 지원 빌드에서 NVIDIA GPU·VRAM을 확인했다.
`save_config_on_exit=false`이므로 옵션 화면의 변경은 종료 후 저장되지 않는다.
지속적으로 바꿀 옵션은 `templates/btop/btop.conf`를 수정하고 theme update로 반영한다.

Usage는 upstream CodexBar CLI 0.82.0의 수집·인증 기능을 재사용한다.
화면은 Yuru에 맞춰 따로 만들었다. 남은 비율·초기화까지의 시간·마지막 갱신 시각을 표시한다.
`r`은 새로고침, `q`는 종료다. 닫으면 수집을 멈추고 자신이 시작한 child process를 정리한다.

두 provider는 각각 최대 40초의 요청을 5분마다 갱신한다.
응답에 없는 한도는 만들지 않으며, 조회 실패 시 이전 값과 `stale` 표시를 유지한다.
현재 확인한 응답은 두 서비스 모두 주간 한도였고 Codex 단기 한도는 없었다.
인증은 기존 provider 로그인 저장소를 사용한다. 자체 로그인·브라우저 쿠키 가져오기·사용량 파일 저장은 하지 않는다.

CLI와 resource bundle은 `~/.local/lib/codexbar-cli/0.82.0/`, 실행 symlink는 `~/.local/bin/codexbar`다.
공식 CLI 제거가 필요하면 Usage를 닫은 뒤 이 symlink와 버전 디렉터리를 제거한다.
provider 로그인 파일은 제거 대상이 아니다.

[Usage 화면 — 샘플 수치](verification/native-usage.png).
실제 계정의 사용량 조회 성공은 화면 샘플과 별도로 확인했으며 원본 응답은 공개하지 않는다.
[CodexBar CLI 문서](https://github.com/steipete/CodexBar/blob/v0.82.0/docs/cli.md),
[btop 원본](https://github.com/aristocratos/btop).

## 생성·설치·현재 세션 적용

기본 세션의 패키지·설치는 [Sway desktop 안내](../sway-desktop/README.md)를 따른다.
아래는 이미 구성된 Arch 세션에서 rice를 생성·검토하는 순서다.

```sh
cd ~/dotfiles/yuru
doas pacman -S --needed qt5ct qt6ct btop gtk3 python-gobject kitty
python install_codexbar.py
python install_fonts.py
python theme.py build
python theme.py plan
python -m unittest -v test_theme.py test_usage.py test_chatgpt_theme.py
python verify_native.py --rofi
```

`build`와 `plan`은 활성 설정을 바꾸지 않는다. 새 설치는 `install`, 설치 후 변경은 `update`다.
보통 Sway를 종료한 상태에서 실행한다. 현재 세션에 의도적으로 반영할 때만 `--live`를 붙인다.

```sh
# 최초 설치와 기존 설치 갱신 중 하나를 선택
python theme.py install --live
# python theme.py update --live
python activate.py apply
python chatgpt_theme.py apply  # ChatGPT 데스크톱 앱도 맞출 때
```

파일 설치와 runtime 적용은 별도다. `activate.py`는 Sway의 시각 명령과 앱별 reload를 수행한다.
전체 Sway config를 재로드하거나 Firefox를 종료하지 않는다.

다른 설정을 함께 재적용하지 않고 한 관리 파일만 갱신할 때는 `--only`를 사용한다.
기존 백업·설치 기록·선택 파일의 변경 감지는 유지한다. 예:

```sh
python theme.py update --live --only .config/gtk-3.0/yuru.css
```

| 항목 | 새 설정을 읽는 시점 |
| --- | --- |
| Sway 색·배경 | `activate.py apply`의 개별 IPC. 다음 세션에는 저장된 include에서 로드. |
| Kitty·Waybar·Dunst | activation의 앱별 reload. |
| Fcitx 후보창·한/영 상태 표시 | activation에서 core `ReloadConfig` 후 `ReloadAddonConfig classicui`. 다음 실행에는 저장된 `classicui.conf`의 Yuru 선택을 읽음. |
| Bash | 새 interactive shell. |
| GTK 앱·Usage·btop | 해당 앱을 다시 실행할 때. |
| Qt 앱 | Qt 환경 키를 받은 새 프로세스. 로그인 환경·start-sway·Bash·launcher 경로에 연결됨. |
| Firefox UI | Firefox를 완전히 종료한 뒤 정상 시작할 때. |
| Firefox 파일 선택창 | GTK portal backend가 새로 시작할 때. Firefox UI와 별개다. |

Hangul 키의 `en/한` 팝업도 Fcitx classicui 테마를 사용한다. core `ReloadConfig`만
호출하면 디스크의 `Theme=yuru`와 달리 실행 중 UI가 기본 테마에 남을 수 있어 addon도
다시 읽는다. 입력기 표시만 반영하려면 다음 명령을 사용한다:

```sh
gdbus call --session --dest org.fcitx.Fcitx5 --object-path /controller \
  --method org.fcitx.Fcitx.Controller1.ReloadAddonConfig classicui
```

2026-11-01 현재 세션에서 core reload 후에도 기본 테마가 유지되는 것을 재현하고,
addon reload 후 Yuru·Ubuntu Mono 12로 바뀐 것을 확인했다. 별도 Wayland·D-Bus 환경에서
Fcitx와 GTK 입력창을 두 번 새로 실행해 `한`과 `en`의 먹색·크림·버건디 경계 및 한/영 전환을
확인했다. 실제 사용자 입력기 재시작·OS 재부팅·재로그인은 수행하지 않았다.
[검증 기록](verification/fcitx-status.json).

파일 선택창만 예전 Adwaita 모습이면 선택 작업을 마치고 창을 닫은 뒤 실행한다:

```sh
systemctl --user restart xdg-desktop-portal-gtk.service
```

이 명령은 열려 있는 파일 선택창을 닫을 수 있다. 다음 파일 선택창에서 새 GTK CSS를 읽는다.

Thunar 메뉴바의 오른쪽만 회색이던 문제는 `menubar` 배경 규칙이 빠진 탓이었다.
메뉴 항목은 Yuru 색으로 칠해져도 부모 메뉴바의 남은 폭은 비활성 상태에서 Adwaita 색을 사용했다.
GTK3 메뉴바 전체의 배경·배경 이미지를 명시해 활성/비활성 모두 `#2A222B`로 맞췄다.
[수정한 Thunar 상단](verification/native-thunar.png), [활성/비활성 검증](verification/gtk3-menubar.json).
이미 실행 중인 Thunar는 이전 CSS를 유지하므로 파일 작업을 마친 뒤 완전히 재시작한다:

```sh
thunar --quit
thunar
```

이번 수정에서는 사용자의 기존 Thunar 창을 닫지 않았고, 격리 환경의 새 프로세스로 재실행을 검증했다.

Remmina의 빠른 연결 영역에 남던 밝은 띠는 `GtkSearchBar` 내부
`searchbar > revealer > box`의 Adwaita 배경이었다. GTK3 공통 CSS에 해당 노드의
배경·글자·경계를 지정하고 목록/열 헤더 경계도 `window_border`로 맞췄다.
앱 전용 wrapper나 Remmina preference 변경은 필요 없다. 적용은 다음과 같다:

```sh
python theme.py build
python theme.py update --live --only .config/gtk-3.0/yuru.css
```

열린 원격 연결을 마친 뒤 Remmina를 완전히 종료하고 정상 실행한다.
기존 `gtk.css` import가 다음 앱 실행·로그인에도 같은 파일을 읽는다.
부분 복원은 템플릿의 `searchbar`/`treeview.view header button` 추가 규칙을 되돌린 뒤
위 생성·선택 갱신과 앱 재실행을 반복한다. 테마 전체 복원은 아래 절차를 따른다.

검증(2026-11-01): 실제 Remmina 1.4.43을 격리 HOME·D-Bus·Wayland에서 수정 전 한 번,
수정 후 두 번 새로 실행했다. 활성/비활성 검색바가 모두 `#2A222B`이고 목록 표시·검색·
검색 해제가 동작한다. GTK3/4 CSS·Bash·격리 Sway 검사와 테스트 27개를 통과했다.
사용자 Remmina도 연결 창·활성 TCP 연결이 없는 상태에서 정상 종료·재실행했다.
해당 창의 작업공간은 화면에 표시하지 않았으므로 실제 사용자 창의 캡처 확인과는 구분한다.
OS 재부팅·재로그인은 수행하지 않았다.
[수정 전](verification/remmina-before.png), [수정 후](verification/remmina.png),
[검증 기록](verification/remmina.json).

## 복원

백업은 디렉터리 0700·파일 0600으로 보관하며 최초 설치 전 내용을 유지한다.
업데이트 이후 임의 편집이나 symlink 대상 변경은 자동으로 덮어쓰지 않는다.
거부되면 설치 기록과 해당 파일을 대조하고 변경 내용을 보존한 채 검토한다.

게임·작업을 저장하고 Sway를 종료한 TTY에서 다음 순서로 복원한다:

```sh
cd ~/dotfiles/yuru
python chatgpt_theme.py restore  # ChatGPT 테마를 별도로 적용했을 때
python discord_theme.py restore  # Discord 종료 후, 해당 테마를 별도로 적용했을 때
python activate.py restore-settings
python theme.py restore
~/.local/bin/start-sway
```

`restore-settings`는 자신이 적용한 값과 여전히 일치하는 GTK·Thunar preference를 되돌린다.
`restore`는 파일·권한을 복원하고 원래 없던 관리 파일은 제거한다.
ChatGPT·Discord preference 백업이 남아 있으면 파일 복원을 거부하므로 위 순서를 유지한다.
별도 설치한 btop 패키지와 CodexBar CLI는 파일 복원만으로 삭제되지 않는다.

## 검증 범위

2026-10-31 확인: 관리 파일 **58개**의 설치 SHA 일치, 설치·복원·선택 갱신·Usage·ChatGPT 설정 **32개 테스트 통과**.
ChatGPT는 별도 두 appearance 키만 저장·복원하며, 실제 app-server 프로세스 재실행과 버전 충돌을 격리 검증했다.
사용자 앱의 UI 재시작·실렌더와는 구분한다. swaynag는 격리 compositor에서 두 번 실행해
[실제 종료 확인 UI](verification/native-swaynag.png)를 확인했다. 검증용 Exit 동작은 `true`로 대체한다.
Chrome은 실제 설치 버전의 격리 프로필에서 테마 패키징을 확인했으며 최초 선택은 사용자 UI 단계로 남아 있다.
GTK3/4 CSS·Bash·desktop 항목·격리 Sway 구문, Rofi 검색 화면,
Qt5/6 offscreen 팔레트, 격리 Wayland의 btop·Usage 실렌더와 재실행을 확인했다.
Firefox 158.0.1도 격리 프로필의 두 번 실행에서 모서리·선택선·글꼴·본문 분리,
새 탭 배경·검색창·설정 버튼을 확인했다. 실제 element click으로 검색 handoff를 검증했다.
주소창·내부 입력·배경의 중복 outline 제거, 회색 입력 면과 민트 caret 색을 확인했다.
일반 실행에서는 격리 Wayland의 가상 키보드로 추천 목록을 열어 화면을 확인했다.
자동화를 켜지 않은 세 번째 일반 실행에서 상단 및 가로/세로 새 탭 화면을 캡처했다.
실제 Codex·Grok 조회와 배경 IPC를 확인했고 화면 모드·회전·위치는 유지했다.

사용자 실제 Firefox 프로필의 새 CSS 재시작 후 UI, 실제 재부팅·재로그인·모니터 재연결·lock/unlock,
모든 GTK/Qt 앱의 전체 화면·동작은 미검증이다. 저장 구조 확인과 실제 재시작 검증을 구분한다.

[최초 desktop 검증](verification/results.json), [모니터·업스케일 배경 검증](verification/monitors.json), [Firefox 검증](verification/firefox.json),
[Rofi 화면](verification/native-rofi.png).
[toolkit notes](toolkit-notes.md)와 [desktop notes](desktop-notes.md)는 초기 준비 단계의 형식 조사 기록이다.
디자인 조사 원본은 [design-rnd의 Yuru rice 연구](https://github.com/notdevblue/design-rnd/blob/main/studies/sway-rice/yuru-rice.md)에 있다.

### Live2D Companion의 SwayFX blur

Companion의 채팅·설정은 Xwayland `class=live2d-agent-companion`, `window_type=dialog`이므로 Kitty의 Wayland `app_id` 규칙과 별도로 지정한다. `templates/sway/effects.conf`의 다음 규칙은 배경 alpha .8인 두 대화 창에만 적용하며 unmanaged 캐릭터 Overlay와 native menu는 대상이 아니다.

```sway
for_window [class="^live2d-agent-companion$" window_type="dialog"] blur enable
```

`python theme.py update --live --only .local/share/yuru-theme/effects.conf`로 관리 중인 설치본과 journal SHA를 갱신한다. 전체 Sway reload 없이 현재 세션에는 위 `for_window` 명령과 `for_window`를 뺀 `[class=… window_type=…] blur enable`을 각각 적용한다. 기존 include는 다음 로그인에도 규칙을 읽고 새 창에도 적용한다. 원복은 해당 줄 제거·선택 갱신 후 같은 criteria의 `blur disable`이며, 현재 세션에 등록한 새 창 규칙의 완전 제거는 다음 정상 Sway 설정 재읽기 때 반영된다.

2026-11-01 검증: 기존 창 scoped 명령·새 창 규칙 등록 성공, 설치본/원본/복원본·include·journal SHA 일치, headless backend의 실제 SwayFX 전체 설정 validate 및 선택 갱신/원본 백업 보존 검사 2개 통과. 앱 재실행으로 생성한 채팅/설정이 해당 criteria의 dialog·32-bit ARGB·mapped임을 확인했다. IPC는 컨테이너별 blur 값을 읽어 주지 않으므로 이 기록은 명령 적용·규칙 매칭·투명 framebuffer 검사이며 compositor 픽셀 비교를 수행했다고 주장하지 않는다. OS 재부팅/재로그인은 하지 않았다.
