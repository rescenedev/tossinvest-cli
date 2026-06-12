# tossinvest-cli

토스증권 [Open API](https://developers.tossinvest.com/docs) 를 이용해 시세 조회부터 주문까지
처리하는 커맨드라인 도구입니다. (비공식)

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

설정 우선순위: **환경변수 > `.env`(현재 디렉터리) > `~/.toss-cli/config.toml`**.
토큰은 `~/.toss-cli/token.json` 에 캐시되어 만료 전까지 재사용됩니다(권한 600).

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
| `005930 000660` | 여러 종목 현재가 |
| `005930 100` | 100주 **시장가 매수** |
| `005930 -100` | 100주 **시장가 매도** (음수=매도) |
| `005930 100 70000` | 100주 **지정가(70000) 매수** |
| `005930 100 -y` | 확인 없이 매수 |
| `p` | **보유 종목** (수량·평단·현재가·평가손익·수익률·매수일) |
| `p -s 005930` | 특정 종목만 |
| `m p 005930` | `market price 005930` |
| `o b 005930 -q 10 -p 70000` | `order buy ...` |

그룹 약어: `m`=market, `s`=stock, `i`=info, `a`=account, `o`=order.
6자리 영숫자(005930, 0193T0)는 KR 종목코드, **대문자 티커(AAPL, TSLL)는 미국 종목**으로 인식됩니다.

### 메타 명령 / 동작

| 명령 | 설명 |
|---|---|
| `help` / `?` | 명령·숏컷 목록 |
| `:account <seq>` | 세션 계좌 변경 |
| `:json` | JSON 출력 토글 |
| `:tick [%]` | 모의 시세 이동 (sim 전용, 기본 +1%) → 손익 변화 확인 |
| `:reset` | 시뮬레이션 상태 초기화 (sim 전용) |
| `:clear` | 화면 지우기 |
| `exit` / `quit` / `Ctrl-D` | 종료 |

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
toss market chart 005930 -P 3m       # 터미널 캔들 차트 (REPL: c 005930)
#   --ma 5,20,60   이동평균 · --bb 20  볼린저밴드 · --rsi 14  RSI 패널
#   --period/-P 1w|1m|3m|6m|1y · --watch N  실시간 갱신 · 보유 종목이면 평단선 표시
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
```

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
