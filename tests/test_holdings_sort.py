"""보유종목 정렬(--sort) 테스트."""

from toss_cli.cli.account import _sort_holdings


def _payload():
    return {"items": [
        {"symbol": "A", "profitLoss": {"rate": "0.05"}, "dailyProfitLoss": {"rate": "-0.02"},
         "marketValue": {"amount": "300"}},
        {"symbol": "B", "profitLoss": {"rate": "-0.10"}, "dailyProfitLoss": {"rate": "0.08"},
         "marketValue": {"amount": "100"}},
        {"symbol": "C", "profitLoss": {"rate": "0.20"}, "dailyProfitLoss": {"rate": "0.01"},
         "marketValue": {"amount": "200"}},
    ]}


def _order(data):
    return [i["symbol"] for i in data["items"]]


def test_sort_by_daily():
    assert _order(_sort_holdings(_payload(), "daily")) == ["B", "C", "A"]  # +8% > +1% > -2%


def test_sort_by_pl():
    assert _order(_sort_holdings(_payload(), "pl")) == ["C", "A", "B"]   # +20% > +5% > -10%


def test_sort_by_value():
    assert _order(_sort_holdings(_payload(), "value")) == ["A", "C", "B"]  # 300 > 200 > 100


def test_unknown_key_keeps_original(capsys):
    data = _sort_holdings(_payload(), "bogus")
    assert _order(data) == ["A", "B", "C"]


def test_currency_dict_uses_krw():
    data = {"items": [
        {"symbol": "X", "marketValue": {"amount": {"krw": "100", "usd": "5"}}},
        {"symbol": "Y", "marketValue": {"amount": {"krw": "200", "usd": "1"}}},
    ]}
    from toss_cli.cli.account import _sort_holdings as s
    assert [i["symbol"] for i in s(data, "value")["items"]] == ["Y", "X"]
