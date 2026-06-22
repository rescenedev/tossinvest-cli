# tossinvest-cli

<p>
  <a href="https://pypi.org/project/tossinvest-cli/"><img src="https://img.shields.io/pypi/v/tossinvest-cli" alt="PyPI"></a>
  <a href="https://github.com/rescenedev/tossinvest-cli/actions/workflows/ci.yml"><img src="https://github.com/rescenedev/tossinvest-cli/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/pypi/pyversions/tossinvest-cli" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT">
  <a href="https://rescenedev.github.io/tossinvest-cli/"><img src="https://img.shields.io/badge/website-rescenedev.github.io-3182F6" alt="Website"></a>
  <a href="README.en.md"><img src="https://img.shields.io/badge/docs-English-blue" alt="English"></a>
</p>

토스증권 [Open API](https://developers.tossinvest.com/docs) 를 이용해 시세 조회부터 주문까지
처리하는 커맨드라인 도구입니다. (비공식)

> 🌐 **웹사이트:** <https://rescenedev.github.io/tossinvest-cli/> — 기능·명령어·릴리스 노트 한눈에.

## 왜 이 도구인가 — 공식 API 만 씁니다

토스증권 비공식 도구는 두 부류입니다: **공식 Open API 를 쓰는 것**과, 앱의
**비공개 API 를 역공학해서 쓰는 것**. 후자는 기능이 더 넓어 보이지만 대가가 있습니다.
이 도구는 **공식 Open API 만** 호출합니다.

| | **tossinvest-cli** | 내부 API 역공학 도구 |
|---|---|---|
| 데이터 출처 | 공식 Open API (콘솔에서 발급한 자격증명) | 앱 비공개 API |
| 약관·계정 리스크 | 공식 발급 경로 그대로 — **계정 제재 사유 없음** | 약관 위반 소지, 차단·제재 위험 |
| 인증 | OAuth2 client credentials (공식) | 앱 토큰 추출 등 비공식 |
| API 변경 시 | 공식 스펙 버저닝을 따라 안정적 | 예고 없이 깨질 수 있음 |
| 기능 범위 | 공식 표면 100% + 클라이언트 기능(차트·대시보드·관심종목·ledger) | 더 넓지만 전부 비공식 |

여기에 **실거래 도구로서의 안전장치**를 겹겹이 둡니다:
`--dry-run` 미리보기 → 확인 프롬프트 → 1억+ `--confirm-high-value` →
액션별 차단 게이트(`TOSS_NO_BUY/SELL/MODIFY/CANCEL`) → 멱등키 자동 생성 →
로컬 거래 ledger. 연습은 `--sim` 으로 계좌 없이.

공식 API 에 없는 수급·랭킹·AI 시그널·실시간 푸시는 **의도적으로** 지원하지 않습니다
([FAQ](#faq)). AI 에이전트(Claude Code 등)에서 도구로 쓰는 규약은 [AGENTS.md](AGENTS.md) 를 보세요.

> ⚠️ **실거래 주의** — 이 도구는 실제 계좌에 주문을 전송합니다. `order buy`/`sell`/`modify`/`cancel`
> 은 기본적으로 확인 프롬프트를 거치며, `--dry-run` 으로 전송 없이 요청 내용을 먼저 확인할 수 있습니다.

## 설치

```bash
uv tool install tossinvest-cli      # 또는: pip install tossinvest-cli
```

설치하면 `toss` 명령이 등록됩니다. (또는 `python -m toss_cli` 로도 실행 가능)

소스에서 개발 설치:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 셸 자동완성

`toss` 의 서브커맨드·옵션을 `<TAB>` 으로 자동완성합니다. 현재 셸을 자동 감지해 설정까지 마치려면:

```bash
toss --install-completion      # 적용하려면 셸 재시작 또는: exec $SHELL
toss --show-completion          # 스크립트 내용만 출력
```

bash/zsh/fish 정적 스크립트와 수동 설치 방법은 [`completions/`](completions/) 디렉터리를 참고하세요. 예) bash:

```bash
source completions/toss.bash    # 현재 셸에만 적용
```

> zsh 사용 중 자동완성이 갱신되지 않으면 캐시를 비우고 새 셸을 여세요: `rm -f ~/.zcompdump*; exec zsh`

### 명령 약어 (prefix)

고유하게 식별되는 접두어로 명령을 줄여 쓸 수 있습니다. 정확한 이름은 항상 우선합니다.

```bash
toss o list           # = toss order list
toss acc holdings     # = toss account holdings
toss au k status      # = toss auth keychain status
```

접두어가 여러 명령에 걸리면(예: `a` → account/auth) 후보를 보여 주고 멈춥니다.

## 설정

[토스증권 Open API 콘솔](https://developers.tossinvest.com)에서 클라이언트를 등록해
`client_id` / `client_secret` 을 발급받으세요.

`.env.example` 을 복사해 자격증명을 채웁니다:

```bash
cp .env.example .env
```

```dotenv
TOSS_CLIENT_ID=your-client-id
TOSS_CLIENT_SECRET=your-client-secret
TOSS_ACCOUNT_SEQ=1          # 선택: 기본 계좌
```

### macOS Keychain 에 안전 보관 (권장)

`.env` 평문 대신 자격증명을 **macOS Keychain 에 암호화 보관**할 수 있습니다.
한 번 저장하면 `.env` 없이 어느 디렉터리에서든 동작합니다.

```bash
toss auth keychain set       # client_id / client_secret 입력 (secret 은 가림)
toss auth keychain status    # 저장 여부 확인 (값은 노출 안 함)
toss auth keychain clear     # 삭제
```

설정 우선순위: **환경변수 > `.env`(현재 디렉터리) > macOS Keychain > `~/.toss-cli/config.toml`**.
토큰은 `~/.toss-cli/token.json` 에 캐시되어 만료 전까지 재사용됩니다(권한 600).
키 원문은 `auth status` 출력에서 마스킹되어 화면·로그에 드러나지 않습니다.

설정/토큰 상태 확인:

```bash
toss auth status      # 설정 확인 (시크릿 마스킹)
toss auth login       # 토큰 강제 발급
toss auth logout      # 토큰 캐시 삭제
```

## 대화형 셸 (REPL)

**`toss` 만 입력하면 바로 REPL 이 시작**됩니다. 매번 `toss ...` 로 새로 실행하는 대신,
한 번 진입해 토큰·연결을 세션 내내 재사용하며 명령만 입력합니다.

```bash
toss                      # 인자 없이 → REPL 시작
toss --sim                # 시뮬레이션 모드로 REPL 시작 (자격증명 불필요)
toss -a 1                 # 계좌 지정 후 REPL
toss repl                 # 명시적으로 REPL 시작
```

```text
SIM 토스증권 Open API REPL  계좌=1 · base=sim://local
toss> 005930                       # 베어 심볼 → 현재가
toss> 005930 100                   # 100주 시장가 매수
toss> 005930 -100                  # 100주 시장가 매도 (음수=매도)
toss> 005930 100 70000             # 100주 지정가(70000) 매수
toss> m p 005930                   # 숏컷: market price
toss> a h                          # 숏컷: account holdings
toss> order --help                 # 전체 옵션 도움말
toss> ?                            # 명령/숏컷 목록
toss> exit
```

### 숏컷

| 입력 | 동작 |
|---|---|
| `005930` | 현재가 조회 |
| `w 005930` | **종목 대시보드** — 시세·보유·차트·호가·유의사항 한 화면 |
| `wl` / `wl add 005930 AAPL` | **관심종목 시세판** — 전일 대비 등락순 정렬 (`wl -w 10` 실시간) |
| `c 005930` | 캔들 차트 (MA·거래량·평단선·이격도) |
| `005930 000660` | 여러 종목 현재가 |
| `005930 100` | 100주 **시장가 매수** |
| `005930 -100` | 100주 **시장가 매도** (음수=매도) |
| `005930 100 70000` | 100주 **지정가(70000) 매수** |
| `005930 100 -y` | 확인 없이 매수 |
| `p` | **보유 종목** (수량·평단·현재가·평가손익·수익률·매수일) |
| `p -s 005930` | 특정 종목만 |
| `p --sort daily` | 일간 등락순 정렬 (pl·value 도 가능) |
| `m p 005930` | `market price 005930` |
| `o b 005930 -q 10 -p 70000` | `order buy ...` |

그룹 약어: `m`=market, `s`=stock, `i`=info, `a`=account, `o`=order.
6자리 영숫자(005930, 0193T0)는 KR 종목코드, **대문자 티커(AAPL, TSLL)는 미국 종목**으로 인식됩니다.

### 메타 명령 / 동작

| 명령 | 설명 |
|---|---|
| `help` / `?` | 명령·숏컷 목록 |
| `:history [n]` | 명령 기록 목록 (번호 표시) — `!42`(번호)·`!!`(직전)·`!o b`(접두어)로 재실행, `Ctrl-R` 검색 |
| `:account <seq>` | 세션 계좌 변경 |
| `:json` | JSON 출력 토글 |
| `:tick [%]` | 모의 시세 이동 (sim 전용, 기본 +1%) → 손익 변화 확인 |
| `:reset` | 시뮬레이션 상태 초기화 (sim 전용) |
| `clear` / `cl` / `cls` / `:clear` | 화면 지우기 |
| `exit` / `/quit` / `q` / `Ctrl-D` / `Ctrl-C` 두 번 | 종료 |

- 모든 CLI 서브커맨드/옵션/`--help` 가 셸 안에서 동일하게 동작합니다.
- 잘못된 명령이나 API 오류가 나도 셸은 종료되지 않습니다.
- prompt_toolkit 기반 **명령 히스토리**(`~/.toss-cli/repl_history`)와 **자동완성** 지원.

> 토스 Open API 는 현재 REST 만 제공하며 WebSocket/실시간 푸시는 지원하지 않습니다.

## 시뮬레이션 모드

자격증명이 아직 없으면 **시뮬레이션 모드**로 모든 기능을 체험할 수 있습니다.
실제 API 를 호출하지 않고 결정적 모의 시세를 만들며, 주문은
`~/.toss-cli/sim_state.json` 에 저장돼 예수금·포지션·주문이 이어집니다.

```bash
toss --sim                       # sim 모드 REPL
toss --sim market price 005930   # sim 모드 단발 실행
```

- `.env` 에 `TOSS_SIM=1` 을 넣으면 자격증명 없이 `toss` 만 쳐도 sim 모드로 시작합니다.
- 자격증명이 아예 없을 때 `toss` 를 실행하면 자동으로 sim 모드로 전환됩니다.
- sim 모드의 주문은 확인 프롬프트 없이 즉시 접수되며 `[SIM]` 으로 표시됩니다.
- 시장가 주문은 즉시 체결, 지정가 주문은 미체결(PENDING) 상태로 보관됩니다.
- 매수 후 `:tick 5` 처럼 시세를 움직이면 `p`(보유 종목)에서 평가손익이 변합니다.
- `:reset` 으로 모의 예수금·포지션·주문을 초기화합니다.

```text
toss> 005930 100        # 100주 매수 (체결가 15,900)
toss> :tick 5           # 시세 +5%
toss> p                 # 005930 100주 · 평가손익 +80,000 (+5.03%) · 매수일 표시
```

> 실 API 의 보유종목 응답에는 매수일이 없어 실거래 모드에서 `매수일` 은 `-` 로 표시됩니다.

## 사용법 (단발 실행)

전역 옵션: `--account/-a <accountSeq>`, `--json`(원본 JSON 출력), `--version`.

### 시세 (market)

```bash
toss market price 005930 000660      # 현재가 (여러 종목)
toss market price 005930 --watch 5   # 5초 간격 폴링 갱신 (Ctrl-C 종료)
toss market orderbook 005930         # 호가
toss market trades 005930 -n 20      # 최근 체결
toss market candles 005930 -i 1d -n 30   # 캔들 (1m | 1d)
toss market overview 005930          # 종목 대시보드 (REPL: w 005930)
toss watchlist add 005930 AAPL       # 관심종목 등록 (로컬 저장, REPL: wl add)
toss watchlist show -w 10            # 관심종목 시세판 실시간 갱신 (REPL: wl -w 10)
toss market chart 005930 -P 3m       # 터미널 캔들 차트 (REPL: c 005930)
#   --ma 5,20,60   이동평균 · --bb 20  볼린저밴드 · --rsi 14  RSI 패널
#   --period/-P 1w|1m|3m|6m|1y · --watch N  실시간 갱신 · 보유 종목이면 평단선 표시
#   차트 하단에 이동평균 기간별 이격도(종가/MA×100)를 함께 표시 (--ma 기간 기준)
toss market limits 005930            # 상/하한가
```

### 종목 정보 (stock)

```bash
toss stock info 005930 AAPL          # 기본 정보
toss stock warnings 005930           # 매수 유의사항
```

### 시장 정보 (info)

```bash
toss info fx --base USD --quote KRW  # 환율
toss info calendar KR --date 2026-06-03   # 거래 캘린더 (KR | US)
```

### 계좌/자산 (account)

```bash
toss account list                    # 계좌 목록 (accountSeq 확인)
toss account holdings                # 보유 주식 (평가손익·일간 손익 포함)
toss account buying-power            # 매수 가능 금액 (KRW·USD 모두, -c 로 단일 통화)
toss account sellable 005930         # 매도 가능 수량
toss account history -P 3m           # 보유액 추이 차트 (REPL: a hist)
```

`history` 는 현재 보유 수량 × 과거 종가로 재구성한 **근사** 곡선입니다 (기간 중
매매·입출금 미반영, 환율은 현재값 고정). 또한 `holdings` 전체 조회 시 평가액이
`~/.toss-cli/portfolio_history.jsonl` 에 하루 1회 기록되어, 시간이 쌓이면 실제
추이 데이터가 됩니다.

### 주문 (order)

```bash
# 매수 — 지정가 (확인 프롬프트 후 전송)
toss order buy 005930 -q 10 -p 70000

# 전송 전 요청만 미리보기
toss order buy 005930 -q 10 -p 70000 --dry-run

# 시장가 매도, 확인 생략
toss order sell 005930 -q 10 -t MARKET -y

# 미국 주식 금액 기반 매수 (US MARKET 전용)
toss order buy AAPL --amount 100.5 -t MARKET

# 멱등성 키 — 미지정 시 자동 생성됩니다 (재전송 중복 방지). 직접 지정도 가능:
toss order buy 005930 -q 10 -p 70000 --id my-order-001

toss order list -s OPEN              # 미체결 주문
toss order list -s CLOSED --all      # 전체 페이지 자동 조회
toss order get <orderId>             # 주문 단건
toss order modify <orderId> -q 5 -p 71000   # 정정
toss order cancel <orderId>          # 취소
toss order commissions               # 매매 수수료
```

#### 주문 규칙 (스펙 기준 사전 검증)

- `--quantity` 와 `--amount` 는 동시 사용 불가, 하나는 필수.
- `LIMIT` 은 `--price` 필수, `MARKET` 은 `--price` 사용 불가.
- 금액 기반(`--amount`) 주문은 US `MARKET` 전용.
- 1억원 이상 주문은 `--confirm-high-value` 필요 (확인 표의 예상 금액으로 미리 안내).
- KR 지정가가 호가 단위에 안 맞으면 전송 전에 경고합니다 (ETF 등은 단위가 달라 차단하지 않음).
- `.env` 에 `TOSS_NO_SELL=1` 을 넣으면 실거래 매도가 차단됩니다 (sim·dry-run 은 허용).

### 로컬 거래 기록 (ledger)

이 CLI 로 보낸 주문/정정/취소는 `~/.toss-cli/ledger.jsonl` 에 자동 기록됩니다
(API 에 거래내역 엔드포인트가 없어 로컬 기록 — 다른 채널 거래는 포함 안 됨).

```bash
toss ledger show -n 50               # 최근 기록
toss --csv ledger show > trades.csv  # CSV 내보내기
```

### 출력 형식

모든 조회 명령에 전역 옵션으로 적용됩니다:

```bash
toss --json market price 005930      # 원본 JSON (jq 파이프)
toss --csv account holdings          # CSV (엑셀/스프레드시트)
```

## FAQ

**Q. 수급·실시간 인기 순위·AI 시그널·실시간 푸시는 왜 없나요?**
공식 Open API 에 해당 엔드포인트가 없습니다. 앱 내부 API 를 역공학하면 가능하지만
약관 위반과 계정 제재 위험이 있어 이 도구는 의도적으로 공식 표면만 사용합니다.

**Q. 토스 앱의 관심종목과 연동되나요?**
아니요. 공식 API 에 관심종목 엔드포인트가 없어 CLI 로컬(`~/.toss-cli/watchlist.json`)에
저장합니다. 그룹(폴더) 관리는 `toss watchlist group --help` 를 보세요.

**Q. 실거래가 무섭습니다.**
`--sim` 으로 전 기능을 모의로 쓸 수 있고, 실거래는 `--dry-run`(전송 없음) →
확인 프롬프트 → (1억+ 는 `--confirm-high-value`) 단계를 거칩니다. `.env` 에
`TOSS_NO_BUY/SELL/MODIFY/CANCEL=1` 로 액션별 차단도 가능합니다.

## 개발

```bash
pip install -e ".[dev]"
pytest
```

## 구조

```
src/toss_cli/
  config.py        설정 로딩 (env / .env / toml)
  auth.py          OAuth2 토큰 발급 + 캐싱
  client.py        HTTP 클라이언트 (인증/429 재시도/에러)
  errors.py        TossApiError 모델
  render.py        rich 표/JSON 출력
  api/             엔드포인트 그룹별 래퍼
  cli/             Typer 커맨드 그룹 (+ repl.py 대화형 셸)
```

전체 OpenAPI 스펙은 `docs/openapi.json` 에 보관되어 있습니다 (구현 기준 v1.1.1).

## 면책

비공식 도구입니다. 사용에 따른 거래 결과의 책임은 사용자에게 있습니다.
API 사양은 [공식 문서](https://developers.tossinvest.com/docs)를 따릅니다.
