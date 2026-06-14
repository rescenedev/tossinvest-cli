"""시세 관련 커맨드: price, orderbook, trades, candles, limits."""

from __future__ import annotations

from typing import Any

import typer

from ..api import market_data
from .. import render
from . import indicators
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
    watch: float = typer.Option(None, "--watch", "-w", help="N초 간격 폴링 갱신 (Ctrl-C 종료)"),
) -> None:
    """호가 조회."""
    with open_client(ctx) as (client, _):
        if watch:
            _watch(
                lambda: _render_orderbook(symbol, market_data.get_orderbook(client, symbol)),
                max(1.0, watch),
            )
            return
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
    rsi: int = typer.Option(None, "--rsi", help="RSI 기간 (예: 14)"),
    bb: int = typer.Option(None, "--bb", help="볼린저밴드 기간 (예: 20, 승수 2)"),
    period: str = typer.Option(None, "--period", "-P", help="기간 프리셋: 1d(오늘·분봉)|1w|1m|3m|6m|1y (일봉)"),
    watch: float = typer.Option(None, "--watch", "-w", help="N초 간격 갱신 (Ctrl-C 종료)"),
) -> None:
    """캔들 차트를 터미널에 그려서 추세 확인 (이동평균·거래량·RSI·볼린저·평단선)."""
    ma_periods = tuple(int(p) for p in ma.split(",") if p.strip().isdigit())
    if period:
        if period.lower() == "1d":  # 오늘 차트 = 1분봉 (count 상한 200 = 약 3시간 20분)
            interval, count = "1m", 200
        else:
            count = _period_to_count(period)
            interval = "1d"
    with open_client(ctx) as (client, config):
        avg_price = _holding_avg_price(client, config, symbol)

        def draw(data=None):
            _render_chart(
                symbol, interval,
                data if data is not None
                else market_data.get_candles(client, symbol, interval, count, before, None),
                ma_periods=ma_periods, show_volume=volume, avg_price=avg_price,
                rsi_period=rsi, bb_period=bb,
            )

        if watch:
            _watch(draw, max(1.0, watch))
            return
        data = market_data.get_candles(client, symbol, interval, count, before, None)
    output(ctx, data, lambda d: draw(d))


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


@app.command("overview")
def overview(
    ctx: typer.Context,
    symbol: str = typer.Argument(..., help="종목 심볼"),
    watch: float = typer.Option(None, "--watch", "-w", help="N초 간격 갱신 (Ctrl-C 종료)"),
) -> None:
    """종목 원샷 대시보드 — 현재가·차트·호가·보유·유의사항을 한 화면에 (REPL: w 005930)."""
    with open_client(ctx) as (client, config):
        def draw():
            _render_overview(symbol, _gather_overview(client, config, symbol))

        if watch:
            _watch(draw, max(1.0, watch))
            return
        parts = _gather_overview(client, config, symbol)
    output(ctx, parts, lambda _d: _render_overview(symbol, _d))


def _gather_overview(client, config, symbol: str) -> dict:
    """대시보드 데이터 수집. 일부 실패는 해당 섹션만 비운다."""
    from ..api import account as account_api
    from ..api import stock as stock_api

    parts: dict[str, Any] = {}

    def safe(key, fn):
        try:
            parts[key] = fn()
        except Exception:
            parts[key] = None

    safe("info", lambda: stock_api.get_stocks(client, [symbol]))
    safe("price", lambda: market_data.get_prices(client, [symbol]))
    safe("limits", lambda: market_data.get_price_limits(client, symbol))
    safe("candles", lambda: market_data.get_candles(client, symbol, "1d", 30, None, None))
    safe("orderbook", lambda: market_data.get_orderbook(client, symbol))
    safe("warnings", lambda: stock_api.get_stock_warnings(client, symbol))
    if config.account_seq is not None:
        safe("holdings", lambda: account_api.get_holdings(client, config.account_seq, symbol))
    return parts


