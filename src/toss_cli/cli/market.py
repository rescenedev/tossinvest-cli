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
    watch: float = typer.Option(None, "--watch", "-w", help="N초 간격 폴링 갱신 (Ctrl-C 종료)"),
) -> None:
    """현재가 조회 (여러 종목 가능)."""
    with open_client(ctx) as (client, _):
        if watch:
            _watch_prices(client, symbols, max(1.0, watch))
            return
        data = market_data.get_prices(client, symbols)
    output(ctx, data, _render_prices)


def _watch_prices(client, symbols: list[str], interval: float) -> None:
    """현재가를 주기적으로 다시 그린다. Ctrl-C 로 종료."""
    _watch(lambda: _render_prices(market_data.get_prices(client, symbols)), interval)


def _watch(draw, interval: float) -> None:
    """draw() 를 주기적으로 다시 실행. Ctrl-C 로 종료."""
    import time

    try:
        while True:
            render.console.clear()
            draw()
            render.console.print(f"[dim]{interval:g}초 간격 갱신 중 — Ctrl-C 로 종료[/dim]")
            time.sleep(interval)
    except KeyboardInterrupt:
        render.console.print("[dim]watch 종료[/dim]")


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
    output(ctx, data, _render_trades)


@app.command("candles")
def candles(
    ctx: typer.Context,
    symbol: str = typer.Argument(..., help="종목 심볼"),
    interval: str = typer.Option("1d", "--interval", "-i", help="1m | 1d"),
    count: int = typer.Option(30, "--count", "-n", help="조회 건수"),
    before: str = typer.Option(None, "--before", help="기준 시각 (ISO8601)"),
    adjusted: bool = typer.Option(None, "--adjusted/--no-adjusted", help="수정주가 여부"),
) -> None:
    """캔들 차트 조회."""
    with open_client(ctx) as (client, _):
        data = market_data.get_candles(client, symbol, interval, count, before, adjusted)
    output(ctx, data, _render_candles)


@app.command("chart")
def chart(
    ctx: typer.Context,
    symbol: str = typer.Argument(..., help="종목 심볼"),
    interval: str = typer.Option("1d", "--interval", "-i", help="1m | 1d"),
    count: int = typer.Option(60, "--count", "-n", help="캔들 수"),
    before: str = typer.Option(None, "--before", help="기준 시각 (ISO8601)"),
    ma: str = typer.Option("5,20", "--ma", help="이동평균 기간 (쉼표 구분, 빈 문자열이면 끔)"),
    volume: bool = typer.Option(True, "--volume/--no-volume", help="거래량 서브차트"),
    watch: float = typer.Option(None, "--watch", "-w", help="N초 간격 갱신 (Ctrl-C 종료)"),
) -> None:
    """캔들 차트를 터미널에 그려서 추세 확인 (이동평균·거래량·평단선 포함)."""
    ma_periods = tuple(int(p) for p in ma.split(",") if p.strip().isdigit())
    with open_client(ctx) as (client, config):
        avg_price = _holding_avg_price(client, config, symbol)

        def fetch():
            return market_data.get_candles(client, symbol, interval, count, before, None)

        if watch:
            _watch(lambda: _render_chart(
                symbol, interval, fetch(),
                ma_periods=ma_periods, show_volume=volume, avg_price=avg_price,
            ), max(1.0, watch))
            return
        data = fetch()
    output(ctx, data, lambda d: _render_chart(
        symbol, interval, d, ma_periods=ma_periods, show_volume=volume, avg_price=avg_price))


def _holding_avg_price(client, config, symbol: str) -> str | None:
    """보유 종목이면 평단가 반환 (계좌 미설정/미보유/조회 실패 시 None)."""
    from ..api import account as account_api

    if config.account_seq is None:
        return None
    try:
        holdings = account_api.get_holdings(client, config.account_seq, symbol)
        for item in (holdings or {}).get("items", []):
            if item.get("symbol") == symbol.upper() or item.get("symbol") == symbol:
                return item.get("averagePurchasePrice")
    except Exception:
        return None
    return None


@app.command("limits")
def limits(
    ctx: typer.Context,
    symbol: str = typer.Argument(..., help="종목 심볼"),
) -> None:
    """상/하한가 조회."""
    with open_client(ctx) as (client, _):
        data = market_data.get_price_limits(client, symbol)
    output(ctx, data, lambda d: _render_limits(symbol, d))


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


def _render_trades(data: Any) -> None:
    rows = [
        (render.short_dt(t.get("timestamp")), render.fmt_decimal(t.get("price")),
         render.fmt_decimal(t.get("volume")), t.get("currency"))
        for t in _as_list(data)
    ]
    if not rows:
        render.print_warning("체결 내역이 없습니다.")
        return
    render.table("최근 체결", ["시각", "가격", "수량", "통화"], rows)


