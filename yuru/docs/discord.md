# Discord / Yuru Kitty

BetterDiscord용 단일 CSS 테마다. 원본은
[`templates/discord/YuruKitty.theme.css`](../templates/discord/YuruKitty.theme.css),
색·글꼴은 [`palette.json`](../palette.json)에서 생성한다.
Ubuntu Mono·D2Coding, 크림 글자·민트 강조, 80% 불투명도와 직각 컨트롤을 사용한다.
채팅 프사·서버 이미지·멤버 프사·답장·리액션·계정 설정은 그대로 사용한다.
외부 CSS·웹폰트·이미지 import나 JavaScript 플러그인은 없다.

## 배경과 유료 기능의 경계

공식 [Nitro 기능](https://support.discord.com/hc/en-us/articles/115000435108-What-are-Nitro-Nitro-Basic),
[프로필](https://support.discord.com/hc/en-us/articles/4403147417623-Custom-Profiles),
[상점](https://support.discord.com/hc/en-us/articles/17162747936663-Shop-FAQ),
[부스트](https://support.discord.com/hc/en-us/articles/360028038352-Server-Boosting-FAQ)를
조사하고 앱 배경과 사용자가 고른 콘텐츠를 구분했다.

| 영역 | 처리 원칙 | 검증 범위 / 남은 확인 |
| --- | --- | --- |
| 서버 채팅·DM·친구 목록 | 앱의 한 배경층만 alpha 합성. 하위 기본 패널은 투명 | 실제 서버 채팅·읽기 전용 입력·DM·친구 탭/목록/활동 카드와 네이티브 합성 확인 |
| 메뉴·입력·설정·다이얼로그 | 불투명 면과 읽을 수 있는 글자색. 일반/hover/pressed·disabled·키보드 포커스 유지 | 실제 설정 8개 화면, 우클릭 메뉴·검색 필터/빈 결과·이모지/GIF/스티커·Apps/첨부 메뉴·Inbox/고정 메시지 열람. 별도 대비·입력 검사 |
| Nitro 클라이언트 테마 | 앱용 gradient 슬롯만 Yuru의 단색 이미지로 대체. `none`으로 지워 새 팝업이 투명해지는 경로를 피함 | 실제 커스텀 클라이언트 테마와 충돌 확인·수정. 모드 4종 컴포넌트 검사 |
| 프로필·배너·효과·네임플레이트 | 중첩된 프로필의 light/dark 토큰·gradient·이미지·animation·mask를 재정의하지 않음 | 실제 흰 프로필 편집 미리보기·DM의 어두운 프로필·멤버/계정 이름표 표시 확인. 표본 대비·장식 검사. 모든 상품/효과 조합은 미검증 |
| 프사·역할·이름 표시 | 원본 이미지와 역할색 보존. 프사/장식 크기 비율과 접근성 확대 유지 | 실제 프사·역할색·유료 표시 이름/이름표 확인, 별도 장식 배치·확대 검사. 유료 효과 전 조합은 미검증 |
| 메시지 콘텐츠 | 코드·멘션·읽지 않음·반응만 제한적으로 조정. 스포일러 숨김·media filter/opacity·선택/답장 유지 | 표본 스포일러·반응·입력·미디어 CSS 검사. 투표·업로드·실제 첨부 재생·모든 embed는 미검증 |
| 스레드·포럼·검색 | 기본 팔레트 상속. 기능·배치·갤러리·태그를 재작성하지 않음 | 실제 검색 필터·빈 결과 확인. 단순 스레드/포럼 표본 검사. 실제 결과 행·포럼 갤러리·모든 분할 상태는 미검증 |
| Nitro·구독·선물·부스트·결제 | 공통 설정 바탕과 카드 경계를 조정. 가격·자격 표시·상품 그림 유지 | 실제 Nitro Home/상점/프로필 편집/Nitro/구독/선물함/부스트/결제 설정 열람. 구매·결제·선물 전송·부스트 실행은 미수행 |
| 통화·영상·송출·Activities | player·canvas·iframe·영상의 opacity/filter/display를 변경하지 않음. 앱의 투명도를 미디어 전체에 주지 않음 | 실제 음성 설정과 표본 video/iframe CSS 보존만 확인. 통화·송출·전체화면·PiP·Activities 실행은 미검증 |

`*`에 배경·opacity·filter·display·border-radius를 덮지 않는다. 팔레트는 `:root`와
현재 확인한 앱 전용 theme 경계에만 둔다. `.theme-light` 전체를 덮으면 밝은 유료 프로필과
Appearance 미리보기에 크림 글자가 섞여 읽을 수 없게 된다. 모르는 중첩 theme 경계는
Discord의 기본 토큰을 사용하므로 새 화면에 대한 지원을 검증한 것처럼 간주하지 않는다.
프로필 고유 색상·역할색은 사용자가 정하는 콘텐츠여서 모든 조합의 대비를 보장하지 않는다.

실제 앱의 추가 점검에서 Friends의 고유 선택자 우선순위 때문에 mint CTA에 흰 글자가 남고,
활동 카드와 Inbox/고정 메시지에는 하드코딩한 모서리가 남는 것을 확인했다.
Friends·설정 탐색·팝업 탭은 민트 커서선으로, 활동/상품/알림 카드의 바깥 틀은 직각으로 맞췄다.
이모지/GIF/스티커·Apps 등의 portal은 `.layer__59d0d`에서 새 theme 경계를 만들므로
그 경계도 앱 팔레트를 받게 했다. 중첩된 유료 프로필과 theme 미리보기의 자체 경계는 유지한다.
스위치는 프레임워크가 inline 색을 지정하므로 실제 input의 `:checked` 상태로 track/knob을
쌍으로 칠한다. 체크 여부·위치 이동·disabled·접근성 이벤트는 재작성하지 않는다.
읽기 전용 입력에는 장식용 `>`를 숨긴다. Nitro의 전체 페이지 장식 gradient만 제거하며
별도 hero 그림·상품 그림·가독성을 위한 상품 footer gradient는 유지한다.

입력창의 `>`는 Slate 입력문·placeholder와 글꼴/줄높이를 공유하고, Discord의 입력 높이와
`--chat-markup-line-height`로 계산한 동일한 첫 줄 padding에 둔다. 기존 `top: 12px`와
16px 전용 글꼴은 실제 입력문의 17px padding·14px 글자와 달라 기준선이 어긋났다.
여러 줄을 입력해도 첫 줄에 남으며, 입력창 전체 높이의 가운데로 이동하지 않는다.
포럼 글 작성은 `.textAreaForPostCreation`이 그 padding을 `0 !important`로 지운다.
같은 높이 공식을 쓰면 `>`가 `Enter a message...`보다 아래로 내려가므로, 그 입력만
`top: 0`에 두고 왼쪽 18px 여백은 `!important`로 다시 준다.

하단 계정 패널의 세로선은 `.sidebarList__5e434`의 원래 border가 절대 배치된 패널 뒤까지
계속되면서 투명한 프사/이름표 사이로 보인 문제였다. border의 레이아웃 폭은 유지하고 색만
투명하게 한 뒤, `--custom-app-panels-height`와 기존 간격을 뺀 높이까지만 1px 선을 그린다.
Discord의 동적 패널 높이를 사용하므로 이름표를 불투명하게 덮거나 57px를 하드코딩하지 않는다.
실제 앱에서 선 끝 y=1244와 패널 시작 y=1244가 일치함을 확인했다. 별도 픽셀 검사에서는
57px/190px 패널과 접힘 상태를 확인하고, 수정 규칙 제거 시 이름표에 선이 다시 나타나는 것도 재현했다.
190px 확장은 표본 검사이며 실제 음성 통화는 실행하지 않았다.

CSS만으로 바탕화면을 흐릴 수 없다. [BetterDiscord 투명도](https://docs.betterdiscord.app/themes/tutorials/transparency)를
켜서 새 Electron 창을 만들고, SwayFX의 `app_id=discord` blur 규칙을 함께 사용한다.
영상·글자까지 흐리게 하는 창 전체 opacity는 사용하지 않는다.

## 설치와 갱신

BetterDiscord를 설치하고 Discord를 한 번 시작해 기본 stable 설정을 만든 뒤 완전히 종료한다.
이 저장소의 Yuru 설치가 있는 환경에서는:

```sh
cd ~/dotfiles/yuru
python theme.py update --live \
  --only .config/BetterDiscord/themes/YuruKitty.theme.css \
  --only .local/share/yuru-theme/effects.conf
python discord_theme.py apply
discord
```

`--live`는 Sway 세션 안의 파일 설치를 허용한다. 위 종료·재시작은 **최초 설치와 창 투명도
preference 변경**에 필요하다. 이미 설치된 CSS만 갱신할 때는 Discord를 켜 둔 채 실행한다:

```sh
python theme.py update --live --only .config/BetterDiscord/themes/YuruKitty.theme.css
```

BetterDiscord 1.14.4는 파일 내용 변경(`change`)을 `reloadAddon`으로 처리해 활성 상태를 유지한다.
반면 원자적 파일 교체(`rename`)는 `unloadAddon` → `disableAddon`으로 처리한다.
그래서 기존 Discord CSS의 선택 갱신은 inode를 유지한 채 쓰고, BetterDiscord가 자동 리로드한다.
앱 재실행·Ctrl+R·실행 중 설정 JSON 수정은 필요 없다. 같은 CSS는 다시 쓰지 않는다.
최초 백업·갱신 journal·외부 수정 충돌 검사는 유지하고 쓰기 예외 시 직전 내용을 복구한다.
전원 중단처럼 복구 코드를 실행할 수 없는 중단은 부분 CSS를 남길 수 있다. 이때 journal의
`updating` 상태와 원본 backup을 보존하며, 모르는 SHA는 자동 덮어쓰지 않으므로 검토 후 복구한다.
다른 설치 파일과 journal 자체는 기존 원자적 저장을 유지한다.

새 호스트는 README의 최초 `theme.py install` 절차로 CSS를 설치한 뒤 `discord_theme.py apply`를 실행한다.
기본 경로는 `~/.config/BetterDiscord`이며 **native Linux stable**만 관리한다.
다른 채널·Flatpak·사용자 지정 XDG/BetterDiscord 경로는 자동 지원하지 않는다.

`discord_theme.py`는 `data/stable/settings.json`의 `window.transparency`와
`themes.json`의 `Yuru Kitty`만 병합한다. 원래 값·키/파일 부재 여부는
`~/.local/state/yuru-theme/discord-before.json`에 0600으로 보관한다.
반복 적용은 최초 백업을 유지하며, 관련 없는 테마와 preference는 변경하지 않는다.
수동 변경과 충돌하면 덮어쓰지 않고 거부한다. 계정 DB·토큰·대화·프로필 설정은 수집하지 않는다.

SwayFX의 기존 `effects.conf` include가 다음 로그인에도 blur 규칙을 읽는다.
이미 실행 중인 Sway에 새 규칙만 적용하려면:

```sh
swaymsg 'for_window [app_id="^discord$"] blur enable'
swaymsg '[app_id="^discord$"] blur enable'
```

두 번째 명령은 열린 Discord 창이 있을 때 실행한다. 전체 Sway reload는 필요 없다.

## 복원

Discord를 완전히 종료한 뒤 `python discord_theme.py restore`로 이전 두 preference를 복원한다.
Yuru 전체 파일 복원은 README의 순서를 따른다. preference 백업이 남으면 `theme.py restore`가
거부하므로 preference부터 복원한다. 개별 비활성화만 필요하면 BetterDiscord의 Themes에서
Yuru Kitty를 끌 수 있다. 이후 자동 복원은 수동 변경과의 충돌을 보고하므로 먼저 검토한다.

이 테마만 철회할 때는 관리 CSS와 파일 journal을 따로 삭제하지 말고 원본 변경을 되돌려
선택 갱신한다. CSS만 되돌릴 때는 자동 리로드되며, preference와 전체 복원은 종료 후 실행한다.
기존 전체 복원은 최초 CSS·Sway 파일을 복구한다.
로그아웃 전 임시로 기존 Discord 창의 blur를 끄려면
`swaymsg '[app_id="^discord$"] blur disable'`을 사용한다. 새 창에 적용되는 `for_window` 규칙은
설정 파일 복원 후 다음 정상 세션에서 제거된다. 수동 일회성 명령만으로 복원 완료라고 하지 않는다.

## 검증과 유지보수

2026-11-01, Discord stable **1.0.168**, BetterDiscord **1.14.4** 기준이다.

- 설치·선택 갱신·복원·preference 충돌/중단 복구·기존 Usage/ChatGPT: **43개 테스트 통과**.
  CSS 변경 후 inode·백업 유지, 짧은 내용으로 갱신 시 truncate, 외부 수정 거부·쓰기 실패 복구 포함.
- [공개 컴포넌트 검사](../verification/discord.json): **401개 통과**. 800/1280/1600px,
  root 16/20px, 앱 모드 4종, 불투명 메뉴·modal, 상태별 버튼 대비, 프로필·미리보기·장식 보존,
  스포일러·반응·입력·키보드 포커스·Friends 고유 CTA·portal·스위치·읽기 전용 입력·상품 틀을 검사한다.
  프사·미디어는 작성한 SVG/iframe 표본이다.
  계정 패널 뒤 구분선은 일반/확장 패널의 픽셀과 실제 클릭으로 검사한다.
  입력창은 실제 Slate/placeholder 구조에서 44/56/72px 높이·16/20px root·800/1280px와
  빈 입력/한 줄/여러 줄의 첫 글자 기준선을 비교한다. 이전 prompt 규칙은 어긋남을 재현한다.
  포럼 작성창은 padding이 0인 Slate에서 `>`와 첫 글자의 기준선·왼쪽 간격을 비교하고,
  채널용 가운데 정렬을 다시 넣으면 어긋남이 재현되는지 확인한다.
  React·권한·서버 기능·재생을 구현하거나 검증한 테스트가 아니다.
- [실제 앱 검사](../verification/discord-live.json): 실제 화면·네이티브 합성·설치 SHA·정상 재실행 범위.
  공개 화면은 계정 캡처 대신 [표본](../verification/native-discord.png)과
  [상태별 컴포넌트](../verification/discord-components.png)를 제공한다.
- 실제 **OS 재부팅·재로그인·모니터 재연결은 미수행**이다. 저장/include 구조와 실제 앱 재실행을 구분한다.

재검사는 Python `playwright`, `tinycss2`, `Pillow`와 Chrome이 필요하다:

```sh
python theme.py build
python -m unittest test_theme test_discord_theme test_chatgpt_theme test_usage
python verify_discord.py --discord-css /외부경로/discord-native.css \
  --betterdiscord-css /외부경로/betterdiscord-native.css
```

입력 CSS는 해당 Discord 버전의 **공식 정적 stylesheet만** 추출한 파일이어야 한다.
Yuru CSS를 함께 넣으면 비교 기준이 오염된다. 계정 DOM·메시지·인증 정보는 입력하지 않는다.
BetterDiscord 입력에서는 notification/toast 규칙만 추출한다. 앱의 다른 규칙이나 Yuru CSS를
비교 기준에 섞지 않는다. 업스트림 CSS는 저장소에 복사하지 않으며 SHA와 브라우저 버전만 결과에 기록한다.
Discord 업데이트 후에는 이 검사와 위 표의 실제 화면 점검을 반복하고, 바뀐 앱 theme 경계와
구조 선택자를 수정한다. 해당 클래스가 없어 검사 자체가 실행되지 않는 상황도 성공으로 처리하지 않는다.