def _render_overview(symbol: str, parts: dict) -> None:
    from .account import _currency_amounts, _percent, _signed  # 색/포맷 헬퍼 재사용

    # ── 헤더: 종목 정보 + 현재가 + 상하한 ──
    infos = parts.get("info") or []
    info = infos[0] if isinstance(infos, list) and infos else {}
    price_rows = parts.get("price") or []
    price = price_rows[0] if isinstance(price_rows, list) and price_rows else {}
    limits = parts.get("limits") or {}
    name = info.get("name") or symbol
    render.console.print(
        f"\n[bold]{name}[/bold] [dim]({symbol}) · {info.get('market', '-')}"
        f" · {info.get('securityType', '-')} · {price.get('currency', '')}[/dim]"
    )
    header = [("현재가", render.fmt_decimal(price.get("lastPrice")))]
    if limits.get("upperLimitPrice") or limits.get("lowerLimitPrice"):
        header.append(("상한 / 하한",
                       f"{render.fmt_decimal(limits.get('upperLimitPrice'))}"
                       f" / {render.fmt_decimal(limits.get('lowerLimitPrice'))}"))
    header.append(("시각", render.short_dt(price.get("timestamp"))))
    render.key_values("시세", header)

    # ── 보유 현황 (있으면) ──
    holding = None
    for item in (parts.get("holdings") or {}).get("items", []) if isinstance(parts.get("holdings"), dict) else []:
        if item.get("symbol") in (symbol, symbol.upper()):
            holding = item
            break
    if holding:
        hpl = holding.get("profitLoss", {})
        hdaily = holding.get("dailyProfitLoss", {})
        render.key_values(
            "보유",
            [
                ("수량", holding.get("quantity")),
                ("평단", render.fmt_decimal(holding.get("averagePurchasePrice"))),
                ("평가손익", f"{_signed(hpl.get('amount'))}  {_percent(hpl.get('rate'))}"),
                ("일간", _percent(hdaily.get("rate"))),
                ("평가금액", _currency_amounts(holding.get("marketValue", {}).get("amount"))),
            ],
        )

    # ── 미니 차트 (30일 · MA5/20, 거래량 생략) ──
    if parts.get("candles"):
        _render_chart(
            symbol, "1d", parts["candles"],
            ma_periods=(5, 20), show_volume=False,
            avg_price=holding.get("averagePurchasePrice") if holding else None,
        )

    # ── 호가 상위 5단 ──
    ob = parts.get("orderbook")
    if isinstance(ob, dict) and (ob.get("asks") or ob.get("bids")):
        trimmed = {**ob, "asks": (ob.get("asks") or [])[:5], "bids": (ob.get("bids") or [])[:5]}
        _render_orderbook(symbol, trimmed)

    # ── 매수 유의사항 ──
    warns = parts.get("warnings")
    if isinstance(warns, list) and warns:
        rows = [(w.get("warningType"), w.get("exchange"), w.get("startDate"), w.get("endDate"))
                for w in warns]
        render.table("매수 유의사항", ["유형", "거래소", "시작일", "종료일"], rows)


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

# 차트 지표 계산은 indicators 모듈(순수 함수)에 위임. 기존 이름은 호환 유지.
_sma = indicators.sma
_bollinger = indicators.bollinger
_rsi_series = indicators.rsi_series


def _period_to_count(period: str) -> int:
    """기간 프리셋 → 일봉 수. CLI 경계에서 ValueError 를 typer 에러로 변환."""
    try:
        return indicators.period_to_count(period)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from None


def _render_chart(
    symbol: str,
    interval: str,
    data: Any,
    *,
    ma_periods: tuple[int, ...] = (5, 20),
    show_volume: bool = True,
    avg_price: str | None = None,
    rsi_period: int | None = None,
    bb_period: int | None = None,
) -> None:
    """plotext 캔들스틱 + 이동평균 + 거래량 + RSI + 평단선. 상승=빨강, 하락=파랑 (한국식).

    패널마다 독립 figure 를 build/print 한다 — plotext 서브플롯은 clear_figure 후에도
    그리드 상태가 남는 버그가 있어, 패널을 분리해 순차 출력하는 방식이 안전하다.
    """
    candles = list(reversed((data or {}).get("candles", [])))  # 과거 → 최근
    if not candles:
        render.print_warning("캔들 데이터가 없습니다.")
        return

    dates, series, closes, volumes, date_form = _chart_series(candles, interval)
    draw_volume = show_volume and any(volumes) and len(candles) > 1
    rsi_values = _rsi_series(closes, rsi_period) if rsi_period else []
    width = min(render.console.width or 100, 110)

    # 패널 구성에 따라 높이를 터미널 한도(약 24행) 안으로 배분.
    panels = 1 + int(draw_volume) + int(bool(rsi_values))
    main_h, vol_h, rsi_h = {1: (22, 0, 0), 2: (15, 8, 8), 3: (12, 5, 6)}[panels]

    _draw_price_panel(symbol, interval, dates, series, closes, date_form,
                      width, main_h, ma_periods, bb_period, avg_price)
    if draw_volume:
        _draw_volume_panel(dates, series, volumes, date_form, width, vol_h)
    if rsi_values:
        _draw_rsi_panel(dates, rsi_values, rsi_period, date_form, width, rsi_h)
    _print_chart_summary(candles, avg_price)


