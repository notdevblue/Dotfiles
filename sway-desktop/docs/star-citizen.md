# Star Citizen: Arch Linux / Sway 설정 및 문제 해결 기록

정리일: 2026-10-30. 기본 구성은 10월 27~28일에 설치·설정하고 실제 플레이로 확인한 내용이며, HDR 항목에는 10월 30일의 설정 및 진단 상태를 반영했다. 버전은 당시 사용한 값이며, 최신 버전 권장 목록은 아니다.

## 현재 구성

| 항목 | 최종 상태 |
| --- | --- |
| 설치 | LUG Helper로 구성한 `~/Games/star-citizen` Wine prefix |
| 게임 | LIVE, 캐시 디렉터리 기준 `sc-alpha-4.10.2` |
| 실행 | 앱 메뉴의 **RSI Launcher** → `sc-launch.sh` |
| Wine | LUG Wine Experimental Wayland `11.20-2` |
| 창 시스템 | Wine 네이티브 Wayland |
| 화면 | LG `DP-6`, 3440×1440, 게임 borderless + Sway fullscreen, 작업공간 5 |
| GPU | RTX 4090 24 GB, 확인 시 NVIDIA 드라이버 `615.78.08` |
| 렌더러 | **Vulkan**, `GraphicsRenderer = 1` |
| 업스케일링 | **DLSS 선택 가능**, 사용자 확인 완료 |
| HDR | 사용자 선호로 LG·MSI 모두 SDR, 실행 스크립트 `DXVK_HDR=0`; 실제 재부팅·게임 재실행 후 유지 확인 |
| 커서 | 게임 기본 커서, 소프트웨어 커서 강제 옵션 제거 |
| 키 반복 | 게임 포커스에서만 반복 끄기, 일반 창에서는 정상 반복 |
| 한/영 | 자동 전환 없음, Hangul 키 역할의 RAlt로 수동 전환 |
| RAlt 역할 | **Super+Ctrl+G**로 Alt ↔ Hangul 수동 전환 |
| 게임용 마이크 | MiniFuse 2의 **Mic/Line/Inst 1 (L)** |
| AirPods | 마이크 사용에 따른 handsfree 자동 전환을 끄고 별도 마이크 사용 |

기존 Windows 설치 파일을 Linux 설치에 재사용했고 Windows 쪽 원본은 유지했다. Linux에서 사용하는 prefix와 게임 설정은 별도로 관리한다.

## 평소 실행과 단축키

1. 앱 메뉴에서 **RSI Launcher**를 연다.
2. LIVE를 선택해 게임을 실행한다.
3. **Super+5**로 LG 모니터의 게임 작업공간으로 이동한다.
4. 게임 조작 전에는 한/영 상태를 직접 영문으로 맞춘다. RAlt가 게임 단축키에 필요하면 **Super+Ctrl+G**로 Alt 역할로 바꾼다.

| 키 | 동작 |
| --- | --- |
| Super+5 | 게임 작업공간으로 이동 |
| Super+1…0 | 다른 작업공간으로 이동 |
| Super+F | Sway fullscreen 토글 |
| Super+Ctrl+G | RAlt 역할을 Alt ↔ 한/영 키로 전환 |
| RAlt | Hangul 역할일 때 실제 한/영 입력 전환 |

**Super+Shift+G는 현재 단축키가 아니다.** 충돌 때문에 Super+Ctrl+G로 변경했다. Alt+Tab은 이 Sway 설정에서 창 전환 키로 지정하지 않았다.

RAlt 역할 토글은 언어 상태를 자동으로 영문으로 바꾸지 않는다. 영문으로 전환한 뒤 RAlt를 Alt 역할로 바꾸면 된다. 창이나 작업공간을 옮겨도 선택한 RAlt 역할과 한/영 상태를 자동으로 변경하지 않는다.

`sc-launch.sh`는 시작할 때 해당 prefix의 `wineserver -k`를 실행한다. 실행 중인 게임이 있다면 먼저 정상 종료한 뒤 런처를 다시 연다. 이 스크립트를 실행 중인 게임의 단순 상태 확인 용도로 호출하지 않는다.

## 게임·런처·Wine 업데이트

### 게임 업데이트

