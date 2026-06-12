"""관심종목(watchlist) 커맨드: add, rm, show, clear.

심볼 목록은 ~/.toss-cli/watchlist.json 에 저장된다.
show 는 등록 종목 전체의 현재가와 전일 대비 등락률을 등락률 순으로 보여주는
시세판이며, --watch 로 실시간 갱신할 수 있다 (전일 종가는 시작 시 1회만 조회).
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any

import typer

from ..api import market_data
from ..config import CONFIG_DIR
from .. import render
from ._common import open_client, output

WATCHLIST_FILE = CONFIG_DIR / "watchlist.json"

app = typer.Typer(help="관심종목 시세판 (등록 종목 일괄 시세 · 등락률 정렬)")


def _load() -> list[str]:
    if not WATCHLIST_FILE.exists():
        return []
    try:
        data = json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return [s for s in data if isinstance(s, str)] if isinstance(data, list) else []


def _save(symbols: list[str]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    WATCHLIST_FILE.write_text(json.dumps(symbols, ensure_ascii=False), encoding="utf-8")


def _normalize(symbol: str) -> str:
    # KR 코드(숫자 시작)는 그대로, 미국 티커는 대문자로 통일
    return symbol if symbol[:1].isdigit() else symbol.upper()


@app.command("add")
def add(symbols: list[str] = typer.Argument(..., help="추가할 종목 심볼")) -> None:
    """관심종목 추가."""
    current = _load()
    added = [s for s in (_normalize(x) for x in symbols) if s not in current]
    _save(current + added)
    render.print_success(f"추가됨: {', '.join(added) or '(이미 전부 등록됨)'} · 총 {len(current) + len(added)}종목")


@app.command("rm")
def rm(symbols: list[str] = typer.Argument(..., help="제거할 종목 심볼")) -> None:
    """관심종목 제거."""
    targets = {_normalize(x) for x in symbols}
    remaining = [s for s in _load() if s not in targets]
    _save(remaining)
    render.print_success(f"제거 완료 · 남은 종목 {len(remaining)}개")


@app.command("clear")
def clear(
    yes: bool = typer.Option(False, "--yes", "-y", help="확인 생략"),
) -> None:
    """관심종목 전체 비우기."""
    if not yes and not typer.confirm("관심종목을 전부 비울까요?"):
        render.print_warning("취소했습니다.")
        raise typer.Exit(code=0)
    _save([])
    render.print_success("관심종목을 비웠습니다.")


@app.command("show")
def show(
    ctx: typer.Context,
    watch: float = typer.Option(None, "--watch", "-w", help="N초 간격 갱신 (Ctrl-C 종료)"),
) -> None:
    """관심종목 시세판 — 전일 대비 등락률 순 정렬."""
    symbols = _load()
    if not symbols:
        render.print_warning("관심종목이 없습니다. 예: toss watchlist add 005930 AAPL (REPL: wl add 005930)")
        return

    from .market import _watch  # 공용 watch 루프

    with open_client(ctx) as (client, _config):
        prev_closes = _fetch_prev_closes(client, symbols)  # 갱신 루프 밖에서 1회만

        def draw():
            prices = market_data.get_prices(client, symbols)  # 배치 1콜
            _render_board(symbols, prices, prev_closes)

        if watch:
            _watch(draw, max(1.0, watch))
            return
        prices = market_data.get_prices(client, symbols)
    output(ctx, prices, lambda _d: _render_board(symbols, _d, prev_closes))


def _fetch_prev_closes(client, symbols: list[str]) -> dict[str, Decimal]:
    """종목별 전일 종가. 실패하거나 이력이 없으면 생략."""
    closes: dict[str, Decimal] = {}
    for symbol in symbols:
        try:
            data = market_data.get_candles(client, symbol, "1d", 2, None, None)
            candles = (data or {}).get("candles", [])
            # 최신순: [0]=오늘(진행 중), [1]=전일. 이력이 1개뿐이면 시가 대비.
            raw = candles[1]["closePrice"] if len(candles) >= 2 else candles[0]["openPrice"]
            closes[symbol] = Decimal(raw)
        except Exception:
            continue
    return closes


def _render_board(symbols: list[str], prices: Any, prev_closes: dict[str, Decimal]) -> None:
    by_symbol = {p.get("symbol"): p for p in (prices or []) if isinstance(p, dict)}
    rows = []
    for symbol in symbols:
        p = by_symbol.get(symbol, {})
        last_raw = p.get("lastPrice")
        change = _change_pct(last_raw, prev_closes.get(symbol))
        rows.append((symbol, last_raw, p.get("currency"), change))

    rows.sort(key=lambda r: r[3] if r[3] is not None else Decimal("-9999"), reverse=True)
    table_rows = []
    for symbol, last_raw, currency, change in rows:
        if change is None:
            change_text = "[dim]-[/dim]"
        else:
            color = "red" if change > 0 else "blue" if change < 0 else "white"
            change_text = f"[{color}]{change:+.2f}%[/{color}]"
        table_rows.append((symbol, render.fmt_decimal(last_raw), change_text, currency))
    render.table("관심종목 (전일 대비 등락순)", ["종목", "현재가", "등락", "통화"], table_rows)


def _change_pct(last_raw: Any, prev: Decimal | None) -> Decimal | None:
    if not last_raw or not prev:
        return None
    try:
        return (Decimal(str(last_raw)) - prev) / prev * 100
    except (InvalidOperation, ZeroDivisionError):
        return None
