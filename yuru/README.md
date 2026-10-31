# GMK Yuru / Shima Rin rice

현재 사용하는 Sway rice의 설정 원본과 운영 안내다. 확인일: **2026-10-31**.
시마린 배경, GMK Yuru의 크림·버건디·민트를 바탕으로 고정폭 글자와 실제 프로그램 출력을 사용한다.
ASCII 느낌은 문자 정렬·짧은 Bash 프롬프트·얇은 경계로 만들고, 장식용 코드 라벨이나 대시보드는 넣지 않는다.

## 현재 구성

| 부분 | 구성과 적용 상태 |
| --- | --- |
| Sway / SwayFX | 1px 직각 경계, inner gap 6 / outer gap 2. 기존 타일링·입력·게임·전체화면 설정 유지. |
| Waybar | 하단 26px. 왼쪽 숫자 workspace, 오른쪽 시각만 표시. |
| Kitty / Bash | Ubuntu Mono, Yuru 16색, 불투명도 1.0, blur 끔. Bash는 경로와 `$`/`#` 프롬프트. 새 셸부터 반영. |
| Rofi | 13pt. 입력·일반 행은 어두운 배경에 크림 글자, 선택은 민트 배경에 먹색 글자. |
| GTK3 / GTK4 | Adwaita 기반 CSS, Ubuntu Mono 11, dark 선호. 아이콘·커서는 Adwaita. |
| Thunar | GTK 테마와 상세 목록·경로 입력창 사용. |
| Qt5 / Qt6 | Fusion 팔레트와 버전별 QSS. 공통 환경 키는 `QT_QPA_PLATFORMTHEME=qt5ct`. |
| Dunst / Fcitx5 / gtklock | 알림·입력 후보창·잠금 UI의 색과 글꼴 통일. 실제 lock/unlock은 미검증. |
| Code - OSS | 기존 설정에 UI 색·폰트 병합. JSONC·별도 프로필은 자동 병합 대상에서 제외. |
| Firefox | 탭·주소창·메뉴 색 파일 저장 완료. **현재 실행 중인 브라우저는 재시작 대기**, 재시작 후 실렌더 미검증. |
| btop | CPU·GPU·VRAM·RAM·프로세스. 2초 갱신, 직각 테두리·민트 그래프. |
| Usage | CodexBar CLI를 사용하는 자체 GTK3 창. Codex·Grok 한도와 초기화 시간, 5분 갱신. |
| 배경 | 사용자가 업스케일한 가로·세로 시마린 이미지 적용 완료. |

Chrome·Discord·Steam 앱 내부 테마는 현재 범위에 포함하지 않는다.
전체 Sway reload나 실행 중 앱의 일괄 종료 없이 적용했다. **OS 재부팅·재로그인 검증은 아직 하지 않았다.**

## 팔레트

색과 기본 글꼴의 원본은 [`palette.json`](palette.json)이다.

| 용도 | 값 |
| --- | --- |
| 배경 / 면 | `#1E191F` / `#2A222B` |
| 글자 / 밝은 글자 | `#E1DBD1` / `#EAECF0` |
| 선택·강조 | `#88D4CC` |
| 경계 | `#712F3E` |
| 보조 글자 | `#A69A9F` |
| 오류·부족 상태 | `#D58C97` |
| 글꼴 | Ubuntu Mono, 한글은 설치된 Noto CJK fallback |

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
├── test_theme.py            설치·복원 검증
├── test_usage.py            한도 응답·타임아웃 검증
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
| Usage 실행 명령 | `~/.local/bin/yuru-usage` |
| Rofi 실행 항목 | `~/.local/share/applications/yuru-{usage,btop}.desktop` |
| Firefox | 선택된 프로필의 `chrome/yuru.css`, `userChrome.css` import, `user.js` flag |
| 원본 백업·설치 기록 | `~/.local/state/yuru-theme/`, Git 제외 |

현재 호스트의 적용 기록은 private-configs의 `hosts/hanusearch/docs/yuru-theme.md`에 있다.
다른 호스트에서는 DP-5/DP-6, Qt 경로와 시작 훅을 먼저 검토한다.

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

## btop과 AI 사용량

