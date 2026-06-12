"""HTTP 클라이언트 테스트: 인증 헤더, 계좌 헤더, 에러 매핑, 429 재시도."""

import httpx
import pytest
import respx

from toss_cli import auth as auth_mod
from toss_cli.client import TossClient
from toss_cli.config import Config
from toss_cli.errors import TossApiError

BASE = "https://openapi.tossinvest.com"


@pytest.fixture(autouse=True)
def isolated_token_cache(monkeypatch, tmp_path):
    # 토큰 캐시를 임시 경로로 격리.
    monkeypatch.setattr(auth_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(auth_mod, "TOKEN_CACHE_FILE", tmp_path / "token.json")
    yield


@pytest.fixture
def config():
    return Config(client_id="cid", client_secret="sec", base_url=BASE)


def _mock_token(router):
    router.post(f"{BASE}/oauth2/token").mock(
        return_value=httpx.Response(
            200, json={"access_token": "tok-123", "token_type": "Bearer", "expires_in": 3600}
        )
    )


@respx.mock
def test_get_injects_auth_header(config):
    _mock_token(respx)
    route = respx.get(f"{BASE}/api/v1/prices").mock(
        return_value=httpx.Response(200, json=[{"symbol": "005930", "lastPrice": "70000"}])
    )
    with TossClient(config) as client:
        data = client.get("/api/v1/prices", params={"symbols": "005930"})
    assert data[0]["symbol"] == "005930"
    sent = route.calls.last.request
    assert sent.headers["Authorization"] == "Bearer tok-123"


@respx.mock
def test_account_header_set(config):
    _mock_token(respx)
    route = respx.get(f"{BASE}/api/v1/holdings").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    with TossClient(config) as client:
        client.get("/api/v1/holdings", account_seq=9)
    assert route.calls.last.request.headers["X-Tossinvest-Account"] == "9"


@respx.mock
def test_none_params_dropped(config):
    _mock_token(respx)
    route = respx.get(f"{BASE}/api/v1/trades").mock(
        return_value=httpx.Response(200, json=[])
    )
    with TossClient(config) as client:
        client.get("/api/v1/trades", params={"symbol": "005930", "count": None})
    assert "count" not in route.calls.last.request.url.params
    assert route.calls.last.request.url.params["symbol"] == "005930"


@respx.mock
def test_result_envelope_unwrapped(config):
    # 실 API 는 모든 성공 응답을 {"result": ...} 봉투로 감싼다 (스펙 ApiResponse).
    _mock_token(respx)
    respx.get(f"{BASE}/api/v1/accounts").mock(
        return_value=httpx.Response(
            200,
            json={"result": [{"accountSeq": 1, "accountNo": "19001000025", "accountType": "BROKERAGE"}]},
        )
    )
    with TossClient(config) as client:
        data = client.get("/api/v1/accounts")
    assert isinstance(data, list)
    assert data[0]["accountSeq"] == 1


@respx.mock
def test_non_envelope_body_passthrough(config):
    # 봉투가 아닌 본문(sim/레거시 형태)은 그대로 반환.
    _mock_token(respx)
    respx.get(f"{BASE}/api/v1/holdings").mock(
        return_value=httpx.Response(200, json={"items": [], "totalPurchaseAmount": "0"})
    )
    with TossClient(config) as client:
        data = client.get("/api/v1/holdings", account_seq=1)
    assert data == {"items": [], "totalPurchaseAmount": "0"}


@respx.mock
def test_error_response_mapped(config):
    _mock_token(respx)
    respx.post(f"{BASE}/api/v1/orders").mock(
        return_value=httpx.Response(
            400,
            json={"error": {"requestId": "r1", "code": "invalid-request", "message": "잘못된 요청"}},
        )
    )
    with TossClient(config) as client:
        with pytest.raises(TossApiError) as exc:
            client.post("/api/v1/orders", json_body={}, account_seq=1)
    assert exc.value.code == "invalid-request"
    assert exc.value.status_code == 400
    assert exc.value.request_id == "r1"


@respx.mock
def test_html_block_page_rendered_cleanly(config):
    # CDN(WAF) 차단 시 HTML 페이지가 오면 원문 대신 요약 메시지로 매핑.
    _mock_token(respx)
    respx.get(f"{BASE}/api/v1/holdings").mock(
        return_value=httpx.Response(
            403,
            headers={"Content-Type": "text/html"},
            text="<!DOCTYPE HTML><HTML><HEAD><TITLE>ERROR</TITLE></HEAD>"
                 "<BODY><H1>403 ERROR</H1>Request blocked.</BODY></HTML>",
        )
    )
    with TossClient(config) as client:
        with pytest.raises(TossApiError) as exc:
            client.get("/api/v1/holdings", account_seq=1)
    assert "<" not in exc.value.message  # HTML 원문 노출 금지
    assert "차단" in exc.value.message
    assert exc.value.status_code == 403


@respx.mock
def test_user_agent_header_sent(config):
    _mock_token(respx)
    route = respx.get(f"{BASE}/api/v1/prices").mock(
        return_value=httpx.Response(200, json={"result": []})
    )
    with TossClient(config) as client:
        client.get("/api/v1/prices", params={"symbols": "005930"})
    assert route.calls.last.request.headers["User-Agent"].startswith("tossinvest-cli/")


@respx.mock
def test_429_retries_then_succeeds(config, monkeypatch):
    _mock_token(respx)
    monkeypatch.setattr("toss_cli.client.time.sleep", lambda _s: None)
    route = respx.get(f"{BASE}/api/v1/prices")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "0"}, json={"error": {"code": "rate", "message": "x"}}),
        httpx.Response(200, json=[{"symbol": "005930"}]),
    ]
    with TossClient(config) as client:
        data = client.get("/api/v1/prices", params={"symbols": "005930"})
    assert data[0]["symbol"] == "005930"
    assert route.call_count == 2


@respx.mock
def test_retry_after_capped(config, monkeypatch):
    # 비정상적으로 큰 Retry-After 헤더도 상한(30초)으로 캡
    _mock_token(respx)
    waits = []
    monkeypatch.setattr("toss_cli.client.time.sleep", lambda s: waits.append(s))
    route = respx.get(f"{BASE}/api/v1/prices")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "99999"}, json={"error": {"code": "r", "message": "x"}}),
        httpx.Response(200, json={"result": []}),
    ]
    with TossClient(config) as client:
        client.get("/api/v1/prices", params={"symbols": "005930"})
    assert waits == [30.0]
