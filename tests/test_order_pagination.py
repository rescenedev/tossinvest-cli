"""order list --all 페이지 자동 추적 테스트."""

import httpx
import pytest
import respx

from toss_cli import auth as auth_mod
from toss_cli.api import order
from toss_cli.client import TossClient
from toss_cli.config import Config

BASE = "https://openapi.tossinvest.com"


@pytest.fixture(autouse=True)
def isolated_token_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(auth_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(auth_mod, "TOKEN_CACHE_FILE", tmp_path / "token.json")


@respx.mock
def test_list_all_orders_follows_cursor():
    respx.post(f"{BASE}/oauth2/token").mock(
        return_value=httpx.Response(
            200, json={"access_token": "t", "token_type": "Bearer", "expires_in": 3600}
        )
    )
    route = respx.get(f"{BASE}/api/v1/orders")
    route.side_effect = [
        httpx.Response(200, json={"result": {
            "orders": [{"orderId": "o1"}], "hasNext": True, "nextCursor": "c2"}}),
        httpx.Response(200, json={"result": {
            "orders": [{"orderId": "o2"}], "hasNext": False}}),
    ]
    config = Config(client_id="cid", client_secret="sec", base_url=BASE)
    with TossClient(config) as client:
        data = order.list_all_orders(client, 1, "CLOSED")
    assert [o["orderId"] for o in data["orders"]] == ["o1", "o2"]
    assert data["hasNext"] is False
    assert route.calls[1].request.url.params["cursor"] == "c2"