Rofi에서 **btop (Yuru)**와 **Usage**로 실행한다. 터미널 명령은 `btop`, `yuru-usage`다.
자동 시작 항목이나 Waybar 사용량 수집기는 추가하지 않았다. 필요한 때 열어 타일로 배치한다.

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
python theme.py build
python theme.py plan
python -m unittest -v test_theme.py test_usage.py
python verify_native.py --rofi
```

`build`와 `plan`은 활성 설정을 바꾸지 않는다. 새 설치는 `install`, 설치 후 변경은 `update`다.
보통 Sway를 종료한 상태에서 실행한다. 현재 세션에 의도적으로 반영할 때만 `--live`를 붙인다.

```sh
# 최초 설치와 기존 설치 갱신 중 하나를 선택
python theme.py install --live
# python theme.py update --live
python activate.py apply
```

파일 설치와 runtime 적용은 별도다. `activate.py`는 Sway의 시각 명령과 앱별 reload를 수행한다.
전체 Sway config를 재로드하거나 Firefox를 종료하지 않는다.

| 항목 | 새 설정을 읽는 시점 |
| --- | --- |
| Sway 색·배경 | `activate.py apply`의 개별 IPC. 다음 세션에는 저장된 include에서 로드. |
| Kitty·Waybar·Dunst·Fcitx | activation의 앱별 reload. |
| Bash | 새 interactive shell. |
| GTK 앱·Usage·btop | 해당 앱을 다시 실행할 때. |
| Qt 앱 | Qt 환경 키를 받은 새 프로세스. 로그인 환경·start-sway·Bash·launcher 경로에 연결됨. |
| Firefox UI | Firefox를 완전히 종료한 뒤 정상 시작할 때. |
| Firefox 파일 선택창 | GTK portal backend가 새로 시작할 때. Firefox UI와 별개다. |

파일 선택창만 예전 Adwaita 모습이면 선택 작업을 마치고 창을 닫은 뒤 실행한다:

```sh
systemctl --user restart xdg-desktop-portal-gtk.service
```

이 명령은 열려 있는 파일 선택창을 닫을 수 있다. 다음 파일 선택창에서 새 GTK CSS를 읽는다.

## 복원

백업은 디렉터리 0700·파일 0600으로 보관하며 최초 설치 전 내용을 유지한다.
업데이트 이후 임의 편집이나 symlink 대상 변경은 자동으로 덮어쓰지 않는다.
거부되면 설치 기록과 해당 파일을 대조하고 변경 내용을 보존한 채 검토한다.

게임·작업을 저장하고 Sway를 종료한 TTY에서 다음 순서로 복원한다:

```sh
cd ~/dotfiles/yuru
python activate.py restore-settings
python theme.py restore
~/.local/bin/start-sway
```

`restore-settings`는 자신이 적용한 값과 여전히 일치하는 GTK·Thunar preference를 되돌린다.
`restore`는 파일·권한을 복원하고 원래 없던 관리 파일은 제거한다.
별도 설치한 btop 패키지와 CodexBar CLI는 파일 복원만으로 삭제되지 않는다.

## 검증 범위

2026-10-31 확인: 관리 파일 **51개**의 설치 SHA 일치, 설치·복원 및 Usage 처리 **25개 테스트 통과**.
GTK3/4 CSS·Bash·desktop 항목·격리 Sway 구문, Rofi 검색 화면,
Qt5/6 offscreen 팔레트, 격리 Wayland의 btop·Usage 실렌더와 재실행을 확인했다.
실제 Codex·Grok 조회와 배경 IPC를 확인했고 화면 모드·회전·위치는 유지했다.

Firefox 재시작 후 UI, 실제 재부팅·재로그인·모니터 재연결·lock/unlock,
모든 GTK/Qt 앱의 전체 화면·동작은 미검증이다. 저장 구조 확인과 실제 재시작 검증을 구분한다.

[최초 desktop 검증](verification/results.json), [모니터·업스케일 배경 검증](verification/monitors.json),
[Rofi 화면](verification/native-rofi.png).
[toolkit notes](toolkit-notes.md)와 [desktop notes](desktop-notes.md)는 초기 준비 단계의 형식 조사 기록이다.
디자인 조사 원본은 [design-rnd의 Yuru rice 연구](https://github.com/notdevblue/design-rnd/blob/main/studies/sway-rice/yuru-rice.md)에 있다.