def _render_candles(data: Any) -> None:
    candles = data.get("candles", []) if isinstance(data, dict) else (data or [])
    rows = [
        (render.short_dt(c.get("timestamp")),
         render.fmt_decimal(c.get("openPrice")), render.fmt_decimal(c.get("highPrice")),
         render.fmt_decimal(c.get("lowPrice")), render.fmt_decimal(c.get("closePrice")),
         render.fmt_decimal(c.get("volume")))
        for c in candles
    ]
    if not rows:
        render.print_warning("캔들 데이터가 없습니다.")
        return
    render.table("캔들", ["시각", "시가", "고가", "저가", "종가", "거래량"], rows)
    if isinstance(data, dict) and data.get("nextBefore"):
        render.console.print(f"[dim]다음 페이지: --before {data['nextBefore']}[/dim]")


_MA_COLORS = ("orange", "yellow", "green", "cyan")


def _render_chart(
    symbol: str,
    interval: str,
    data: Any,
    *,
    ma_periods: tuple[int, ...] = (5, 20),
    show_volume: bool = True,
    avg_price: str | None = None,
) -> None:
    """plotext 캔들스틱 + 이동평균 + 거래량 + 평단선. 상승=빨강, 하락=파랑 (한국식)."""
    from decimal import Decimal

    import plotext as plt

    candles = list(reversed((data or {}).get("candles", [])))  # 과거 → 최근
    if not candles:
        render.print_warning("캔들 데이터가 없습니다.")
        return

    stamps = [render.short_dt(c.get("timestamp")) for c in candles]  # "YYYY-MM-DD HH:MM"
    if interval == "1m":
        dates = [s[11:16] for s in stamps]                   # "HH:MM"
    else:
        dates = [s[5:10].replace("-", "/") for s in stamps]  # "MM/DD"
    closes = [float(c["closePrice"]) for c in candles]
    series = {
        "Open": [float(c["openPrice"]) for c in candles],
        "High": [float(c["highPrice"]) for c in candles],
        "Low": [float(c["lowPrice"]) for c in candles],
        "Close": closes,
    }
    volumes = [float(c.get("volume") or 0) for c in candles]
    draw_volume = show_volume and any(volumes) and len(candles) > 1
    width = min(render.console.width or 100, 110)
    date_form = "H:M" if interval == "1m" else "m/d"

    plt.clear_figure()
    if draw_volume:
        plt.subplots(2, 1)
        plt.subplot(1, 1)
        plt.subplot(1, 1).plotsize(width, 15)

    plt.theme("clear")
    plt.date_form(date_form)
    plt.candlestick(dates, series, colors=["red", "blue"])

    # 이동평균선 오버레이 (기간이 캔들 수보다 길면 생략)
    for period, color in zip(ma_periods, _MA_COLORS):
        if period >= 2 and len(closes) >= period:
            ma_values = [
                sum(closes[i - period + 1 : i + 1]) / period
                for i in range(period - 1, len(closes))
            ]
            plt.plot(dates[period - 1 :], ma_values, label=f"MA{period}", color=color)

    # 보유 평단선 — 가격 범위에서 크게 벗어나면 차트가 짜부되므로 생략 (요약에는 표시)
    if avg_price:
        try:
            avg = float(avg_price)
            lows, highs = min(series["Low"]), max(series["High"])
            if lows * 0.85 <= avg <= highs * 1.15:
                plt.hline(avg, "magenta")
        except ValueError:
            pass

    first, last = Decimal(candles[0]["closePrice"]), Decimal(candles[-1]["closePrice"])
    change = (last - first) / first * 100 if first else Decimal(0)
    plt.title(f"{symbol}  {interval} x{len(candles)}")

    if draw_volume:
        # 거래량 서브차트 — 양봉 빨강 / 음봉 파랑
        up = [v if series["Close"][i] >= series["Open"][i] else 0 for i, v in enumerate(volumes)]
        down = [v if series["Close"][i] < series["Open"][i] else 0 for i, v in enumerate(volumes)]
        plt.subplot(2, 1)
        plt.subplot(2, 1).plotsize(width, 8)
        plt.theme("clear")
        plt.date_form(date_form)
        plt.bar(dates, up, color="red")
        plt.bar(dates, down, color="blue")
        plt.title("거래량")

    print(plt.build())

    high = max(Decimal(c["highPrice"]) for c in candles)
    low = min(Decimal(c["lowPrice"]) for c in candles)
    color = "red" if change > 0 else "blue" if change < 0 else "white"
    summary = (
        f"기간 등락 [{color}]{change:+.2f}%[/{color}]"
        f" · 종가 {render.fmt_decimal(first)} → {render.fmt_decimal(last)}"
        f" · 고가 {render.fmt_decimal(high)} · 저가 {render.fmt_decimal(low)}"
    )
    if avg_price:
        diff = (last - Decimal(avg_price)) / Decimal(avg_price) * 100
        dcolor = "red" if diff > 0 else "blue" if diff < 0 else "white"
        summary += (
            f" · [magenta]평단 {render.fmt_decimal(avg_price)}[/magenta]"
            f" ([{dcolor}]{diff:+.2f}%[/{dcolor}])"
        )
    render.console.print(summary)


def _render_limits(symbol: str, data: dict) -> None:
    render.key_values(
        f"상/하한가 {symbol}",
        [
            ("상한가", render.fmt_decimal(data.get("upperLimitPrice"))),
            ("하한가", render.fmt_decimal(data.get("lowerLimitPrice"))),
            ("통화", data.get("currency")),
            ("기준시각", render.short_dt(data.get("timestamp"))),
        ],
    )


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
