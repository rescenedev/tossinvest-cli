"""시뮬레이션 클라이언트 테스트."""

from decimal import Decimal

import pytest

from toss_cli import sim as sim_mod
from toss_cli.errors import TossApiError
from toss_cli.sim import SimClient, sim_config


@pytest.fixture(autouse=True)
def isolated_sim_state(monkeypatch, tmp_path):
    monkeypatch.setattr(sim_mod, "SIM_STATE_FILE", tmp_path / "sim_state.json")
    from toss_cli import config as config_mod
    monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(sim_mod, "CONFIG_DIR", tmp_path)
    yield


def _client():
    return SimClient(sim_config(1))


def test_prices_deterministic():
    c = _client()
    p1 = c.get("/api/v1/prices", params={"symbols": "005930"})
    p2 = c.get("/api/v1/prices", params={"symbols": "005930"})
    assert p1[0]["symbol"] == "005930"
    assert p1[0]["currency"] == "KRW"
    assert p1[0]["lastPrice"] == p2[0]["lastPrice"]  # 결정적


def test_us_symbol_usd():
    c = _client()
    p = c.get("/api/v1/prices", params={"symbols": "AAPL"})
    assert p[0]["currency"] == "USD"


def test_market_buy_fills_and_updates_holdings():
    c = _client()
    res = c.post("/api/v1/orders", json_body={
        "symbol": "005930", "side": "BUY", "orderType": "MARKET", "quantity": "100"
    }, account_seq=1)
    assert res["orderId"].startswith("SIM-")

    order = c.get(f"/api/v1/orders/{res['orderId']}", account_seq=1)
    assert order["status"] == "FILLED"

    holdings = c.get("/api/v1/holdings", account_seq=1)
    assert holdings["items"][0]["symbol"] == "005930"
    assert holdings["items"][0]["quantity"] == "100"


def test_limit_order_stays_pending_and_listed_open():
    c = _client()
    res = c.post("/api/v1/orders", json_body={
        "symbol": "005930", "side": "BUY", "orderType": "LIMIT",
        "quantity": "10", "price": "70000"
    }, account_seq=1)
    open_orders = c.get("/api/v1/orders", params={"status": "OPEN"}, account_seq=1)
    assert any(o["orderId"] == res["orderId"] for o in open_orders["orders"])
    assert open_orders["orders"][0]["status"] == "PENDING"


def test_buy_then_sell_nets_position():
    c = _client()
    c.post("/api/v1/orders", json_body={"symbol": "005930", "side": "BUY",
           "orderType": "MARKET", "quantity": "100"}, account_seq=1)
    c.post("/api/v1/orders", json_body={"symbol": "005930", "side": "SELL",
           "orderType": "MARKET", "quantity": "30"}, account_seq=1)
    sellable = c.get("/api/v1/sellable-quantity", params={"symbol": "005930"}, account_seq=1)
    assert sellable["sellableQuantity"] == "70"


def test_cancel_order():
    c = _client()
    res = c.post("/api/v1/orders", json_body={"symbol": "005930", "side": "BUY",
           "orderType": "LIMIT", "quantity": "10", "price": "70000"}, account_seq=1)
    c.post(f"/api/v1/orders/{res['orderId']}/cancel", account_seq=1)
    order = c.get(f"/api/v1/orders/{res['orderId']}", account_seq=1)
    assert order["status"] == "CANCELED"


def test_idempotent_client_order_id():
    c = _client()
    body = {"symbol": "005930", "side": "BUY", "orderType": "MARKET",
            "quantity": "10", "clientOrderId": "dup-1"}
    r1 = c.post("/api/v1/orders", json_body=body, account_seq=1)
    r2 = c.post("/api/v1/orders", json_body=dict(body), account_seq=1)
    assert r1["orderId"] == r2["orderId"]  # 동일 키 → 동일 주문


def test_holdings_records_purchase_date():
    c = _client()
    c.post("/api/v1/orders", json_body={"symbol": "005930", "side": "BUY",
           "orderType": "MARKET", "quantity": "10"}, account_seq=1)
    item = c.get("/api/v1/holdings", account_seq=1)["items"][0]
    assert item["purchasedAt"]  # 매수 시점 기록됨


def test_price_shift_creates_profit():
    c = _client()
    c.post("/api/v1/orders", json_body={"symbol": "005930", "side": "BUY",
           "orderType": "MARKET", "quantity": "10"}, account_seq=1)
    # 매수 직후엔 손익 0. 요약 금액은 스펙(HoldingsOverview)대로 통화별 dict.
    before = c.get("/api/v1/holdings", account_seq=1)["profitLoss"]["amount"]
    assert Decimal(before["krw"]) == 0

    c.shift_price(5.0)  # 시세 +5%
    after = c.get("/api/v1/holdings", account_seq=1)
    assert Decimal(after["profitLoss"]["amount"]["krw"]) > 0
    # rate 는 소수비율 (0.05 = 5%) — 스펙 ProfitLoss.rate
    assert float(after["items"][0]["profitLoss"]["rate"]) == pytest.approx(0.05, abs=0.005)


def test_full_sell_clears_purchase_date():
    c = _client()
    c.post("/api/v1/orders", json_body={"symbol": "005930", "side": "BUY",
           "orderType": "MARKET", "quantity": "10"}, account_seq=1)
    c.post("/api/v1/orders", json_body={"symbol": "005930", "side": "SELL",
           "orderType": "MARKET", "quantity": "10"}, account_seq=1)
    holdings = c.get("/api/v1/holdings", account_seq=1)
    assert holdings["items"] == []  # 전량 매도 → 보유 없음


def test_persistence_across_clients():
    c1 = _client()
    c1.post("/api/v1/orders", json_body={"symbol": "005930", "side": "BUY",
            "orderType": "MARKET", "quantity": "5"}, account_seq=1)
    c1.close()
    c2 = _client()  # 새 클라이언트가 디스크 상태를 읽음
    holdings = c2.get("/api/v1/holdings", account_seq=1)
    assert holdings["items"][0]["quantity"] == "5"


def test_oversell_rejected():
    # 보유 수량 초과 매도는 거부 — 현금 부풀림 방지 (실 API 와 동일하게 에러)
    c = _client()
    c.post("/api/v1/orders", json_body={"symbol": "005930", "side": "BUY",
           "orderType": "MARKET", "quantity": "10"}, account_seq=1)
    cash_before = c.get("/api/v1/buying-power", params={"currency": "KRW"}, account_seq=1)
    with pytest.raises(TossApiError):
        c.post("/api/v1/orders", json_body={"symbol": "005930", "side": "SELL",
               "orderType": "MARKET", "quantity": "999"}, account_seq=1)
    cash_after = c.get("/api/v1/buying-power", params={"currency": "KRW"}, account_seq=1)
    assert cash_before == cash_after  # 거부된 주문은 현금 불변
