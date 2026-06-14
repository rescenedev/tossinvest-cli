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
    sort: str = typer.Option(
        None, "--sort", help="정렬: daily(일간 등락) | pl(수익률) | value(평가금액)"
    ),
) -> None:
    """보유 주식 조회. --sort 로 일간 등락·수익률·평가금액 순 정렬."""
    with open_client(ctx) as (client, config):
        data = account.get_holdings(client, config.require_account(), symbol)
    if symbol is None and not get_state(ctx).sim:
        _record_snapshot(data)  # 실계좌 전체 조회 시 하루 1회 평가액 기록
    if sort:
        data = _sort_holdings(data, sort)
    output(ctx, data, _render_holdings)


_SORT_KEYS = {
    "daily": lambda i: ("dailyProfitLoss", "rate"),
    "pl": lambda i: ("profitLoss", "rate"),
    "value": lambda i: ("marketValue", "amount"),
}


def _sort_holdings(data: Any, key: str) -> Any:
    """보유 항목을 지정 키(내림차순)로 정렬한 새 dict 반환. 잘못된 키면 원본 유지."""
    if key not in _SORT_KEYS or not isinstance(data, dict):
        if key not in _SORT_KEYS:
            render.print_warning(f"알 수 없는 정렬 키: {key} (daily | pl | value)")
        return data
    section, field = _SORT_KEYS[key]("")

    def metric(item: dict) -> Decimal:
        raw = (item.get(section) or {}).get(field)
        if isinstance(raw, dict):  # 통화별 dict 면 KRW 우선
            raw = raw.get("krw") or next(iter(raw.values()), None)
        try:
            return Decimal(str(raw))
        except (InvalidOperation, ValueError, TypeError):
            return Decimal("-1e30")

    items = sorted(data.get("items", []), key=metric, reverse=True)
    return {**data, "items": items}


def _snapshot_path():
    from ..config import CONFIG_DIR  # 테스트에서 CONFIG_DIR 패치 가능하도록 지연 참조

    return CONFIG_DIR / "portfolio_history.jsonl"


