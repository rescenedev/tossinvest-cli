# Changelog

형식: [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) · 버전: [SemVer](https://semver.org/lang/ko/)

## [Unreleased]

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
