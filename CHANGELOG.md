# Changelog

형식: [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) · 버전: [SemVer](https://semver.org/lang/ko/)

## [Unreleased]

## [0.4.7] - 2026-06-22

### Added
- 차트 **이격도(disparity ratio)** 출력 — 표시된 이동평균 기간별 `종가/MA×100` 을 차트 하단에 한 줄 요약(`c 005930`·`w 005930`·`market chart`). 100 기준 색상(평균 위 빨강·아래 파랑), 100±5 이탈은 굵게 강조(과열·침체). `indicators.disparity`/`disparity_latest` 순수 함수
- REPL `clear`·`cl`·`cls` — 콜론 없이도 화면을 지웁니다 (기존 `:clear`·`:cls` 와 동일, 자동완성 노출)

## [0.4.6] - 2026-06-20

### Fixed
- `toss --version` 이 패키지 버전과 어긋나던 문제 — `importlib.metadata` 로 설치 버전을 읽도록 변경(하드코딩 제거, 향후 자동 동기화)

## [0.4.5] - 2026-06-20

### Added
- 명령 약어(prefix) 해석 — `toss o list`(=order list), `toss acc h`(=account holdings), `toss au k status`(=auth keychain status)처럼 고유 접두어로 호출 가능. 접두어가 모호하면(예: `a` = account/auth) 후보를 안내. 모든 그룹/하위 그룹에 적용

## [0.4.4] - 2026-06-20

### Added
- bash/zsh/fish 셸 자동완성 스크립트 (`completions/`) — `toss --install-completion` 또는 정적 스크립트 `source`. Typer 동적 완성으로 커맨드 변경에 자동 동기화

### Changed
- 내부: api 계층을 `ApiClient` 프로토콜로 통일하고 mypy 타입 체크를 CI 에 도입

## [0.4.3] - 2026-06-14

### Fixed
- 에러/경고 메시지의 대괄호(`[400 x]`·`[network-error]`)가 rich 마크업으로 오인돼 화면에서 사라지던 버그
- 네트워크 연결 실패·타임아웃 시 raw traceback 대신 친절한 한국어 에러 (단발 실행 exit 1)
- 상태 파일(토큰·sim·관심종목) 원자적 쓰기 — 부분 쓰기·동시 쓰기 손상 방지, 토큰은 교체 전 0o600 적용

## [0.4.2] - 2026-06-14

### Added
- `account holdings --sort daily|pl|value` — 일간 등락·수익률·평가금액 순 정렬 (REPL `p --sort daily`)

## [0.4.1] - 2026-06-14

### Fixed
- REPL 자동완성에 `:history` 와 베어 숏컷(`w` 대시보드·`c` 차트·`wl` 관심종목) 노출

### Changed
- 내부 리팩토링: 차트 지표를 `indicators.py` 순수 함수로 분리, `_render_chart`/`_render_overview` 패널별 헬퍼 분해
- 테스트 보강: API 래퍼(market_data·market_info·stock·account·order) 파라미터·계좌 헤더 전달 검증 (129 passed)

## [0.4.0] - 2026-06-14

### Added
- macOS Keychain 자격증명 백엔드 — `toss auth keychain set/status/clear`, 우선순위 env > .env > Keychain > toml (`.env` 평문 없이 어디서나 동작)

## [0.3.2] - 2026-06-13

### Added
- `account history` — 보유액 추이 차트 (현재 보유 수량 × 과거 종가로 근사 재구성), REPL `a hist`
- `holdings` 전체 조회 시 평가액을 `~/.toss-cli/portfolio_history.jsonl` 에 하루 1회 기록
- REPL 명령 기록 메뉴 `:history` + bash 스타일 재실행 `!42` · `!!` · `!o b`

## [0.3.1] - 2026-06-13

### Changed
- README(ko/en) 에 "왜 이 도구인가 — 공식 API 만 사용" 비교 섹션 — PyPI 페이지 반영용 문서 릴리스

## [0.3.0] - 2026-06-13
### Added
- `--csv` 전역 출력 (파이프/엑셀/에이전트용, 중첩 응답 평탄화)
- 주문 액션별 차단 게이트: `TOSS_NO_BUY` / `TOSS_NO_MODIFY` / `TOSS_NO_CANCEL` (기존 `TOSS_NO_SELL` 확장)
- 로컬 거래 ledger: 이 CLI 로 보낸 주문/정정/취소를 `~/.toss-cli/ledger.jsonl` 에 기록, `toss ledger show`
- 관심종목 그룹(폴더): `watchlist group create|rename|delete`, `add -g <그룹>`, 그룹별 시세판
- `AGENTS.md` — AI 에이전트 사용 규약

## [0.2.3] - 2026-06-13

### Added
- `wl` 관심종목 시세판 — 전일 대비 등락순 정렬, `-w` 실시간 갱신 (로컬 저장)
- `c <심볼> -P 1d` 오늘(분봉) 차트 프리셋

### Changed
- REPL 종료 UX — Ctrl-C 두 번, `/quit`·`/exit`·`q`, 실행 중 Ctrl-C 는 명령만 중단

## [0.2.2] - 2026-06-12

### Fixed
- sim 캔들 응답을 스펙(CandlePageResponse) 형태로 — sim 모드 차트/캔들 표 복구

## [0.2.1] - 2026-06-12

### Fixed
- requires-python ≥3.11 — `tomllib` 은 3.11 표준 라이브러리 (3.10 설치 깨짐 수정)

## [0.2.0] - 2026-06-12

### Added
- 터미널 캔들 차트: 이동평균·거래량·RSI·볼린저밴드·보유 평단선, `--watch` 실시간
- `w <심볼>` 종목 원샷 대시보드
- 보유종목 일간 손익, 전 조회 명령 rich 표 렌더링
- 주문 안전장치: 예상 금액 표시, 1억+ 사전 차단, KR 호가 단위 경고, 멱등키 자동 생성, `TOSS_NO_SELL`
- `order list --all` 페이지 자동 추적, `buying-power` KRW·USD 동시 조회
- GitHub Actions CI + PyPI Trusted Publishing

## [0.1.0] - 2026-06-12

### Added
- 최초 공개: 토스증권 공식 Open API 전체 래핑 (시세·종목·시장정보·계좌·주문)
- 대화형 REPL (숏컷·자동완성·히스토리), 시뮬레이션 모드
