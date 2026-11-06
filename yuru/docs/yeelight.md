# Waybar에서 Yeelight 제어

하단 Waybar의 `☼ 밝기%`는 선택한 조명의 상태다. 꺼지면 `off`, 연결이 끊기면 `!`,
검색 전에는 `—`다. 좌클릭은 전원 토글, 휠은 밝기 ±5%, 우클릭은 조절 패널이다.
패널에서 조명 선택, 전원, 밝기, 백색의 색온도, 컬러의 색상 선택을 제공한다.
백색/컬러는 서로 다른 모드이며 마지막 조작한 모드로 전환한다. Esc·×·바 우클릭으로 닫는다.
패널은 현재 포커스된 출력의 오른쪽 아래에 열리고, 휴대폰의 상태 변경도 반영한다.

## 검색과 상태 구조

`templates/waybar/scripts/yeelight.py`가 LAN 제어와 Unix RPC를 공유한다. 각 출력의
Waybar와 GTK 패널이 같은 사용자 서비스에 연결하므로 조명 TCP 연결을 중복 생성하지 않는다.
IP·공유기·인터페이스 이름을 설정하거나 저장하지 않는다. 활성 물리 인터페이스의 RFC1918 IPv4를
매번 찾고 Yeelight의 UDP `239.255.255.250:1982`로 검색한다. 공인 uplink·VPN은 제외한다.

멀티캐스트에 응답하지 않는 기기를 위해 첫 검색·수동 검색과 120초 간격 보조 검색에서
직접 연결된 /24 이하 사설 LAN의 TCP 55443을 최대 16개씩 확인한다. 더 큰 LAN은 커널의
neighbor 목록만 확인한다. 포트 응답만으로 조명으로 등록하지 않고 `get_prop`의 모델·전원 등
응답을 검증한다. 보조 검색에서는 neighbor의 MAC을 기기 식별자로 사용한다. 표준 검색은
기기가 광고한 지원 명령을 쓰며 보조 검색은 읽힌 속성으로 지원 기능을 추정한다.
지원하지 않는 명령이나 색온도 범위는 기기의 오류 응답을 패널에 표시한다.

표준 검색 주기는 약 33초이고 상태는 TCP 알림과 45초 주기의 재조회로 갱신한다.
조명별 연결이 끊기면 자동 재접속하며 재검색으로 주소 변경을 반영한다. 과거에 대기하던
명령은 연결이 끊기면 취소한다. 슬라이더·휠 명령은 마지막 값으로 합치고 명령 전송량을 제한한다.
팝업의 기기 선택 전환 중에는 조작을 막고 이전 상태 응답과 지연 슬라이더 명령을 버린다.

`~/.local/state/yuru-yeelight/selection.json`에는 선택한 기기 식별자만 0600으로 저장한다.
IP는 메모리에만 두며, 조명의 전원 기본값이나 전원 복구 설정은 변경하지 않는다.
RPC는 `$XDG_RUNTIME_DIR/yuru-yeelight.sock`의 0600 Unix 소켓이다. 네트워크 서버 포트를 열지 않는다.

## 적용과 복원

필요 패키지는 `python`, `python-gobject`, `gtk3`, `gtk-layer-shell`, `iproute2`, `libnotify`다.
조명 앱에서 LAN 제어를 켜고 PC와 같은 사설 LAN에 연결한다. 생성기는 아래 파일을 기존
설치 기록에 통합하므로 재생성·다음 로그인도 같은 기본 경로를 쓴다.

```bash
cd ~/dotfiles/yuru
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

2026-11-07: 모의 TCP·RPC를 포함한 백엔드 19개, 테마 설치·복원 및 기존 Waybar 서비스와
함께 총 65개 테스트 통과. `python verify_yeelight.py`는 격리 Sway·가짜 조명으로 GTK 패널을
렌더하고 HSV 색 표시, 기기 선택 직후의 명령 차단, 오래된 상태 무시, 슬라이더 최종 값 병합,
오프라인 조작 비활성화를 확인한다. [패널 샘플](../verification/yeelight-panel.png)은
가짜 기기/수치이며 개인 LAN 식별자를 포함하지 않는다.

실제 호스트의 기기 검색·제어·서비스 재시작·지속성 확인 범위는 private-configs의 호스트 문서에
기록한다. 격리 검증이나 저장 구조 확인을 실제 재부팅·재로그인 검증으로 간주하지 않는다.

프로토콜 근거: [Yeelight 공식 LAN 규격](https://www.yeelight.com/download/Yeelight_Inter-Operation_Spec.pdf).
