"""시세 관련 커맨드: price, orderbook, trades, candles, limits."""

from __future__ import annotations

from typing import Any

import typer

from ..api import market_data
from .. import render
from ._common import open_client, output

app = typer.Typer(help="시세 조회 (현재가/호가/체결/캔들/상하한가)")


@app.command("price")
def price(
    ctx: typer.Context,
    symbols: list[str] = typer.Argument(..., help="종목 심볼 (예: 005930 AAPL)"),
) -> None:
    """현재가 조회 (여러 종목 가능)."""
    with open_client(ctx) as (client, _):
        data = market_data.get_prices(client, symbols)
    output(ctx, data, _render_prices)


@app.command("orderbook")
def orderbook(
    ctx: typer.Context,
    symbol: str = typer.Argument(..., help="종목 심볼"),
) -> None:
    """호가 조회."""
    with open_client(ctx) as (client, _):
        data = market_data.get_orderbook(client, symbol)
    output(ctx, data, lambda d: _render_orderbook(symbol, d))


@app.command("trades")
def trades(
    ctx: typer.Context,
    symbol: str = typer.Argument(..., help="종목 심볼"),
    count: int = typer.Option(None, "--count", "-n", help="조회 건수"),
) -> None:
    """최근 체결 내역 조회."""
    with open_client(ctx) as (client, _):
        data = market_data.get_trades(client, symbol, count)
    output(ctx, data, lambda d: render.print_json(d))


@app.command("candles")
def candles(
    ctx: typer.Context,
    symbol: str = typer.Argument(..., help="종목 심볼"),
    interval: str = typer.Option("1d", "--interval", "-i", help="1m | 1d"),
    count: int = typer.Option(None, "--count", "-n", help="조회 건수"),
    before: str = typer.Option(None, "--before", help="기준 시각 (ISO8601)"),
    adjusted: bool = typer.Option(None, "--adjusted/--no-adjusted", help="수정주가 여부"),
) -> None:
    """캔들 차트 조회."""
    with open_client(ctx) as (client, _):
        data = market_data.get_candles(client, symbol, interval, count, before, adjusted)
    output(ctx, data, lambda d: render.print_json(d))


@app.command("limits")
def limits(
    ctx: typer.Context,
    symbol: str = typer.Argument(..., help="종목 심볼"),
) -> None:
    """상/하한가 조회."""
    with open_client(ctx) as (client, _):
        data = market_data.get_price_limits(client, symbol)
    output(ctx, data, lambda d: render.print_json(d))


# -- renderers -----------------------------------------------------------
def _as_list(data: Any) -> list[dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    if isinstance(data, dict):
        return [data]
    return []


def _render_prices(data: Any) -> None:
    rows = [
        (p.get("symbol"), p.get("lastPrice"), p.get("currency"), p.get("timestamp"))
        for p in _as_list(data)
    ]
    render.table("현재가", ["종목", "현재가", "통화", "시각"], rows)


def _render_orderbook(symbol: str, data: dict) -> None:
    asks = data.get("asks", [])
    bids = data.get("bids", [])
    currency = data.get("currency", "")
    rows = []
    for i in range(max(len(asks), len(bids))):
        ask = asks[i] if i < len(asks) else {}
        bid = bids[i] if i < len(bids) else {}
        rows.append(
            (
                bid.get("volume", ""),
                bid.get("price", ""),
                ask.get("price", ""),
                ask.get("volume", ""),
            )
        )
    render.table(
        f"호가 {symbol} ({currency})",
        ["매수잔량", "매수호가", "매도호가", "매도잔량"],
        rows,
    )
