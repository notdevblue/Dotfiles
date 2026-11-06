# Waybar에서 Yeelight 제어

Waybar는 Codex/Grok과 같은 `light 65%` 형식이다. **좌클릭으로 세부 조절창**을 열고
다시 좌클릭하거나 Esc로 닫는다. 휠은 밝기 ±5%, 우클릭은 이름 편집이다. 전원은 팝업 스위치로 조절한다.
Grok 바로 오른쪽, 마이크 앞에 배치하며 조절창의 오른쪽 끝을 해당 모듈의 오른쪽 끝에 맞춘다.

조절창은 268px 폭, 기본 약 107px 높이의 네 줄이다. 첫 줄에 `전체`/개별 조명 선택과
전원 스위치, 다음 줄에 밝기·색온도·색상만 둔다. 바와 같은 12px 폰트·Yuru 팔레트와
직각 경계를 쓰며 제목·설명·정상 연결 상태 문구를 표시하지 않는다. 오류가 있을 때만
작은 `!`의 툴팁으로 원인을 확인한다. 색온도 조절은 백색, 색상 조절은 컬러 모드로 전환한다.

`전체`에서는 모든 온라인 지원 기기에 설정값을 적용한다. 휠은 각 기기의 기존 밝기를
기준으로 ±5% 조절한다. 오프라인·미지원 기기는 제외하고 오류 표시로 알린다. 개별 기기를 고르면
그 기기만 조절하며 바의 전원·휠도 같은 선택 범위를 따른다. 밝기가 다르면 바에 범위,
켜짐이 섞이면 켜진 수/온라인 수를 표시한다. 선택 범위는 다음 서비스 시작에도 유지한다.

바를 우클릭하거나 팝업의 조명 이름을 우클릭하면 같은 칸에서 표시 이름을 수정한다.
`전체` 상태면 개별 조명을 고른 뒤 편집한다. **Enter 저장, Esc 취소**, 빈 이름은 기본 이름으로
복원한다. 한글을 포함해 64자까지, 오프라인에서도 가능하다. 로컬 표시 이름 변경이므로
조명 제어 명령이나 quota를 사용하지 않는다.

창은 Waybar의 높이+아래 여백을 읽고, Codex/Grok의 native GTK 툴팁에서 실측한
4px 간격을 바 위에 둔다. 숫자 표시에 마우스를 올렸을 때 추가 툴팁이 조절창을
덮지 않도록 light의 hover 툴팁은 끈다. layer-shell 기본값은 Waybar의
exclusive zone까지 피하므로 margin만 주면 38px 예약 공간을 중복 계산해 창이 떨어졌다.
팝업의 exclusive zone을 -1로 지정해 예약 영역 계산을 피하고, 명시한 bar 높이·여백만
한 번 적용한다. 오른쪽 위치는 같은 폰트의 Pango 시계 폭·패딩과 마이크 표시 폭으로 계산한다.

클릭 명령은 `WAYBAR_OUTPUT_NAME`을 넘기는 `0.15.0-yuru-actions2` Waybar를 사용한다.
새 프로세스의 출력 인자를 GApplication command-line 경로로 기존 창에도 전달한다.
같은 출력에서는 열기/닫기, 다른 출력에서 클릭하면 그 화면으로 이동해 열린다.
포커스된 앱의 출력으로 추정하지 않는다. 실행 오류는 런타임의
`yuru-yeelight-popup.log`에만 기록한다.

Waybar가 실행한 helper는 `/usr/bin/python3 -Es`를 명시적으로 사용한다.
세션 PATH에 프로젝트 가상환경이 앞서면 `python3`가 시스템의 PyGObject(`gi`)를 찾지 못해
창 생성 전에 종료될 수 있다. `-E`는 Python 환경 변수, `-s`는 사용자 site-packages의
영향을 제외하고 시스템 GTK 바인딩을 읽게 한다. watch·클릭·휠도 같은 실행 경로를 쓴다.

## 검색과 상태 구조

`templates/waybar/scripts/yeelight.py`가 LAN 제어와 Unix RPC를 공유한다. 각 출력의
Waybar와 GTK 패널이 같은 사용자 서비스에 연결하므로 조명 TCP 연결을 중복 생성하지 않는다.
IP·공유기·인터페이스 이름을 설정하거나 저장하지 않는다. 활성 물리 인터페이스의 RFC1918 IPv4를
매번 찾고 Yeelight의 UDP `239.255.255.250:1982`로 검색한다. 공인 uplink·VPN은 제외한다.

