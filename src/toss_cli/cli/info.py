"""시장 정보 커맨드: fx(환율), calendar(거래 캘린더)."""

from __future__ import annotations

import typer

from ..api import market_info
from .. import render
from ._common import open_client, output

app = typer.Typer(help="시장 정보 (환율/거래 캘린더)")


@app.command("fx")
def fx(
    ctx: typer.Context,
    base: str = typer.Option("USD", "--base", help="기준 통화"),
    quote: str = typer.Option("KRW", "--quote", help="상대 통화"),
    at: str = typer.Option(None, "--at", help="기준 시각 (ISO8601)"),
) -> None:
    """환율 조회."""
    with open_client(ctx) as (client, _):
        data = market_info.get_exchange_rate(client, base.upper(), quote.upper(), at)
    output(ctx, data, lambda d: render.key_values("환율", list(d.items()) if isinstance(d, dict) else []))


@app.command("calendar")
def calendar(
    ctx: typer.Context,
    market: str = typer.Argument("KR", help="KR | US"),
    date: str = typer.Option(None, "--date", help="조회 날짜 (YYYY-MM-DD)"),
) -> None:
    """거래 캘린더 조회."""
    market = market.upper()
    with open_client(ctx) as (client, _):
        if market == "US":
            data = market_info.get_us_calendar(client, date)
        else:
            data = market_info.get_kr_calendar(client, date)
    output(ctx, data, lambda d: _render_calendar(market, d))


# -- renderers -----------------------------------------------------------
def _flatten(value, prefix: str = "") -> list[tuple[str, str]]:
    """중첩 dict 를 'a.b.c' 키로 평탄화. 시각 문자열은 보기 좋게 축약."""
    rows: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            rows.extend(_flatten(child, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            rows.extend(_flatten(child, f"{prefix}[{i}]"))
    else:
        text = render.short_dt(value) if isinstance(value, str) and "T" in value else value
        rows.append((prefix, text))
    return rows


def _render_calendar(market: str, data) -> None:
    if not isinstance(data, dict):
        render.print_json(data)
        return
    render.key_values(f"거래 캘린더 {market}", _flatten(data))
