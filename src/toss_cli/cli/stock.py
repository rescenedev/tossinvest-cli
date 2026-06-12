"""종목 정보 커맨드: info, warnings."""

from __future__ import annotations

import typer

from ..api import stock
from .. import render
from ._common import open_client, output

app = typer.Typer(help="종목 정보 (기본정보/매수 유의사항)")


@app.command("info")
def info(
    ctx: typer.Context,
    symbols: list[str] = typer.Argument(..., help="종목 심볼 (예: 005930 AAPL)"),
) -> None:
    """종목 기본 정보 조회."""
    with open_client(ctx) as (client, _):
        data = stock.get_stocks(client, symbols)
    output(ctx, data, lambda d: render.print_json(d))


@app.command("warnings")
def warnings(
    ctx: typer.Context,
    symbol: str = typer.Argument(..., help="종목 심볼"),
) -> None:
    """매수 유의사항 조회."""
    with open_client(ctx) as (client, _):
        data = stock.get_stock_warnings(client, symbol)
    output(ctx, data, lambda d: render.print_json(d))