멀티캐스트에 응답하지 않는 기기를 위해 첫 검색·수동 검색과 120초 간격 보조 검색에서
직접 연결된 /24 이하 사설 LAN의 TCP 55443을 전체 검색 12개와 빠른 재검색 4개, 합계 최대 16개씩 확인한다. 더 큰 LAN은 커널의
neighbor 목록만 확인한다. 포트 응답만으로 조명으로 등록하지 않고 `get_prop`의 모델·전원 등
응답을 검증한다. 보조 검색에서는 neighbor의 MAC을 기기 식별자로 사용한다. 표준 검색은
기기가 광고한 지원 명령을 쓰며 보조 검색은 읽힌 속성으로 지원 기능을 추정한다.
지원하지 않는 명령이나 색온도 범위는 기기의 오류 응답을 패널에 표시한다.

표준 검색 주기는 약 30초이고 상태는 TCP 알림과 45초 주기의 재조회로 갱신한다.
전체 subnet 검색은 별도 스레드에서 실행하고, 아직 등록하지 못한 neighbor 기기는 10초마다
따로 확인한다. 주소별 진행 상태와 온라인 연결을 확인해 중복 TCP 검색을 막는다.
전체 검색이 오래 걸리거나 첫 조회가 실패해도 다음 120초 검색까지 기다리지 않는다.
조명별 연결이 끊기면 자동 재접속하며 재검색으로 주소 변경을 반영한다. 과거에 대기하던
명령은 연결이 끊기면 취소한다. 슬라이더·휠 명령은 마지막 값으로 합치고 명령 전송량을 제한한다.
팝업의 기기 선택 전환 중에는 조작을 막고 이전 상태 응답과 지연 슬라이더 명령을 버린다.

`~/.local/state/yuru-yeelight/selection.json`에는 선택한 기기 식별자 또는 `all`과
선택적으로 `names: {기기 ID: 표시 이름}`을 0600으로 저장한다. 선택 변경·재검색·서비스
재시작 후에도 별칭을 유지한다. 검색 응답의 원래 기기 이름은 별도로 유지한다.
IP는 메모리에만 두며, 조명의 전원 기본값이나 전원 복구 설정은 변경하지 않는다.
RPC는 `$XDG_RUNTIME_DIR/yuru-yeelight.sock`의 0600 Unix 소켓이다. 네트워크 서버 포트를 열지 않는다.

## 입력과 요청 제한

첫 휠 입력은 즉시 전송 루프를 깨운다. 연속 입력은 마지막 값으로 합쳐, 입력이
60ms 조용해지거나 첫 대기값 이후 150ms가 되면 최신값을 보낸다. 따라서 휠 한 칸마다
물리 조명 요청 하나가 반드시 생기지 않으며, 계속 돌리는 동안에도 반영이 멎지 않는다.
밝기 최솟값·최댓값에서 같은 값이 되는 입력은 전송하지 않는다. 팝업의 입력 병합은
20ms/최대 40ms로 짧게 두고 실제 LAN 병합은 백엔드에서 한다.

기존 1.25초 고정 전송 간격, 100ms 폴링 대기, 슬라이더 ACK 직렬 대기를 제거했다.
소켓 깨우기·TCP_NODELAY를 사용하고 절대값 슬라이더 명령만 최대 두 개까지 진행한다.
오래된 ACK나 속성 조회가 더 최근 요청값을 덮지 않도록 세대를 확인한다. 확정된 `props`와
대기 중인 `pending`은 구분하며, Waybar는 100ms마다 확인하고 값이 달라질 때만 출력한다.

LAN 프로토콜의 연결당 분당 60개·기기 전체 분당 144개 제한을 고려해, 자체 전송은
연결당 48개/60초 및 전체 120개/60초로 제한한다. 다른 클라이언트 트래픽과 펌웨어의
집계 방식까지 추적할 수는 없다. 실제 `client quota exceeded` 응답을 받으면 60초간
제어·상태 조회를 멈추고 최종 절대값과 전원 의도만 보관한다. 대기 중 입력을 다시 쌓아
한꺼번에 재생하지 않는다. 런타임의 `yuru-yeelight.budget.json`(0600)에 식별자와
최근 전송 시각·대기 만료 시각을 저장해 서비스 재시작이 제한을 초기화하지 않게 한다.
IP·계정·비밀정보는 기록하지 않는다. 검증한 기기의 MAC·모델·지원 기능·최근 확정 속성도
이 런타임 캐시에 보관한다. 서비스가 다시 시작되면 현재 neighbor의 같은 MAC을 찾아
식별 조회용 연결을 새로 열지 않고 기존 방식의 지속 TCP 연결로 복구한다. 새 속성 조회가
성공하기 전에는 `stale`로 구분해 오래된 수치를 확정값으로 표시하지 않는다.

