"""계좌/자산 커맨드: list, holdings, buying-power, sellable."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

import typer

from ..api import account, order
from .. import render
from ._common import get_state, open_client, output

app = typer.Typer(help="계좌/자산 (목록/보유/매수가능금액/매도가능수량)")


@app.command("list")
def list_accounts(ctx: typer.Context) -> None:
    """계좌 목록 조회 (accountSeq 확인용)."""
    with open_client(ctx) as (client, _):
        data = account.get_accounts(client)
    output(ctx, data, _render_accounts)


@app.command("holdings")
def holdings(
    ctx: typer.Context,
    symbol: str = typer.Option(None, "--symbol", "-s", help="특정 종목만 조회"),
) -> None:
    """보유 주식 조회."""
    with open_client(ctx) as (client, config):
        data = account.get_holdings(client, config.require_account(), symbol)
    output(ctx, data, _render_holdings)


@app.command("buying-power")
def buying_power(
    ctx: typer.Context,
    currency: str = typer.Option("KRW", "--currency", "-c", help="KRW | USD"),
) -> None:
    """매수 가능 금액 조회."""
    with open_client(ctx) as (client, config):
        data = order.get_buying_power(client, config.require_account(), currency.upper())
    output(ctx, data, lambda d: render.key_values("매수 가능 금액", list(d.items())))


@app.command("sellable")
def sellable(
    ctx: typer.Context,
    symbol: str = typer.Argument(..., help="종목 심볼"),
) -> None:
    """판매 가능 수량 조회."""
    with open_client(ctx) as (client, config):
        data = order.get_sellable_quantity(client, config.require_account(), symbol)
    output(ctx, data, lambda d: render.key_values(f"매도 가능 수량 {symbol}", list(d.items())))


# -- renderers -----------------------------------------------------------
def _render_accounts(data: Any) -> None:
    accounts = data if isinstance(data, list) else data.get("accounts", [])
    rows = [
        (a.get("accountSeq"), a.get("accountNo"), a.get("accountType"))
        for a in accounts
    ]
    render.table("계좌 목록", ["accountSeq", "계좌번호", "유형"], rows)
    render.console.print(
        "[dim]거래/보유 조회 시 --account <accountSeq> 또는 TOSS_ACCOUNT_SEQ 로 지정하세요.[/dim]"
    )


def _fmt_decimal(value: Any) -> str:
    """천 단위 구분 기호를 넣은 숫자 문자열. 정수는 소수점 없이, 그 외 소수 2자리."""
    if value is None or value == "":
        return "[dim]-[/dim]"
    try:
        num = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return str(value)
    if num == num.to_integral_value():
        return f"{num:,.0f}"
    return f"{num:,.2f}"


def _signed(value: Any, suffix: str = "") -> str:
    """부호에 따라 색을 입힌 숫자 문자열. 양수=초록, 음수=빨강."""
    if value is None or value == "":
        return "[dim]-[/dim]"
    try:
        num = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return str(value)
    color = "green" if num > 0 else "red" if num < 0 else "white"
    sign = "+" if num > 0 else ""
    return f"[{color}]{sign}{_fmt_decimal(num)}{suffix}[/{color}]"


def _percent(value: Any) -> str:
    """소수비율(스펙 ProfitLoss.rate, 0.1077 = 10.77%) → 색 입힌 퍼센트 문자열."""
    if value is None or value == "":
        return "[dim]-[/dim]"
    try:
        num = Decimal(str(value)) * 100
    except (InvalidOperation, ValueError):
        return str(value)
    color = "green" if num > 0 else "red" if num < 0 else "white"
    return f"[{color}]{num:+.2f}%[/{color}]"


def _currency_amounts(value: Any, *, signed: bool = False) -> str:
    """통화별 금액 dict({'krw': ..., 'usd': ...}) 또는 단일 금액을 표시용 문자열로."""
    if not isinstance(value, dict):
        if value is None or value == "":
            return "[dim]-[/dim]"
        return _signed(value) if signed else _fmt_decimal(value)
    parts = []
    for currency, amount in value.items():
        if amount is None or amount == "":
            continue
        text = _signed(amount) if signed else _fmt_decimal(amount)
        parts.append(f"{text} {currency.upper()}")
    return " · ".join(parts) or "[dim]-[/dim]"


def _short_dt(value: Any) -> str:
    """ISO8601 → 'YYYY-MM-DD HH:MM' (없으면 -)."""
    if not value:
        return "[dim]-[/dim]"
    text = str(value).replace("T", " ")
    return text[:16]


def _render_holdings(data: Any) -> None:
    if not isinstance(data, dict):
        render.print_json(data)
        return
    pl = data.get("profitLoss", {})
    mv = data.get("marketValue", {})
    render.key_values(
        "보유 요약",
        [
            ("매입금액", _currency_amounts(data.get("totalPurchaseAmount"))),
            ("평가금액", _currency_amounts(mv.get("amount"))),
            ("평가손익", _currency_amounts(pl.get("amount"), signed=True)),
            ("수익률", _percent(pl.get("rate"))),
        ],
    )
    rows = []
    for item in data.get("items", []):
        ipl = item.get("profitLoss", {})
        mval = item.get("marketValue", {})
        rows.append(
            (
                item.get("symbol"),
                item.get("name"),
                item.get("quantity"),
                _fmt_decimal(item.get("averagePurchasePrice")),
                _fmt_decimal(item.get("lastPrice")),
                _fmt_decimal(mval) if (mval := mval.get("amount")) else None,
                _signed(ipl.get("amount")),
                _percent(ipl.get("rate")),
                _short_dt(item.get("purchasedAt")),
            )
        )
    if rows:
        render.table(
            "보유 종목",
            ["종목", "이름", "수량", "평단", "현재가", "평가금액", "평가손익", "수익률", "매수일"],
            rows,
        )
    else:
        render.print_warning("보유 종목이 없습니다.")
