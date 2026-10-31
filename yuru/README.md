# GMK Yuru / Shima Rin rice

현재 사용하는 Sway rice의 설정 원본과 운영 안내다. 확인일: **2026-11-01**.
시마린 배경, GMK Yuru의 크림·버건디·민트를 바탕으로 Ubuntu Mono·D2Coding 고정폭 UI·터미널과 실제 프로그램 출력을 사용한다.
ASCII 느낌은 문자 정렬·짧은 Bash 프롬프트·얇은 경계로 만들고, 장식용 코드 라벨이나 대시보드는 넣지 않는다.

## 현재 구성

| 부분 | 구성과 적용 상태 |
| --- | --- |
| Sway / SwayFX | 1px 직각 경계, 비활성은 어두운 자주빛·활성은 낮은 채도의 청록색. inner gap 6 / outer gap 2. 기존 타일링·입력·게임·전체화면 설정 유지. |
| Waybar | 하단 26px. 왼쪽 숫자 workspace, 오른쪽 접히는 트레이·Codex·Grok 남은 한도·시각과 기본 마이크 음소거 시 빨간 마이크 빗금 아이콘 표시. Adwaita의 `microphone-disabled-symbolic.svg` 사용. |
| Kitty / Bash | Ubuntu Mono, Yuru 16색, 불투명도 0.75, Kitty 전용 blur 켬. Bash는 경로와 `$`/`#` 프롬프트. 새 셸부터 반영. |
| Rofi | 13pt. 입력·일반 행은 어두운 배경에 크림 글자, 선택은 민트 배경에 먹색 글자. |
| GTK3 / GTK4 | Adwaita 기반 CSS, Ubuntu Mono·D2Coding 10.5pt(14px), dark 선호. 아이콘은 Yuru, 커서는 Adwaita. |
| Thunar | GTK 테마와 상세 목록·경로 입력창 사용. 비활성 창의 메뉴바 남은 폭도 같은 배경색으로 통일. |
| Qt5 / Qt6 | Ubuntu Mono·D2Coding 10.5pt·고정폭 Ubuntu Mono 11pt, Fusion 팔레트와 버전별 QSS. 공통 환경 키는 `QT_QPA_PLATFORMTHEME=qt5ct`. |
| Dunst / Fcitx5 / gtklock | 알림·입력 후보창·잠금 UI의 색과 글꼴 통일. 실제 lock/unlock은 미검증. |
| swaynag | 종료 확인·설정 오류 UI. warning/error 색과 글꼴을 기본 설정에 연결. 다음 실행부터 적용. |
| Code - OSS | 기존 설정에 UI 색·폰트 병합. JSONC·별도 프로필은 자동 병합 대상에서 제외. |
| Firefox | 직각 UI·Ubuntu Mono/D2Coding 14px와 시마린 새 탭. **사용 중인 프로필은 다음 정상 재시작에 새 글꼴 반영**. 별도 프로필 가로·세로 실렌더 확인. |
| Chrome | 네이티브 테마의 탭·툴바·주소창 색과 시마린 새 탭 배경. 파일 설치 완료, 최초 테마 선택은 아래 절차 필요. |
| ChatGPT 데스크톱 | 공식 Appearance 설정의 배경·글자·민트 강조와 UI/코드 폰트. 네이티브 설정 저장 도구 제공. |
| btop | CPU·GPU·VRAM·RAM·프로세스. 2초 갱신, 직각 테두리·민트 그래프. |
| cava | 기본 출력 소리를 민트색 막대로 표시. 터미널 배경·투명도 유지. |
| Usage | CodexBar CLI를 사용하는 자체 GTK3 창. Codex·Grok 한도와 초기화 시간, 5분 갱신. |
| 배경 | 원래 겨울 풍경·캐릭터를 SwinIR classical 2×로 확대. 산·수면의 원본 기반 ASCII 질감과 국소 파문. 인물·눈 쌓인 난간 보호. |

Discord·Steam·GPU Screen Recorder UI의 내부 팔레트는 현재 자동 적용 범위에 포함하지 않는다.
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

