"""API 래퍼의 경로·파라미터 전달 검증 (respx).

단순 래퍼지만 symbols 조인·None 드롭·candles 옵션 전달은 회귀 위험이 있어 고정한다.
"""

import httpx
import pytest
import respx

from toss_cli import auth as auth_mod
from toss_cli.api import market_data, market_info
from toss_cli.client import TossClient
from toss_cli.config import Config

BASE = "https://openapi.tossinvest.com"


@pytest.fixture(autouse=True)
def isolated_token_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(auth_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(auth_mod, "TOKEN_CACHE_FILE", tmp_path / "token.json")


@pytest.fixture
def client():
    with TossClient(Config(client_id="cid", client_secret="sec", base_url=BASE)) as c:
        yield c


def _mock_token():
    respx.post(f"{BASE}/oauth2/token").mock(
        return_value=httpx.Response(
            200, json={"access_token": "t", "token_type": "Bearer", "expires_in": 3600}
        )
    )


def _ok(path):
    return respx.get(f"{BASE}{path}").mock(return_value=httpx.Response(200, json={"result": []}))


@respx.mock
def test_get_prices_joins_symbols(client):
    _mock_token()
    route = _ok("/api/v1/prices")
    market_data.get_prices(client, ["005930", "000660", "AAPL"])
    assert route.calls.last.request.url.params["symbols"] == "005930,000660,AAPL"


@respx.mock
def test_get_trades_drops_none_count(client):
    _mock_token()
    route = _ok("/api/v1/trades")
    market_data.get_trades(client, "005930")  # count 미지정
    params = route.calls.last.request.url.params
    assert params["symbol"] == "005930" and "count" not in params

    market_data.get_trades(client, "005930", count=20)
    assert route.calls.last.request.url.params["count"] == "20"


@respx.mock
def test_get_candles_passes_all_options(client):
    _mock_token()
    route = _ok("/api/v1/candles")
    market_data.get_candles(client, "005930", "1m", count=60, before="2026-06-01T00:00:00",
                            adjusted=True)
    p = route.calls.last.request.url.params
    assert p["symbol"] == "005930"
    assert p["interval"] == "1m"
    assert p["count"] == "60"
    assert p["before"] == "2026-06-01T00:00:00"
    assert p["adjusted"] == "true"


@respx.mock
def test_exchange_rate_params(client):
    _mock_token()
    route = _ok("/api/v1/exchange-rate")
    market_info.get_exchange_rate(client, "USD", "KRW", "2026-06-12T10:00:00")
    p = route.calls.last.request.url.params
    assert p["baseCurrency"] == "USD" and p["quoteCurrency"] == "KRW"
    assert p["dateTime"] == "2026-06-12T10:00:00"


@respx.mock
def test_calendar_paths_and_date(client):
    _mock_token()
    kr = _ok("/api/v1/market-calendar/KR")
    market_info.get_kr_calendar(client, "2026-06-12")
    assert kr.calls.last.request.url.params["date"] == "2026-06-12"

    us = _ok("/api/v1/market-calendar/US")
    market_info.get_us_calendar(client)  # date 미지정 → 드롭
    assert "date" not in us.calls.last.request.url.params


@respx.mock
def test_stock_wrappers(client):
    from toss_cli.api import stock
    _mock_token()
    route = _ok("/api/v1/stocks")
    stock.get_stocks(client, ["005930", "AAPL"])
    assert route.calls.last.request.url.params["symbols"] == "005930,AAPL"

    w = respx.get(f"{BASE}/api/v1/stocks/005930/warnings").mock(
        return_value=httpx.Response(200, json={"result": []}))
    stock.get_stock_warnings(client, "005930")
    assert w.called


@respx.mock
def test_account_holdings_sets_account_header(client):
    from toss_cli.api import account
    _mock_token()
    route = respx.get(f"{BASE}/api/v1/holdings").mock(
        return_value=httpx.Response(200, json={"result": {"items": []}}))
    account.get_holdings(client, 7, symbol="005930")
    req = route.calls.last.request
    assert req.headers["X-Tossinvest-Account"] == "7"
    assert req.url.params["symbol"] == "005930"

    account.get_holdings(client, 7)  # symbol 미지정 → 드롭
    assert "symbol" not in route.calls.last.request.url.params


@respx.mock
def test_order_read_wrappers_set_account_and_params(client):
    from toss_cli.api import order
    _mock_token()
    bp = respx.get(f"{BASE}/api/v1/buying-power").mock(
        return_value=httpx.Response(200, json={"result": {}}))
    order.get_buying_power(client, 3, "USD")
    assert bp.calls.last.request.headers["X-Tossinvest-Account"] == "3"
    assert bp.calls.last.request.url.params["currency"] == "USD"

    sq = respx.get(f"{BASE}/api/v1/sellable-quantity").mock(
        return_value=httpx.Response(200, json={"result": {}}))
    order.get_sellable_quantity(client, 3, "PLTR")
    assert sq.calls.last.request.url.params["symbol"] == "PLTR"
