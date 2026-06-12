"""관심종목(watchlist) 저장·렌더링·숏컷 테스트."""

from decimal import Decimal

import pytest

from toss_cli import render
from toss_cli.cli import watchlist as wl
from toss_cli.cli.repl import expand_aliases


@pytest.fixture(autouse=True)
def isolated_watchlist(monkeypatch, tmp_path):
    monkeypatch.setattr(wl, "WATCHLIST_FILE", tmp_path / "watchlist.json")
    monkeypatch.setattr(wl, "CONFIG_DIR", tmp_path)


def test_add_rm_roundtrip():
    wl._save([])
    wl._save(wl._load() + ["005930"])
    assert wl._load() == ["005930"]
    wl._save([s for s in wl._load() if s != "005930"])
    assert wl._load() == []


def test_normalize_symbols():
    assert wl._normalize("aapl") == "AAPL"   # 미국 티커는 대문자
    assert wl._normalize("0193T0") == "0193T0"  # KR 코드는 그대로


def test_board_sorted_by_change():
    prices = [
        {"symbol": "AAA", "lastPrice": "110", "currency": "USD"},
        {"symbol": "BBB", "lastPrice": "90", "currency": "USD"},
        {"symbol": "CCC", "lastPrice": "100", "currency": "USD"},  # 전일 종가 없음 → 맨 뒤
    ]
    prev = {"AAA": Decimal("100"), "BBB": Decimal("100")}
    with render.console.capture() as cap:
        wl._render_board(["AAA", "BBB", "CCC"], prices, prev)
    out = cap.get()
    assert out.index("AAA") < out.index("BBB")  # +10% 가 -10% 보다 위
    assert "+10.00%" in out and "-10.00%" in out


def test_wl_shortcuts():
    assert expand_aliases(["wl"]) == ["watchlist", "show"]
    assert expand_aliases(["wl", "-w", "10"]) == ["watchlist", "show", "-w", "10"]
    assert expand_aliases(["wl", "add", "005930", "AAPL"]) == ["watchlist", "add", "005930", "AAPL"]
    assert expand_aliases(["wl", "rm", "AAPL"]) == ["watchlist", "rm", "AAPL"]
