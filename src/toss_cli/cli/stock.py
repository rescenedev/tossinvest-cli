"""종목 정보 커맨드: info, warnings."""

from __future__ import annotations

import typer

from ..api import stock
from .. import render
from ._alias import AliasGroup
from ._common import open_client, output

app = typer.Typer(help="종목 정보 (기본정보/매수 유의사항)", cls=AliasGroup)
@app.command("info")
def info(
    ctx: typer.Context,
    symbols: list[str] = typer.Argument(..., help="종목 심볼 (예: 005930 AAPL)"),
) -> None:
    """종목 기본 정보 조회."""
    with open_client(ctx) as (client, _):
        data = stock.get_stocks(client, symbols)
    output(ctx, data, _render_infos)


@app.command("warnings")
def warnings(
    ctx: typer.Context,
    symbol: str = typer.Argument(..., help="종목 심볼"),
) -> None:
    """매수 유의사항 조회."""
    with open_client(ctx) as (client, _):
        data = stock.get_stock_warnings(client, symbol)
    output(ctx, data, lambda d: _render_warnings(symbol, d))


# -- renderers -----------------------------------------------------------
def _render_infos(data) -> None:
    items = data if isinstance(data, list) else [data]
    rows = [
        (s.get("symbol"), s.get("name"), s.get("market"), s.get("securityType"),
         s.get("currency"), s.get("listDate"), s.get("status"))
        for s in items if isinstance(s, dict)
    ]
    if not rows:
        render.print_warning("종목 정보가 없습니다.")
        return
    render.table("종목 정보", ["심볼", "이름", "시장", "유형", "통화", "상장일", "상태"], rows)


def _render_warnings(symbol: str, data) -> None:
    items = data if isinstance(data, list) else []
    if not items:
        render.print_warning(f"{symbol}: 매수 유의사항이 없습니다.")
        return
    rows = [
        (w.get("warningType"), w.get("exchange"), w.get("startDate"), w.get("endDate"))
        for w in items
    ]
    render.table(f"매수 유의사항 {symbol}", ["유형", "거래소", "시작일", "종료일"], rows)
