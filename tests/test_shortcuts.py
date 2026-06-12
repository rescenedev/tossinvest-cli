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