def _record_snapshot(data: Any) -> None:
    """평가액 일일 스냅샷을 로컬에 기록 (같은 날짜는 한 번만). 실패는 무시."""
    import json
    from datetime import date

    if not isinstance(data, dict):
        return
    try:
        path = _snapshot_path()
        today = date.today().isoformat()
        if path.exists() and f'"date": "{today}"' in path.read_text(encoding="utf-8"):
            return
        entry = {
            "date": today,
            "marketValue": (data.get("marketValue") or {}).get("amount"),
            "profitLoss": (data.get("profitLoss") or {}).get("amount"),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


@app.command("buying-power")
def buying_power(
    ctx: typer.Context,
    currency: str = typer.Option(None, "--currency", "-c", help="KRW | USD (미지정 시 둘 다)"),
) -> None:
    """매수 가능 금액 조회. 통화 미지정 시 KRW·USD 를 모두 조회."""
    currencies = [currency.upper()] if currency else ["KRW", "USD"]
    with open_client(ctx) as (client, config):
        results = [
            order.get_buying_power(client, config.require_account(), cur)
            for cur in currencies
        ]
    data = results[0] if currency else results
    output(ctx, data, lambda _d: _render_buying_power(results))


def _render_buying_power(results: list) -> None:
    rows = [
        (d.get("currency"), _fmt_decimal(d.get("cashBuyingPower")))
        for d in results if isinstance(d, dict)
    ]
    render.table("매수 가능 금액", ["통화", "현금 매수 가능"], rows)


@app.command("sellable")
def sellable(
    ctx: typer.Context,
    symbol: str = typer.Argument(..., help="종목 심볼"),
) -> None:
    """판매 가능 수량 조회."""
    with open_client(ctx) as (client, config):
        data = order.get_sellable_quantity(client, config.require_account(), symbol)
    output(ctx, data, lambda d: render.key_values(f"매도 가능 수량 {symbol}", list(d.items())))


@app.command("history")
def history(
    ctx: typer.Context,
    period: str = typer.Option("3m", "--period", "-P", help="1w|1m|3m|6m|1y"),
) -> None:
    """보유액 추이 (근사) — 현재 보유 수량 × 과거 종가로 재구성한 평가액 곡선.

    기간 중 매매·입출금은 반영되지 않으며, 환율은 현재값으로 고정 환산합니다.
    """
    from ..api import market_data, market_info
    from .market import _period_to_count

    count = _period_to_count(period)
    with open_client(ctx) as (client, config):
        holdings = account.get_holdings(client, config.require_account(), None)
        items = [i for i in (holdings or {}).get("items", []) if Decimal(i.get("quantity", "0")) > 0]
        if not items:
            render.print_warning("보유 종목이 없습니다.")
            return
        try:
            fx = market_info.get_exchange_rate(client, "USD", "KRW", None)
            usdkrw = Decimal(str(fx.get("rate", "1350")))
        except Exception:
            usdkrw = Decimal("1350")
        candles_by_symbol = {}
        for item in items:
            try:
                data = market_data.get_candles(client, item["symbol"], "1d", count, None, None)
                candles_by_symbol[item["symbol"]] = (data or {}).get("candles", [])
            except Exception:
                candles_by_symbol[item["symbol"]] = []
    dates, values = build_value_series(items, candles_by_symbol, usdkrw=usdkrw)
    output(ctx, {"dates": dates, "valuesKrw": [str(v) for v in values]},
           lambda _d: _render_history(dates, values, usdkrw, period))


def build_value_series(
    items: list, candles_by_symbol: dict, *, usdkrw: Decimal
) -> tuple[list[str], list[Decimal]]:
    """일자별 포트폴리오 평가액(KRW 환산) 시계열.

    종목별 종가를 날짜로 정렬해 합산한다. 휴장일은 직전 종가로 forward-fill,
    이력이 짧은 종목은 첫 종가로 backfill 해 곡선을 끊지 않는다.
    """
    closes: dict[str, dict[str, Decimal]] = {}
    all_dates: set[str] = set()
    for item in items:
        symbol = item["symbol"]
        by_date = {}
        for c in candles_by_symbol.get(symbol, []):
            date = str(c.get("timestamp", ""))[:10]
            try:
                by_date[date] = Decimal(str(c["closePrice"]))
            except Exception:
                continue
        if by_date:
            closes[symbol] = by_date
            all_dates.update(by_date)

    dates = sorted(all_dates)
    values: list[Decimal] = []
    last: dict[str, Decimal] = {}
    first_close = {s: d[min(d)] for s, d in closes.items()}
    for date in dates:
        total = Decimal(0)
        for item in items:
            symbol = item["symbol"]
            if symbol not in closes:
                continue
            price = closes[symbol].get(date) or last.get(symbol) or first_close[symbol]
            last[symbol] = price
            value = Decimal(item["quantity"]) * price
            if item.get("currency") == "USD":
                value *= usdkrw
            total += value
        values.append(total)
    return dates, values


def _render_history(dates: list[str], values: list, usdkrw: Decimal, period: str) -> None:
    import plotext as plt

    if not dates:
        render.print_warning("계산할 시세 이력이 없습니다.")
        return
    plt.clear_figure()
    plt.theme("clear")
    plt.date_form("m/d")
    plt.plotsize(min(render.console.width or 100, 110), 18)
    xs = [d[5:].replace("-", "/") for d in dates]
    plt.plot(xs, [float(v) for v in values], color="cyan")
    plt.title(f"보유액 추이 (근사) · {period}")
    print(plt.build())

    first, last_v = values[0], values[-1]
    diff = last_v - first
    pct = diff / first * 100 if first else Decimal(0)
    color = "red" if diff > 0 else "blue" if diff < 0 else "white"
    render.console.print(
        f"{dates[0]} → {dates[-1]} · "
        f"{_fmt_decimal(first)} → {_fmt_decimal(last_v)} KRW · "
        f"[{color}]{'+' if diff > 0 else ''}{_fmt_decimal(diff)} ({pct:+.2f}%)[/{color}]"
    )
    render.console.print(
        "[dim]현재 보유 수량 기준 재구성 — 기간 중 매매·입출금 미반영, "
        f"환율은 현재값({_fmt_decimal(usdkrw)}원) 고정.[/dim]"
    )


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


_fmt_decimal = render.fmt_decimal


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
    daily = data.get("dailyProfitLoss", {})
    render.key_values(
        "보유 요약",
        [
            ("매입금액", _currency_amounts(data.get("totalPurchaseAmount"))),
            ("평가금액", _currency_amounts(mv.get("amount"))),
            ("평가손익", _currency_amounts(pl.get("amount"), signed=True)),
            ("수익률", _percent(pl.get("rate"))),
            ("일간 손익", f"{_currency_amounts(daily.get('amount'), signed=True)}  {_percent(daily.get('rate'))}"),
        ],
    )
    rows = []
    for item in data.get("items", []):
        ipl = item.get("profitLoss", {})
        idaily = item.get("dailyProfitLoss", {})
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
                _percent(idaily.get("rate")),
                _short_dt(item.get("purchasedAt")),
            )
        )
    if rows:
        render.table(
            "보유 종목",
            ["종목", "이름", "수량", "평단", "현재가", "평가금액", "평가손익", "수익률", "일간", "매수일"],
            rows,
        )
    else:
        render.print_warning("보유 종목이 없습니다.")