원본·프롬프트도 보존한다:
[최초 가로](assets/wallpaper.png) / [프롬프트](assets/wallpaper-prompt.txt),
[최초 세로](assets/wallpaper-portrait.png) / [프롬프트](assets/portrait-wallpaper-prompt.txt),
[약한 보정 가로](assets/wallpaper-retouched.png) / [프롬프트](assets/wallpaper-retouched-prompt.txt),
[약한 보정 세로](assets/wallpaper-portrait-retouched.png) / [프롬프트](assets/portrait-wallpaper-retouched-prompt.txt).
[soft 변형 기록](assets/soft-wallpapers.json)과 [retouch 기록](assets/retouched-wallpapers.json)은 생성 당시 기록이다.
현재 선택 파일의 크기·SHA는 [최신 검증 기록](verification/monitors.json)에 있다.

## ASCII 인터랙티브 배경

현재 배경은 **원래 가로·세로 겨울 장면 + 원본의 색·명암·윤곽에서 읽은 ASCII 질감**이다.
선택은 [`scene_assets.json`](scene_assets.json), 렌더러는 `ascii_wallpaper.py`다.
숲·산·마을·호수 반사·눈 쌓인 난간을 그대로 유지하고 산·수면 일부에 문자 질감을 넣는다.
글자 농도는 원본 명암, `/ \\ | -` 방향은 주변 밝기 변화에서 정한다. 평탄한 하늘에 같은
기호를 반복하지 않고, 인물·전경은 실제 clip으로 문자·눈·파문에서 보호한다.

캐릭터를 따로 생성·분리·이동하지 않는다. 원래 구도 전체를 한 번 cover-fit하여 오른쪽·
아래 가장자리까지 이어지게 한다. 기존 컷아웃의 오른쪽 절단면을 화면 안쪽 2%에 놓던
문제를 없앴다. 별도 ImageGen 컷아웃과 CUNet 확대 경로는 폐기했다.

| 방향 | 현재 인터랙티브 장면 | 크기 |
| --- | --- | --- |
| 가로 | [SwinIR 가로](assets/wallpaper-landscape-swinir.png) | 3876×1624 |
| 세로 | [SwinIR 세로](assets/wallpaper-portrait-swinir.png) | 1624×3870 |

두 장면은 **원래 보정본에서 직접 SwinIR classical DF2K 2×**로 확대했다. GAN·얼굴 보정·
별도 노이즈 제거·색 팔레트 변환·추가 선명화를 사용하지 않는다. 같은 원본의 Lanczos4,
SwinIR, Real-CUGAN conservative/no-denoise를 비교해 원래 색면과 부드러운 선을 덜 바꾸는
classical 모델을 선택했다. 원본 크기로 되줄인 인물 영역의 RGB 차이와 저주파 색 차이는
[비교·모델·SHA256·명령 기록](assets/scene-upscale.json)에 있다. 이 지표는 원본 보존 정도이며
없는 고해상도 정답의 복원을 입증하지 않는다. [얼굴 비교](verification/scene-upscale-comparison.png).

모델 생성만 별도 PyTorch·timm·OpenCV·NumPy·requests 환경이 필요하다.
`upscale_scene.py`는 고정한 공식 코드·가중치를 내려받아 SHA256을 확인한다.
런타임은 이미 만들어진 PNG만 읽으며 GPU 추론을 계속 실행하지 않는다.

```sh
# PyTorch/CUDA가 준비된 별도 환경에서 자산을 다시 만들 때만
python upscale_scene.py --source assets/wallpaper-retouched.png \
  --output assets/wallpaper-landscape-swinir.png
python upscale_scene.py --source assets/wallpaper-portrait-retouched.png \
  --output assets/wallpaper-portrait-swinir.png
# 일반 창에서 미리보기; 데스크톱 설정 변경 없음
python ascii_wallpaper.py --preview
# 최초 설치 및 현재 세션 적용; Sway 전체 reload 불필요
python wallpaper_control.py install
~/.local/bin/yuru-wallpaper start
~/.local/bin/yuru-wallpaper status
# 변경 후 갱신은 stop → install → start
~/.local/bin/yuru-wallpaper stop
# 자동 시작까지 제거해 기존 정적 배경으로 복원
python wallpaper_control.py restore
```