def _chart_series(candles: list, interval: str):
    """캔들 목록 → (dates, OHLC series, closes, volumes, plotext date_form)."""
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
    date_form = "H:M" if interval == "1m" else "m/d"
    return dates, series, closes, volumes, date_form


def _draw_price_panel(symbol, interval, dates, series, closes, date_form,
                      width, height, ma_periods, bb_period, avg_price) -> None:
    """메인 가격 패널: 캔들 + 볼린저밴드 + 이동평균 + 보유 평단선."""
    import plotext as plt

    plt.clear_figure()
    plt.theme("clear")
    plt.date_form(date_form)
    plt.plotsize(width, height)
    plt.candlestick(dates, series, colors=["red", "blue"])

    if bb_period and len(closes) >= bb_period:  # 볼린저밴드 (기간 미달 시 생략)
        upper, lower = _bollinger(closes, bb_period, 2.0)
        plt.plot(dates[bb_period - 1 :], upper, label=f"BB{bb_period}", color="gray")
        plt.plot(dates[bb_period - 1 :], lower, color="gray")

    for period, color in zip(ma_periods, _MA_COLORS):  # 이동평균선 오버레이
        if period >= 2 and len(closes) >= period:
            plt.plot(dates[period - 1 :], _sma(closes, period), label=f"MA{period}", color=color)

    if avg_price:  # 보유 평단선 — 가격 범위 밖이면 차트가 짜부되므로 생략 (요약엔 표시)
        try:
            avg = float(avg_price)
            if min(series["Low"]) * 0.85 <= avg <= max(series["High"]) * 1.15:
                plt.hline(avg, "magenta")
        except ValueError:
            pass

    plt.title(f"{symbol}  {interval} x{len(dates)}")
    print(plt.build())


def _draw_volume_panel(dates, series, volumes, date_form, width, height) -> None:
    """거래량 패널 — 양봉 빨강 / 음봉 파랑."""
    import plotext as plt

    up = [v if series["Close"][i] >= series["Open"][i] else 0 for i, v in enumerate(volumes)]
    down = [v if series["Close"][i] < series["Open"][i] else 0 for i, v in enumerate(volumes)]
    plt.clear_figure()
    plt.theme("clear")
    plt.date_form(date_form)
    plt.plotsize(width, height)
    plt.bar(dates, up, color="red")
    plt.bar(dates, down, color="blue")
    plt.title("거래량")
    print(plt.build())


def _draw_rsi_panel(dates, rsi_values, rsi_period, date_form, width, height) -> None:
    """RSI 패널 — 70(과매수)/30(과매도) 기준선."""
    import plotext as plt

    plt.clear_figure()
    plt.theme("clear")
    plt.date_form(date_form)
    plt.plotsize(width, height)
    plt.plot(dates[rsi_period:], rsi_values, label=f"RSI{rsi_period}", color="cyan")
    plt.hline(70, "red")
    plt.hline(30, "blue")
    plt.ylim(0, 100)
    print(plt.build())


def _print_chart_summary(candles: list, avg_price: str | None) -> None:
    """차트 하단 한 줄 요약: 기간 등락 · 종가 · 고저 · (보유 시) 평단 대비."""
    from decimal import Decimal

    first, last = Decimal(candles[0]["closePrice"]), Decimal(candles[-1]["closePrice"])
    change = (last - first) / first * 100 if first else Decimal(0)
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
    if not data.get("upperLimitPrice") and not data.get("lowerLimitPrice"):
        render.console.print(
            "[dim]가격제한폭은 한국 시장 제도입니다 — 미국 주식 등은 상/하한가가 없습니다.[/dim]"
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
