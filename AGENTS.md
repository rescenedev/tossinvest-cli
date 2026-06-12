# AGENTS.md — AI 에이전트용 사용 규약

이 문서는 Claude Code · Codex · Cursor 등 AI 에이전트가 `toss` CLI 를 도구로 사용할 때의
규약입니다. 사람이 읽어도 됩니다.

## 기본 원칙

- **모든 명령은 비대화형으로 동작합니다.** 단발 실행(`toss <group> <cmd>`)을 사용하세요.
  REPL(`toss` 단독 실행)은 사람 전용입니다.
- **기계가 읽을 출력**: `--json`(원본 응답) 또는 `--csv`(평탄화 표) 전역 옵션을 사용하세요.
  ```bash
  toss --json market price 005930 AAPL
  toss --csv account holdings
  toss --csv order list -s CLOSED --all
  ```
- **종료 코드**: `0` 성공 · `1` API 오류(TossApiError) · `2` 설정/검증 오류.
- 이 CLI 는 **토스증권 공식 Open API 만** 호출합니다. 내부(비공개) API 는 사용하지 않습니다.

## 주문 안전 규약 (중요)

실제 계좌에 주문이 전송됩니다. 에이전트는 다음을 따라야 합니다.

1. **항상 `--dry-run` 으로 먼저 검증**하고, 사용자의 명시적 승인 후에만 실제 전송하세요.
2. 실제 전송 시 `-y` 가 없으면 확인 프롬프트에서 멈춥니다(비대화형에선 실패).
   **사용자가 승인한 주문에만 `-y` 를 붙이세요.**
3. 멱등키는 자동 생성되지만, 재시도 로직이 있다면 `--id <키>` 로 직접 고정하세요 (10분 유효).
4. **액션 차단 게이트를 절대 우회하지 마세요.** `.env` 의 다음 플래그가 켜져 있으면
   해당 액션은 거부됩니다 (sim·dry-run 은 허용):
   - `TOSS_NO_BUY=1` · `TOSS_NO_SELL=1` · `TOSS_NO_MODIFY=1` · `TOSS_NO_CANCEL=1`
5. 1억원 이상 KR 주문은 `--confirm-high-value` 가 없으면 전송 자체가 차단됩니다.

## 연습은 시뮬레이션으로

`--sim` 을 붙이면 자격증명·실계좌 없이 전 명령이 모의로 동작합니다.
워크플로를 개발/테스트할 때는 반드시 sim 에서 먼저 돌리세요.

```bash
toss --sim order buy 005930 -q 10 -t MARKET -y   # 모의 체결
toss --sim --json account holdings                # 모의 보유
```

## 자주 쓰는 패턴

```bash
# 시세 → jq
toss --json market price 005930 | jq -r '.[0].lastPrice'

# 보유 전 종목 CSV
toss --csv account holdings > holdings.csv

# 이 CLI 로 보낸 주문 기록 (로컬 ledger)
toss --csv ledger show -n 100

# 관심종목 등록 후 등락 보드
toss watchlist add 005930 AAPL -g 메인
toss --json watchlist show
```

## 하지 말 것

- 사용자 승인 없는 실거래 주문 (특히 `-y` 자동 부착)
- `.env` / `~/.toss-cli/token.json` 내용을 출력하거나 외부로 전송
- 게이트 플래그(`TOSS_NO_*`) 제거·수정
- 짧은 간격 폴링 남용 (rate limit → CDN 차단)