런타임 필요 패키지는 `python-gobject`, `python-cairo`, `gtk3`, `gtk-layer-shell`이다.
GTK3 layer-shell의 bottom 레이어로 `swaybg` 위·앱 창 아래에 표시하고 키보드 포커스·
화면 예약 영역은 사용하지 않는다. 바탕화면에서 눈이 커서 주변으로 흩어지고, **호수의
왼쪽 클릭은 파문**을 만든다. 인물·난간·하늘 클릭은 파문을 만들지 않는다. 평소 8fps·
입력 직후 20fps이며 현재 workspace의 전체화면 출력은 최대 약 2초 뒤 그리기를 멈춘다.

설치본은 `~/.local/share/yuru-ascii/`, 실행기는 `~/.local/bin/yuru-wallpaper`다.
`~/.config/sway/config.d/95-yuru-ascii.conf`의 exec_always가 기존 include에서 시작하고,
런타임 잠금·준비 완료 신호로 중복 실행·조기 성공 보고를 막는다. 설치 기록·로그는
`~/.local/state/yuru-ascii/`에 둔다. scene manifest에서 선택한 두 이미지도 함께 설치한다.
업데이트는 이전 관리 파일의 SHA를 먼저 확인하고 폐기한 컷아웃을 제거한다. 외부 편집은
보존하며 설치 실패는 되돌린다. base dotfiles의 생성 include는 Git에서 제외한다.
기존 `wallpapers.json`·정적 PNG·브라우저 새 탭은 별도 fallback으로 유지한다.

2026-11-01 검증: 설치·이전 자산 이관·외부 편집 보존·중복 실행·시작 실패와 구도·보호 영역·
클릭 범위 **19개 테스트** 통과. 원본 크기에서 캐릭터·난간 표본 픽셀이 문자·애니메이션 뒤에도
선택된 장면 PNG와 같음을 확인했다. 두 번의 새 격리 Sway에서 포인터·파문, 앱 입력·포커스,
전체화면 일시정지·재개, 크기 변경·가상 출력 재연결을 확인했다.
[검증 기록](verification/ascii-wallpaper.json), [가로 시안](verification/ascii-landscape.png),
[세로 시안](verification/ascii-portrait.png). 호스트의 앱 재실행과 저장 구조는 private-configs의
호스트 문서를 따른다. OS 재부팅·재로그인·물리 모니터 재연결 검증은 수행하지 않았다.

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

## Firefox UI

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

원본은 `templates/waybar/config.jsonc`의 `group/tray-drawer`·`custom/tray`·`tray`와
`templates/waybar/style.css`·`tray-{closed,open}.svg`다. Waybar 기본 drawer를 사용해 별도 트레이 앱·서비스는 없다.
화살표는 drawer의 실제 열림 상태에 따라 CSS로 바뀌며 별도 토글 스크립트나 상태 파일은 없다.
적용은 아래 **btop과 AI 사용량**의 Waybar 선택 갱신·재읽기 명령을 따른다.
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
python theme.py update --live --only .config/waybar/config.jsonc --only .config/waybar/style.css \
  --only .config/waybar/tray-closed.svg --only .config/waybar/tray-open.svg
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

## 복원

백업은 디렉터리 0700·파일 0600으로 보관하며 최초 설치 전 내용을 유지한다.
업데이트 이후 임의 편집이나 symlink 대상 변경은 자동으로 덮어쓰지 않는다.
거부되면 설치 기록과 해당 파일을 대조하고 변경 내용을 보존한 채 검토한다.

게임·작업을 저장하고 Sway를 종료한 TTY에서 다음 순서로 복원한다:

```sh
cd ~/dotfiles/yuru
python chatgpt_theme.py restore  # ChatGPT 테마를 별도로 적용했을 때
python activate.py restore-settings
python theme.py restore
~/.local/bin/start-sway
```

`restore-settings`는 자신이 적용한 값과 여전히 일치하는 GTK·Thunar preference를 되돌린다.
`restore`는 파일·권한을 복원하고 원래 없던 관리 파일은 제거한다.
ChatGPT 백업이 남아 있으면 파일 복원을 거부하므로 위 순서를 유지한다.
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
