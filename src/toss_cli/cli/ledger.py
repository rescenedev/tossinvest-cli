"""로컬 거래 ledger: CLI 가 전송한 주문/정정/취소를 기록·조회.

API 에 거래내역(ledger) 엔드포인트가 없어, 이 CLI 를 거친 액션을
~/.toss-cli/ledger.jsonl 에 한 줄씩(JSON Lines) 누적한다.
다른 채널(앱 등)에서 한 거래는 포함되지 않는다.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import typer

from ..config import CONFIG_DIR
from .. import render
from ._common import output

LEDGER_FILE = CONFIG_DIR / "ledger.jsonl"

app = typer.Typer(help="로컬 거래 기록 (이 CLI 로 보낸 주문/정정/취소)")


def record(action: str, *, sim: bool, **fields: Any) -> None:
    """ledger 에 한 건 기록. 기록 실패가 거래 흐름을 깨지 않도록 조용히 무시."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "action": action,
        "mode": "sim" if sim else "live",
        **{k: v for k, v in fields.items() if v is not None},
    }
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with LEDGER_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def load(limit: int | None = None) -> list[dict]:
    if not LEDGER_FILE.exists():
        return []
    entries: list[dict] = []
    for line in LEDGER_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries[-limit:] if limit else entries


@app.command("show")
def show(
    ctx: typer.Context,
    limit: int = typer.Option(30, "--limit", "-n", help="최근 N건"),
    symbol: str = typer.Option(None, "--symbol", "-s", help="특정 종목만"),
) -> None:
    """기록 조회 (최근순). --csv / --json 으로 내보내기."""
    entries = load()
    if symbol:
        entries = [e for e in entries if e.get("symbol") == symbol]
    entries = entries[-limit:]
    output(ctx, entries, _render_ledger)


@app.command("clear")
def clear(yes: bool = typer.Option(False, "--yes", "-y", help="확인 생략")) -> None:
    """기록 전체 삭제."""
    if not yes and not typer.confirm("로컬 거래 기록을 전부 삭제할까요?"):
        render.print_warning("취소했습니다.")
        raise typer.Exit(code=0)
    if LEDGER_FILE.exists():
        LEDGER_FILE.unlink()
    render.print_success("거래 기록을 삭제했습니다.")


def _render_ledger(entries: list) -> None:
    if not entries:
        render.print_warning("기록이 없습니다. (이 CLI 로 보낸 주문만 기록됩니다)")
        return
    rows = [
        (
            render.short_dt(e.get("ts")),
            e.get("mode"),
            e.get("action"),
            e.get("symbol"),
            e.get("side"),
            e.get("quantity") or e.get("orderAmount"),
            render.fmt_decimal(e.get("price")) if e.get("price") else "-",
            e.get("orderId"),
        )
        for e in reversed(entries)
    ]
    render.table(
        "거래 기록 (이 CLI 경유, 최근순)",
        ["시각(UTC)", "모드", "액션", "종목", "방향", "수량/금액", "가격", "orderId"],
        rows,
    )
