"""관심종목(watchlist) 그룹 저장·렌더링·숏컷 테스트."""

from decimal import Decimal

import pytest
from typer.testing import CliRunner

from toss_cli import render
from toss_cli.cli import watchlist as wl
from toss_cli.cli.app import app
from toss_cli.cli.repl import expand_aliases

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_watchlist(monkeypatch, tmp_path):
    monkeypatch.setattr(wl, "WATCHLIST_FILE", tmp_path / "watchlist.json")
    monkeypatch.setattr(wl, "CONFIG_DIR", tmp_path)


def test_add_to_groups_and_rm():
    runner.invoke(app, ["watchlist", "add", "005930", "aapl"])
    runner.invoke(app, ["watchlist", "add", "TSLA", "-g", "성장주"])
    groups = wl._load_groups()
    assert groups[wl.DEFAULT_GROUP] == ["005930", "AAPL"]  # 소문자 티커 정규화
    assert groups["성장주"] == ["TSLA"]

    runner.invoke(app, ["watchlist", "rm", "AAPL"])
    assert wl._load_groups()[wl.DEFAULT_GROUP] == ["005930"]


def test_flat_legacy_format_migrates():
    wl.WATCHLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    wl.WATCHLIST_FILE.write_text('["005930", "AAPL"]', encoding="utf-8")
    assert wl._load_groups() == {wl.DEFAULT_GROUP: ["005930", "AAPL"]}


def test_group_crud():
    runner.invoke(app, ["watchlist", "group", "create", "반도체"])
    runner.invoke(app, ["watchlist", "add", "000660", "-g", "반도체"])
    runner.invoke(app, ["watchlist", "group", "rename", "반도체", "칩"])
    groups = wl._load_groups()
    assert groups["칩"] == ["000660"] and "반도체" not in groups
    runner.invoke(app, ["watchlist", "group", "delete", "칩", "-y"])
    assert "칩" not in wl._load_groups()


def test_board_sorted_by_change():
    prices = [
        {"symbol": "AAA", "lastPrice": "110", "currency": "USD"},
        {"symbol": "BBB", "lastPrice": "90", "currency": "USD"},
        {"symbol": "CCC", "lastPrice": "100", "currency": "USD"},  # 전일 종가 없음 → 맨 뒤
    ]
    prev = {"AAA": Decimal("100"), "BBB": Decimal("100")}
    with render.console.capture() as cap:
        wl._render_board("기본", ["AAA", "BBB", "CCC"], prices, prev)
    out = cap.get()
    assert out.index("AAA") < out.index("BBB")  # +10% 가 -10% 보다 위
    assert "+10.00%" in out and "-10.00%" in out


def test_wl_shortcuts():
    assert expand_aliases(["wl"]) == ["watchlist", "show"]
    assert expand_aliases(["wl", "-g", "성장주"]) == ["watchlist", "show", "-g", "성장주"]
    assert expand_aliases(["wl", "add", "005930", "AAPL"]) == ["watchlist", "add", "005930", "AAPL"]
    assert expand_aliases(["wl", "groups"]) == ["watchlist", "groups"]
    assert expand_aliases(["wl", "group", "create", "x"]) == ["watchlist", "group", "create", "x"]
