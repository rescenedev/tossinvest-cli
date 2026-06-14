"""REPL 숏컷/베어심볼 확장 로직 테스트."""

from toss_cli.cli.repl import expand_aliases


def test_group_command_alias():
    assert expand_aliases(["m", "p", "005930"]) == ["market", "price", "005930"]
    assert expand_aliases(["a", "h"]) == ["account", "holdings"]
    assert expand_aliases(["o", "b", "005930", "-q", "10"]) == [
        "order", "buy", "005930", "-q", "10"
    ]


def test_full_names_passthrough():
    assert expand_aliases(["market", "price", "005930"]) == ["market", "price", "005930"]


def test_bare_symbol_price():
    assert expand_aliases(["005930"]) == ["market", "price", "005930"]


def test_multiple_symbols_price():
    assert expand_aliases(["005930", "000660"]) == ["market", "price", "005930", "000660"]


def test_bare_symbol_market_buy():
    assert expand_aliases(["005930", "100"]) == [
        "order", "buy", "005930", "-q", "100", "-t", "MARKET"
    ]


def test_bare_symbol_market_sell_negative():
    assert expand_aliases(["005930", "-100"]) == [
        "order", "sell", "005930", "-q", "100", "-t", "MARKET"
    ]


def test_bare_symbol_limit_buy_with_price():
    assert expand_aliases(["005930", "100", "70000"]) == [
        "order", "buy", "005930", "-q", "100", "-p", "70000"
    ]


def test_bare_symbol_limit_sell_with_price():
    assert expand_aliases(["005930", "-50", "71000"]) == [
        "order", "sell", "005930", "-q", "50", "-p", "71000"
    ]


def test_extra_flags_passthrough():
    assert expand_aliases(["005930", "100", "-y"]) == [
        "order", "buy", "005930", "-q", "100", "-t", "MARKET", "-y"
    ]


def test_portfolio_shortcut():
    assert expand_aliases(["p"]) == ["account", "holdings"]
    assert expand_aliases(["p", "-s", "005930"]) == ["account", "holdings", "-s", "005930"]


def test_empty():
    assert expand_aliases([]) == []


def test_us_ticker_bare_symbol():
    assert expand_aliases(["AAPL"]) == ["market", "price", "AAPL"]
    assert expand_aliases(["TSLL", "SPCX"]) == ["market", "price", "TSLL", "SPCX"]


def test_us_ticker_buy_sell():
    assert expand_aliases(["AAPL", "10"]) == ["order", "buy", "AAPL", "-q", "10", "-t", "MARKET"]
    assert expand_aliases(["AAPL", "-5"]) == ["order", "sell", "AAPL", "-q", "5", "-t", "MARKET"]


def test_alnum_kr_etf_code():
    # 신형 ETF 코드 (예: 0193T0) — 숫자로 시작하는 6자리 영숫자
    assert expand_aliases(["0193T0"]) == ["market", "price", "0193T0"]
    assert expand_aliases(["0193T0", "100"]) == ["order", "buy", "0193T0", "-q", "100", "-t", "MARKET"]


def test_lowercase_commands_not_treated_as_ticker():
    assert expand_aliases(["market", "price", "005930"]) == ["market", "price", "005930"]
    assert expand_aliases(["p"]) == ["account", "holdings"]


def test_chart_shortcut():
    assert expand_aliases(["c", "005930"]) == ["market", "chart", "005930"]
    assert expand_aliases(["c", "AAPL", "-i", "1m"]) == ["market", "chart", "AAPL", "-i", "1m"]


def test_overview_shortcut():
    assert expand_aliases(["w", "005930"]) == ["market", "overview", "005930"]
    assert expand_aliases(["w", "PLTR", "-w", "5"]) == ["market", "overview", "PLTR", "-w", "5"]


def test_expand_bang_variants():
    from toss_cli.cli.repl import expand_bang

    hist = ["p", "w PLTR", "c PLTR", "o b 005930 -q 1"]
    assert expand_bang("!!", hist) == "o b 005930 -q 1"
    assert expand_bang("!1", hist) == "p"
    assert expand_bang("!2", hist) == "w PLTR"
    assert expand_bang("!-1", hist) == "o b 005930 -q 1"
    assert expand_bang("!w", hist) == "w PLTR"          # 접두어
    assert expand_bang("!o b", hist) == "o b 005930 -q 1"
    assert expand_bang("!99", hist) is None              # 범위 밖
    assert expand_bang("!zzz", hist) is None             # 매칭 없음
    assert expand_bang("!!", []) is None                 # 빈 기록


def test_load_history_lines(tmp_path, monkeypatch):
    from toss_cli.cli import repl as repl_mod

    f = tmp_path / "repl_history"
    f.write_text("# 2026-06-13 00:00:00.000\n+p\n\n# 2026-06-13 00:00:01.000\n+w PLTR\n",
                 encoding="utf-8")
    monkeypatch.setattr(repl_mod, "HISTORY_FILE", f)
    assert repl_mod.load_history_lines() == ["p", "w PLTR"]


def test_completion_tree_includes_shortcuts_and_meta():
    import typer
    from toss_cli.cli.app import app
    from toss_cli.cli.repl import _completion_tree

    tree = _completion_tree(typer.main.get_command(app))
    for key in ("p", "w", "c", "wl", ":history", ":json", ":reset"):
        assert key in tree, key
    # wl 은 watchlist 하위 트리(add/group 등)를 그대로 노출
    assert isinstance(tree["wl"], dict) and "add" in tree["wl"]
    # 그룹 약어도 유지
    assert tree["m"] == tree["market"]