제한이 분당 1회 조회에서도 계속되고 실제 가동 시간이 긴 경우에는
[제조사가 확인한 약 49.7일 후 quota 타이머 오류](https://forum.yeelight.com/t/topic/15756/18)도
가능하다. 이 경우 제조사는 실제 전원 재연결을 안내한다. 소프트웨어의 off/on은 재부팅이 아니다.
이번 호스트의 가동 시간·재연결·복구 결과는 비공개 호스트 문서에 기록한다.
펌웨어 자체의 영구 수정이나 업데이트를 했다고 표현하지 않는다.

## 적용과 복원

필요 패키지는 `python`, `python-gobject`, `gtk3`, `gtk-layer-shell`, `iproute2`, `libnotify`다.
조명 앱에서 LAN 제어를 켜고 PC와 같은 사설 LAN에 연결한다. 생성기는 아래 파일을 기존
설치 기록에 통합하므로 재생성·다음 로그인도 같은 기본 경로를 쓴다.

```bash
cd ~/dotfiles/yuru
python install_waybar.py
python theme.py build
python theme.py update --live \
  --only .config/waybar/config.jsonc --only .config/waybar/style.css \
  --only .config/waybar/scripts/yeelight.py \
  --only .config/waybar/scripts/yeelight-popup.py \
  --only .config/waybar/scripts/yeelight.css \
  --only .config/systemd/user/yuru-yeelight.service
systemctl --user daemon-reload
systemctl --user enable --now yuru-yeelight.service
pkill -USR2 -x waybar
```

최초 테마 설치는 README의 offline install 절차를 사용한 뒤 사용자 서비스를 활성화한다.
Waybar도 서비스가 없으면 시작을 요청하지만 로그인 자동 시작은 위 enable 상태로 관리한다.
백엔드 코드를 갱신했으면 `systemctl --user restart yuru-yeelight.service`를 실행한다.
열린 패널은 닫았다가 다시 열어 갱신된 UI를 읽는다.

**전체 테마 복원 전 필수:** Waybar가 종료된 offline 복원 세션에서
`systemctl --user disable --now yuru-yeelight.service`를 먼저 실행하고 README의
`theme.py restore`를 수행한다. 이어 `systemctl --user daemon-reload`를 실행한다.
실행 중인 Waybar의 watch는 서비스를 다시 시작하므로 먼저 종료해야 한다.
이 절차가 서비스 프로세스와 `default.target.wants` 링크가 남는 것을 막는다.
선택 기록까지 지우려면 복원 후 `~/.local/state/yuru-yeelight/selection.json`만 별도로 삭제한다.

기능만 숨기려면 원본 Waybar `modules-right`에서 `custom/yeelight`를 제거하고 config를
선택 갱신·재읽기한 다음 패널을 닫고 서비스를 disable --now 한다. 원본 모듈 정의와 파일은
재활성화를 위해 유지할 수 있다. 이때도 IP 설정이나 별도 시험 실행 경로는 필요 없다.

## 검증

2026-11-07: 모의 TCP·RPC를 포함한 백엔드 44개, 테마 설치·복원 및 기존 Waybar 서비스와
및 Waybar 설치·마이그레이션 5개와 함께 총 95개 테스트 통과. `python verify_yeelight.py`는 격리 Sway·가짜 조명으로 GTK 패널을
렌더하고 HSV 색 표시, 기기 선택 직후의 명령 차단, 오래된 상태 무시, 슬라이더 최종 값 병합,
전체/개별 범위, 혼합 값 표시, 오프라인 조작 비활성화와 4px 간격을 확인한다. 같은 검사에서 PATH 앞에 실패하는 가짜 Python을 놓고 배포된 on-click 명령을 그대로 사용한다.
두 출력의 실제 Waybar 클릭으로 열기·닫기·재열기·출력 이동을 확인한다. 실제 포인터와
키보드로 개별 선택·우클릭 편집·저장·취소·초기화·오프라인 수정·바 우클릭 진입을 검사한다.
한글 조합 중 Enter가 미완성 문자열을 저장하지 않는 IME 보호도 확인한다. [패널 샘플](../verification/yeelight-panel.png)은
가짜 기기/수치이며 개인 LAN 식별자를 포함하지 않는다.

실제 호스트의 기기 검색·제어·서비스 재시작·지속성 확인 범위는 private-configs의 호스트 문서에
기록한다. 격리 검증이나 저장 구조 확인을 실제 재부팅·재로그인 검증으로 간주하지 않는다.

프로토콜 근거: [Yeelight 공식 LAN 규격](https://www.yeelight.com/download/Yeelight_Inter-Operation_Spec.pdf).
