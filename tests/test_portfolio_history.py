"""포트폴리오 가치 추이(근사 재구성) 테스트."""

from decimal import Decimal

from toss_cli.cli.account import build_value_series


def _candles(prices_by_date):
    return [
        {"timestamp": f"{d}T00:00:00", "closePrice": str(p)}
        for d, p in prices_by_date.items()
    ]


def test_build_value_series_mixed_currency_with_ffill():
    items = [
        {"symbol": "005930", "quantity": "10", "currency": "KRW"},
        {"symbol": "AAPL", "quantity": "2", "currency": "USD"},
    ]
    candles = {
        # KR 은 6/12 휴장 가정 (6/11 값으로 forward-fill 기대)
        "005930": _candles({"2026-06-10": 100, "2026-06-11": 110}),
        "AAPL": _candles({"2026-06-10": 10, "2026-06-11": 10, "2026-06-12": 12}),
    }
    dates, values = build_value_series(items, candles, usdkrw=Decimal("1000"))
    assert dates == ["2026-06-10", "2026-06-11", "2026-06-12"]
    # 6/10: 10*100 + 2*10*1000 = 21,000 / 6/11: 1100+20000=21,100 / 6/12: ffill 1100 + 24000
    assert [int(v) for v in values] == [21000, 21100, 25100]


def test_build_value_series_backfills_short_history():
    items = [{"symbol": "NEW", "quantity": "1", "currency": "USD"},
             {"symbol": "OLD", "quantity": "1", "currency": "USD"}]
    candles = {
        "NEW": _candles({"2026-06-12": 5}),  # 신규 상장 — 이력 1개
        "OLD": _candles({"2026-06-10": 1, "2026-06-11": 2, "2026-06-12": 3}),
    }
    dates, values = build_value_series(items, candles, usdkrw=Decimal("1"))
    # NEW 는 첫 종가(5)로 과거 backfill → 6,7,8
    assert [int(v) for v in values] == [6, 7, 8]


def test_snapshot_recorded_once_per_day(monkeypatch, tmp_path):
    from toss_cli import config as config_mod
    from toss_cli.cli import account as account_cli

    monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
    payload = {"marketValue": {"amount": {"krw": "100"}}, "profitLoss": {"amount": {"krw": "1"}}}
    account_cli._record_snapshot(payload)
    account_cli._record_snapshot(payload)  # 같은 날 중복 호출
    lines = (tmp_path / "portfolio_history.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