평소 게임 업데이트는 같은 **RSI Launcher**에서 LIVE 채널의 **Update**로 진행한다. 게임 파일을 처음부터 복사하거나 Wine prefix를 매번 다시 만들 필요는 없다. 설치를 인식하지 못하거나 파일 오류가 나면 **Settings → Games → LIVE**에서 설치 경로를 확인하고 **Verify**를 사용한다. 런처의 설치 위치와 Verify 항목은 [RSI 공식 안내](https://support.robertsspaceindustries.com/hc/en-us/articles/115013373508-Install-the-RSI-Star-Citizen-Launcher)를 참고한다.

현재 런처 안의 게임 경로는 다음 위치에 대응한다.

```text
C:\Program Files\Roberts Space Industries\StarCitizen\LIVE
```

### 런처와 Wine runner

런처 자체 업데이트는 런처의 안내를 따른다. 런처가 깨졌거나 runner를 교체할 때는 **Star Citizen LUG Helper**를 사용한다. Helper는 런처 재설치, runner 관리, 실행 스크립트 복구 기능을 제공한다. 메뉴별 용도는 [LUG Helper 문서](https://github.com/starcitizen-lug/lug-helper)를 참고한다.

```sh
~/.local/bin/lug-helper
```

Helper의 실행 스크립트 업데이트·복구를 사용하기 전에는 현재 `sc-launch.sh`를 백업한다. 이 PC에 추가한 Wayland·모니터·DLSS 설정이 유지됐는지 작업 후 비교한다. Wine runner 교체와 게임 패치는 서로 다른 작업이다.

dotfiles를 갱신해도 Wine prefix 안의 DLL, 게임 데이터, 그래픽 설정까지 자동으로 설치되지는 않는다.

## 파일 위치와 설정 보존

| 용도 | 위치 |
| --- | --- |
| Wine prefix | `~/Games/star-citizen` |
| 실행 스크립트 | `~/Games/star-citizen/sc-launch.sh` |
| 앱 메뉴 항목 | `~/.local/share/applications/rsi launcher.exe.desktop` |
| 게임 루트 | `<prefix>/drive_c/Program Files/Roberts Space Industries/StarCitizen/LIVE` |
| 화면·렌더러 지정 | `<LIVE>/user.cfg` |
| 게임 프로필 | `<LIVE>/USER/Client/0/Profiles/default/` |
| 그래픽·조작 프로필 | 위 프로필의 `attributes.xml`, `actionmaps.xml` |
| 렌더러 저장 JSON | `<prefix>/drive_c/users/han/AppData/Local/star citizen/<버전별 폴더>/GraphicsSettings/GraphicsSettings.json` |
| 실행 로그 | `<prefix>/sc-launch.log` |
| 게임 로그 | `<LIVE>/Game.log` |
| 작업 백업 | `~/.local/state/star-citizen-fixes/` |

현재 AppData의 버전별 폴더는 `starcitizen_(sc-alpha-4.10.2)_dpzt1d_0`이다. 업데이트 후 폴더 이름이 바뀔 수 있다. Linux 경로의 `USER` 대문자와 `star citizen` 공백에 주의한다.

현재 `user.cfg`의 핵심 값은 다음과 같다.

```ini
[Localization]
g_languageAudio=english
r_width = 3440
r_height = 1440
r_WindowMode = 1
r.GraphicsRenderer = 1
```

`GraphicsSettings.json`에도 `GraphicsRenderer: 1`이 저장돼 있다. 그래픽 옵션과 키 바인딩은 파일로 저장되어 있으며, 셰이더 재생성 작업에서도 보존했다. 주요 패치나 설정 초기화 전에는 `user.cfg`, `USER/Client/0/Profiles/default/`, 해당 버전의 `GraphicsSettings`를 함께 백업한다. 모든 향후 패치에서 옵션이 그대로 유지된다고 검증한 것은 아니다.

## 네이티브 Wayland, Vulkan, DLSS

### 실행 환경

실제 사용하는 runner는 다음 위치다.

```text
~/Games/star-citizen/runners/lug-wine-tkg-experimental-wayland-git-11.20-2/bin
```

현재 실행 스크립트에는 아래 항목이 들어 있다.

```sh
unset DISPLAY
export WAYLANDDRV_PRIMARY_MONITOR=DP-6
export DXVK_ENABLE_NVAPI=1
export DXVK_HDR=0
export WINEDLLOVERRIDES="winemenubuilder.exe=d;winex11.drv=d;nvapi,nvapi64=n"
```

네이티브 Wayland 전환 후 F 상호작용 선택 위치가 맞는 것을 사용자가 확인했다. Gamescope는 진단 중 시험했지만 선택 위치 문제를 해결하지 못했고, 최종 실행 경로에서는 사용하지 않는다.

### DLSS 구성

DLSS를 위해 [DXVK-NVAPI 0.9.2](https://github.com/jp7677/dxvk-nvapi/releases/tag/v0.9.2)를 prefix에 설치했다.

| 구성 | 위치·값 |
| --- | --- |
| 64비트 NVAPI | `<prefix>/drive_c/windows/system32/nvapi64.dll` |
| 32비트 NVAPI | `<prefix>/drive_c/windows/syswow64/nvapi.dll` |
| NGX DLL | `system32/nvngx.dll`, `system32/_nvngx.dll` |
| NGX 원본 | `/usr/lib/nvidia/wine/`의 해당 파일로 심볼릭 링크 |
| NVAPI 노출 | `DXVK_ENABLE_NVAPI=1` |
| DLL override | `nvapi,nvapi64=n` |
| Wine 레지스트리 | `Software\NVIDIA Corporation\Global\NGXCore`의 `FullPath = C:\Windows\System32` |

NVAPI·NGX·게임 DLSS 라이브러리가 로드된 것을 확인했고, 런처와 게임을 완전히 재실행한 뒤 사용자가 DLSS를 선택할 수 있다고 확인했다. 드라이버나 runner를 바꾼 뒤 DLSS가 사라지면 위 파일·심볼릭 링크·환경변수·override부터 비교한다. HDR은 별도 검증이 필요하며, DLSS가 된다고 HDR도 검증된 것은 아니다.

### HDR 인식 설정과 현재 SDR 선택

2026-10-30에 Sway를 실제로 다시 시작해 LG HDR 켜짐 / MSI HDR 꺼짐을 확인했다.
게임에는 별도로 `DXVK_HDR=1`을 노출하는 구성을 시험했다.
[LUG HDR 안내](https://github.com/starcitizen-lug/knowledge-base/blob/main/wiki/Tips-and-Tricks.md#hdr-high-dynamic-range)와
[DXVK 설정 설명](https://github.com/doitsujin/dxvk/blob/master/dxvk.conf)을 근거로 한다.
현재 experimental runner는 Vulkan 렌더링에서도 DXGI를 통한 presentation 경로를
사용하므로 이 설정만을 위해 DX11로 바꾸지 않았다. 적용에는 RSI Launcher와 해당
Wine 프로세스의 완전 종료 후 재실행이 필요하다. 이후 게임에서 HDR을 활성화하고
로그의 HDR 감지 및 실제 화면을 확인해야 한다. HDR 출력 경로의 정확성과
HDR 모드의 안정성은 검증하지 않았다.

이후 사용자가 HDR의 화면 표현을 선호하지 않아 LG·MSI를 모두 `hdr off`로
저장하고 실행 중인 출력에도 적용했다. 현재 `sc-launch.sh`는 `DXVK_HDR=0`을
명시해 다음 런처 실행부터 SDR을 노출한다. 실행 중인 게임의 환경은 소급해서
바뀌지 않으므로 게임 안의 HDR도 끄거나 런처까지 완전히 재실행해야 한다.
SDR 전환 당시에는 게임·런처·Sway를 종료하지 않았다. 이후 2026-10-30 22:57의
실제 OS 재부팅 뒤 양쪽 출력 `hdr=false`와 새 게임 프로세스 `DXVK_HDR=0`을 확인했다.
사용자는 재실행한 게임에서 월드 플레이 중임을 확인했다.

## 키보드: 게임 반복 방지와 수동 RAlt

최종 구현은 다음 두 기능으로 나뉜다.

| 기능 | 동작 | 파일 |
| --- | --- | --- |
| 게임 키 반복 관리 | 게임 포커스에서 rate 0, 일반 창에서 rate 25 | [game-input-guard](../config/sway/scripts/game-input-guard) |
| 수동 RAlt 역할 전환 | Super+Ctrl+G를 누를 때만 Alt ↔ Hangul | [toggle-ralt](../config/sway/scripts/toggle-ralt) |
| 시작·단축키 연결 | `exec_always`, 수동 토글 바인딩 | [26-game-input.conf](../config/sway/config.d/26-game-input.conf) |
| 일반 키보드 기본값 | US, `korean:ralt_hangul`, repeat 25 | [20-input.conf](../config/sway/config.d/20-input.conf) |
| 게임 식별·기본 XKB 옵션 | Star Citizen app ID/class 등 | [game-input.json](../config/sway/game-input.json) |

rate 0은 키를 누른 상태 자체를 막는 설정이 아니다. F를 계속 누르는 동안 반복 키 이벤트 때문에 상호작용이 끊기던 증상을 막기 위한 설정이다. 일반 창으로 돌아오면 문자·Backspace 등의 정상 반복을 복구한다. Steam 게임과 Gamescope도 식별하므로 Star Citizen에만 묶인 기능은 아니다.

반복 관리 프로그램은 **`input type:keyboard repeat_rate`만** 보낸다. 자동 한/영 전환, 자동 XKB 변경, 마우스 잠금·해제·워프 명령은 수행하지 않는다. 같은 게임 포커스 이벤트가 반복돼도 정책이 같으면 다시 적용하지 않는다. 정상 종료 시 일반 반복 rate 25를 복구한다.

수동 RAlt 토글은 키를 놓을 때 한 번 실행되며, 한/영 활성 상태와 키 반복 값은 변경하지 않는다. 기록된 모드는 다음 명령으로 확인할 수 있다.

```sh
~/.config/sway/scripts/toggle-ralt --status
```

Sway 설정을 다시 읽거나 새 세션을 시작하면 저장된 기본 Hangul 역할로 시작한다. 창 전환만으로 RAlt 역할을 바꾸지는 않는다.

## 마우스와 커서

### 화면 선택 위치와 기본 커서

회전된 보조 모니터가 있는 환경에서 F 상호작용 위치가 어긋났다. 최종적으로 LG `DP-6`를 기본 모니터로 지정한 네이티브 Wine Wayland 구성이 정상 동작했다. 창 배치는 [25-star-citizen.conf](../config/sway/config.d/25-star-citizen.conf)가 담당한다.

진단 중 추가했던 `pl_pit.forceSoftwareCursor`는 제거했다. 사용자는 게임 기본 커서로 정상 동작함을 확인했다.

### 5 → 1 이동 뒤 마우스 잠금과 작업공간 튐

기존 입력 관리 프로그램은 게임 포커스가 바뀔 때 키맵, 입력기 상태, 장치별 반복 속도를 함께 변경했다. 프로그램을 일시 정지하자 마우스 잠금과 작업공간이 되돌아가는 두 증상이 사라졌다.

코드 대조에서 **키보드와 포인터가 같은 식별자를 쓰는 복합 장치**를 확인했다. 기존의 `input <장치 식별자> repeat_rate ...` 방식은 같은 식별자의 포인터에도 설정 재적용 경로를 타게 했다. 최종 구현에서는 장치 식별자별 명령과 자동 키맵·입력기 변경을 제거하고 키보드 타입의 반복 속도만 바꾸도록 범위를 줄였다.

사용자는 최종 구성에서 게임 F 유지, 일반 창의 키 반복, 1↔5 작업공간 이동이 모두 정상이라고 확인했다. 앞서 시도했던 강제 잠금 해제·백그라운드 잠금 차단 등의 포인터 우회 처리는 최종 구현에 남아 있지 않다.

### 휠 과민 반응과 방향 이상

G502 X의 고해상도 휠 설정을 끈 뒤 사용자가 속도·방향 모두 정상이라고 확인했다.

```sh
solaar config 'G502 X' hires-smooth-resolution false
```

2026-10-30 재발 시 저장된 값은 false였지만 실제 장치 값은 true였다. 같은 HID++ 연결에서 false 쓰기와 읽기를 반복하면 유지됐고, 연결을 닫고 다시 열면 true로 돌아오는 현상을 재현했다. 따라서 로그인 시 한 번 실행하는 명령만으로는 유지되지 않았다. [Solaar 공식 문서](https://pwr-solaar.github.io/Solaar/issues/)도 Linux HID++ 드라이버가 이 설정을 변경한다고 설명한다.

현재는 [`g502-wheel-guard`](../config/sway/scripts/g502-wheel-guard)가 HID++ 연결을 유지하고 2초마다 실제 휠 모드를 확인한다. 고해상도 비트만 끄며 방향·diversion 등 다른 비트와 DPI는 보존한다. 장치가 없거나 통신이 실패하면 연결을 다시 찾으며 재시도한다. Solaar의 `ignore` 정책은 그대로 둔다.

[`g502-wheel-guard.service`](../config/systemd/user/g502-wheel-guard.service)를 `~/.config/systemd/user/`에 심볼릭 링크하고 `systemctl --user enable --now g502-wheel-guard.service`로 활성화한다. 사용자 기본 target에서 자동 시작하고, 비정상 종료 시 재시작한다. Sway의 `session-start`에서도 같은 서비스를 시작하므로 중복 프로세스는 생기지 않는다. 서비스 상태와 복구 기록은 다음 명령으로 확인한다.

```sh
systemctl --user status g502-wheel-guard.service
journalctl --user -u g502-wheel-guard.service -b
```

2026-10-30 검증: 서비스가 `enabled`, `active`이고 사용자 기본 target에 연결된 것을 확인했다. 실제 장치에서 고해상도 값을 일부러 다시 켜자 약 2초 안에 복구됐고 다른 휠 모드 비트는 유지됐다. 추가 HID++ 클라이언트를 열었을 때와 서비스 재시작 후에도 false 복구 및 연속 읽기를 확인했다. 이는 자동 시작 구조 확인과 서비스 재시작 검증이며, 실제 재부팅·재로그인·물리적 재연결은 수행하지 않았다.

Sway의 G502 포인터 가속은 `flat`, `pointer_accel 0.0`이다. DPI는 Solaar에서 별도로 관리한다.

## 오디오: AirPods 출력과 MiniFuse 마이크

AirPods 사용 중 handsfree로 바뀌던 증상에는 AirPods 마이크 대신 **MiniFuse 2 Mic 1**을 쓰고 Bluetooth headset 자동 전환을 끄는 구성을 적용했다.

```sh
wpctl settings --save bluetooth.autoswitch-to-headset-profile false
```

WirePlumber의 `~/.local/state/wireplumber/sm-settings`에 false가 저장돼 있으며, 현재 기본 입력은 MiniFuse의 **Mic/Line/Inst 1 (L), MONO**로 확인했다. 기본 입력 장치 선택도 WirePlumber의 `default-nodes`에 저장돼 있다.

AirPods로 들을 때는 pavucontrol에서 출력 장치와 A2DP 프로필을 선택하고, 게임·음성 채팅 입력은 MiniFuse Mic 1로 둔다. 문서 확인 시점의 기본 출력은 MiniFuse였으므로, AirPods가 항상 기본 출력으로 강제돼 있다는 의미는 아니다. 재부팅·AirPods 재연결을 포함한 전체 재검증은 하지 않았다.

## HUD만 보이고 월드가 검게 나왔던 문제

HUD·메뉴는 보이지만 DEPLOY 이후에도 월드가 계속 검게 보였다. Stable Diffusion과 LM Studio의 유휴 모델이 GPU 메모리를 사용하고 있어 사용자 승인 후 내렸지만, **메모리 확보와 게임 재실행만으로는 해결되지 않았다.** 모델·프로그램 파일은 유지했다.

게임 셰이더와 prefix의 드라이버 캐시를 백업해 다시 생성한 뒤 정상 월드 렌더링을 사용자가 확인했다. 당시 DX11도 진단에 사용했으나 현재 선택은 Vulkan이다.

| 재생성한 캐시 | 위치 |
| --- | --- |
| 게임 셰이더 | `<prefix>/drive_c/users/han/AppData/Local/star citizen/<버전별 폴더>/shaders` |
| NVIDIA 캐시 | `<prefix>/GLCache` |
| Mesa 캐시 | `<prefix>/mesa_shader_cache` |

원본 백업은 `~/.local/state/star-citizen-fixes/20261028-002130-shaders/`에 있다. 재발 시 게임과 런처를 종료한 상태에서 필요한 캐시만 별도 이름으로 백업해 재생성한다. 그래픽·조작 설정을 보존할 수 있도록 `USER` 프로필과 `GraphicsSettings`를 캐시와 구분한다. 캐시 재생성 직후에는 셰이더 생성이 끝난 다음 월드를 확인한다.

이 결과는 캐시 재생성이 당시 증상을 해결했다는 기록이다. 특정 캐시 파일의 내부 손상 원인까지 규명한 것은 아니다.

## 진단 중 발생한 Sway 크래시

2026-10-28 22:42 KST, 진단을 위해 게임 종료·재실행을 시도하는 중 Sway가 SIGSEGV로 종료돼 데스크톱 세션이 끊겼다. 당시 실행 중인 것은 로컬 Sway 1.12 detached fullscreen 빌드였다.

덤프의 주 스택은 `wl_list_remove → handle_im_popup_surface_unmap → … → handle_text_input_destroy`로, 입력기 팝업 정리 중 목록 제거에서 충돌했다. **이 크래시와 마우스 잠금 문제의 인과 관계는 입증하지 않았다.** 이 작업에서 Sway 크래시 수정 패치를 설치한 것도 아니다.

덤프와 진단 자료는 `~/.local/state/star-citizen-fixes/20261028-224112-pointer-root-cause/`에 보관한다. 게임 종료나 compositor 재시작을 단순한 상태 확인 수단으로 반복하지 않는다.

## 지속성 및 검증 범위

| 항목 | 저장·시작 구조 확인 | 실제 확인 범위 |
| --- | --- | --- |
| 게임 반복 방지 / 일반 창 반복 | `26-game-input.conf`의 `exec_always`, 기본 rate 25, reload tick 처리 | 사용자 게임·일반 창·1↔5 전환 확인, helper 종료·재시작 확인 |
| 수동 RAlt | 저장된 Super+Ctrl+G 바인딩, 설정 로드 시 토글 기록 초기화 | 수동 토글 실행, 반복 값·입력기 상태를 바꾸지 않음 확인 |
| 네이티브 Wayland / DLSS | 로컬 실행 스크립트·DLL·NGX 링크·레지스트리 | 게임 및 런처 재실행 뒤 DLSS 선택 가능 확인 |
| 해상도 / Vulkan | `user.cfg`, 프로필, GraphicsSettings JSON | 저장된 값 확인, 실행 환경에서 화면·F 선택 위치 확인 |
| AirPods / MiniFuse | WirePlumber 저장 설정·기본 입력, 오디오 서비스 활성화 | 설정값과 현재 MiniFuse Mic 1 확인 |
| 휠 | Solaar 저장값, 로컬 로그인 재적용 줄 존재 | 당시 속도·방향 정상 확인; 재연결·재로그인 후 미검증 |
| HDR / 현재 SDR | Sway Vulkan 렌더러, 양쪽 출력 `hdr off`, 로컬 실행 스크립트 `DXVK_HDR=0` | 2026-10-30 실제 OS 재부팅 뒤 양쪽 출력 off 및 새 게임 환경 `DXVK_HDR=0`, 사용자 월드 플레이 확인 |

SDR 설정은 위 실제 재부팅 뒤 확인했다. 다른 항목의 재부팅·재로그인 검증은
수행 범위를 넓혀 주장하지 않는다. 저장 구조 확인과 실제 재시작 검증을 구분하고,
앱·Wine·드라이버 업데이트나 장치 재연결 이후에는 해당 항목을 다시 확인한다.

저장소에는 Sway 창 규칙·입력 관리 스크립트·단축키·일반 키보드 설정이 들어 있다. `sc-launch.sh`, Wine DLL, 게임 프로필, WirePlumber·Solaar의 사용자 상태와 위 백업은 **이 PC의 로컬 파일**이다. 이 문서는 전체 설치물의 자동 복원 스크립트가 아니다.

## 빠른 확인 명령

현재 Sway 세션의 터미널에서 실행한다.

```sh
# 창 식별자·포커스, 연결 출력·입력 확인
swaymsg -t get_tree
swaymsg -t get_outputs
swaymsg -t get_inputs

# 수동 RAlt 토글의 기록된 역할 확인
~/.config/sway/scripts/toggle-ralt --status

# 입력기 상태: 1은 비활성, 2는 활성
fcitx5-remote
fcitx5-remote -n

# 오디오 자동 전환 저장값과 기본 마이크
wpctl settings bluetooth.autoswitch-to-headset-profile
wpctl inspect @DEFAULT_AUDIO_SOURCE@

# GPU 메모리 현황
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv
```

주요 변경 이력은 `fcf640d`(이전 RAlt 자동 처리), `448576a`(자동 처리 중지), `5e667cb`(키보드 타입에 한정한 반복 관리와 수동 RAlt 분리)다. 현재 동작의 기준은 `5e667cb` 이후 파일이다.
