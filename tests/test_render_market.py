"""시세/종목/캘린더 표 렌더링 테스트 (raw JSON 덤프 → rich 표)."""

from toss_cli import render
from toss_cli.cli.info import _render_calendar
from toss_cli.cli.market import _render_candles, _render_limits, _render_trades
from toss_cli.cli.stock import _render_infos, _render_warnings


def _capture(fn, *args) -> str:
    with render.console.capture() as cap:
        fn(*args)
    return cap.get()


def test_trades_table():
    out = _capture(_render_trades, [
        {"price": "324500", "volume": "10", "timestamp": "2026-06-12T19:59:59.000+09:00", "currency": "KRW"},
    ])
    assert "체결" in out and "324,500" in out


def test_candles_table_with_next_hint():
    out = _capture(_render_candles, {
        "candles": [{"timestamp": "2026-06-12T00:00:00.000+09:00", "openPrice": "313000",
                     "highPrice": "339000", "lowPrice": "313000", "closePrice": "324500",
                     "volume": "60357743", "currency": "KRW"}],
        "nextBefore": "2026-06-10T00:00:00.000+09:00",
    })
    assert "324,500" in out and "--before" in out


def test_limits_key_values():
    out = _capture(_render_limits, "005930", {
        "timestamp": "2026-06-12T20:50:33.869+09:00",
        "upperLimitPrice": "421500", "lowerLimitPrice": "227500", "currency": "KRW",
    })
    assert "상한가" in out and "421,500" in out


def test_stock_info_table():
    out = _capture(_render_infos, [{
        "symbol": "005930", "name": "삼성전자", "market": "KOSPI", "securityType": "STOCK",
        "currency": "KRW", "listDate": "1975-06-11", "status": "ACTIVE",
    }])
    assert "삼성전자" in out and "KOSPI" in out


def test_stock_warnings_empty():
    out = _capture(_render_warnings, "005930", [])
    assert "없" in out  # 유의사항 없음


def test_stock_warnings_table():
    out = _capture(_render_warnings, "005930", [
        {"warningType": "VI_STATIC", "exchange": "KRX", "startDate": "2026-06-01", "endDate": None},
    ])
    assert "VI_STATIC" in out and "KRX" in out


def test_calendar_flattened():
    out = _capture(_render_calendar, "KR", {
        "today": {"date": "2026-06-12", "integrated": {
            "preMarket": {"startTime": "2026-06-12T08:00:00.000+09:00"},
        }},
    })
    assert "today.date" in out and "2026-06-12" in out


def test_watch_prices_renders_until_interrupt(monkeypatch):
    from toss_cli.cli import market as market_cli

    calls = {"n": 0}
    monkeypatch.setattr(market_cli.market_data, "get_prices",
                        lambda _c, _s: [{"symbol": "005930", "lastPrice": "1", "currency": "KRW"}])
    def fake_sleep(_):
        calls["n"] += 1
        raise KeyboardInterrupt
    import time
    monkeypatch.setattr(time, "sleep", fake_sleep)
    out = _capture(market_cli._watch_prices, None, ["005930"], 1.0)
    assert calls["n"] == 1 and "watch 종료" in out


def test_chart_renders_candlestick(capsys):
    from toss_cli.cli.market import _render_chart

    _render_chart("005930", "1d", {"candles": [
        {"timestamp": "2026-06-12T00:00:00", "openPrice": "313", "highPrice": "339",
         "lowPrice": "313", "closePrice": "324"},
        {"timestamp": "2026-06-10T00:00:00", "openPrice": "290", "highPrice": "300",
         "lowPrice": "288", "closePrice": "292"},
    ]})
    out = capsys.readouterr().out
    assert "005930" in out and "기간 등락" in out


def _sample_candles(n=30, base=100.0):
    out = []
    for i in range(n):
        o = base + i
        out.append({"timestamp": f"2026-05-{(i % 28) + 1:02d}T00:00:00", "openPrice": str(o),
                    "highPrice": str(o + 2), "lowPrice": str(o - 2), "closePrice": str(o + 1),
                    "volume": str(1000 + i)})
    return list(reversed(out))  # API 는 최신순


def test_chart_with_ma_volume_and_avg(capsys):
    from toss_cli.cli.market import _render_chart

    _render_chart("005930", "1d", {"candles": _sample_candles()},
                  ma_periods=(5, 20), show_volume=True, avg_price="110")
    out = capsys.readouterr().out
    assert "MA5" in out and "MA20" in out
    assert "거래량" in out
    assert "평단" in out


def test_chart_single_candle_no_volume_subplot(capsys):
    from toss_cli.cli.market import _render_chart

    _render_chart("SPCX", "1d", {"candles": _sample_candles(1)})
    out = capsys.readouterr().out
    assert "기간 등락" in out


def test_chart_with_rsi_and_bb(capsys):
    from toss_cli.cli.market import _render_chart

    _render_chart("005930", "1d", {"candles": _sample_candles(40)},
                  ma_periods=(), show_volume=True, rsi_period=14, bb_period=20)
    out = capsys.readouterr().out
    assert "RSI" in out and "BB" in out


def test_limits_us_no_band_notice():
    out = _capture(_render_limits, "PLTR", {
        "timestamp": "2026-06-12T22:00:00", "upperLimitPrice": None,
        "lowerLimitPrice": None, "currency": "USD",
    })
    assert "가격제한폭" in out


def test_overview_renders_all_sections(capsys):
    from toss_cli.cli.market import _render_overview

    parts = {
        "info": [{"name": "삼성전자", "market": "KOSPI", "securityType": "STOCK"}],
        "price": [{"lastPrice": "324500", "currency": "KRW", "timestamp": "2026-06-12T20:00:00"}],
        "limits": {"upperLimitPrice": "421500", "lowerLimitPrice": "227500"},
        "candles": {"candles": _sample_candles(10)},
        "orderbook": {"currency": "KRW",
                      "asks": [{"price": "324500", "volume": "10"}] * 7,
                      "bids": [{"price": "324000", "volume": "20"}] * 7},
        "warnings": [{"warningType": "VI", "exchange": "KRX", "startDate": "2026-06-01", "endDate": None}],
        "holdings": {"items": [{"symbol": "005930", "quantity": "100",
                                "averagePurchasePrice": "300000",
                                "profitLoss": {"amount": "2450000", "rate": "0.0816"},
                                "dailyProfitLoss": {"rate": "0.012"},
                                "marketValue": {"amount": "32450000"}}]},
    }
    with __import__("toss_cli").render.console.capture() as cap:
        _render_overview("005930", parts)
    out = cap.get() + capsys.readouterr().out  # rich 출력 + plotext print 출력
    assert "삼성전자" in out and "현재가" in out
    assert "보유" in out and "평단" in out
    assert "호가" in out and "유의사항" in out


def test_overview_partial_data_does_not_crash(capsys):
    from toss_cli.cli.market import _render_overview

    with __import__("toss_cli").render.console.capture() as cap:
        _render_overview("PLTR", {"price": [{"lastPrice": "131", "currency": "USD"}]})
    out = cap.get()
    assert "PLTR" in out and "현재가" in out
