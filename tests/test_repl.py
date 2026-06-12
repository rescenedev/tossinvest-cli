"""REPL 핵심 동작 테스트: 공유 클라이언트 재사용, 계좌 헤더, 메타 명령."""

import httpx
import pytest
import respx
import typer

from toss_cli import auth as auth_mod
from toss_cli.cli import repl as repl_mod
from toss_cli.cli._common import AppState
from toss_cli.cli.app import app
from toss_cli.client import TossClient
from toss_cli.config import Config

BASE = "https://openapi.tossinvest.com"


@pytest.fixture(autouse=True)
def isolated_token_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(auth_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(auth_mod, "TOKEN_CACHE_FILE", tmp_path / "token.json")
    yield


def _command():
    return typer.main.get_command(app)


def _mock_token():
    respx.post(f"{BASE}/oauth2/token").mock(
        return_value=httpx.Response(
            200, json={"access_token": "tok", "token_type": "Bearer", "expires_in": 3600}
        )
    )


def _run(cmd, args, state):
    """REPL 의 _dispatch 와 동일하게 공유 state 로 명령 실행."""
    return cmd.main(args=args, prog_name="toss", standalone_mode=False, obj=state)


@respx.mock
def test_shared_client_reused_across_commands():
    _mock_token()
    prices = respx.get(f"{BASE}/api/v1/prices").mock(
        return_value=httpx.Response(200, json=[{"symbol": "005930", "lastPrice": "70000", "currency": "KRW"}])
    )
    client = TossClient(Config(client_id="c", client_secret="s", base_url=BASE))
    state = AppState(client=client)
    cmd = _command()

    _run(cmd, ["market", "price", "005930"], state)
    _run(cmd, ["market", "price", "005930"], state)

    # 두 번 호출됐지만 토큰 발급은 한 번만 (클라이언트/토큰 공유).
    assert prices.call_count == 2
    assert respx.calls[0].request.url.path == "/oauth2/token"
    token_calls = [c for c in respx.calls if c.request.url.path == "/oauth2/token"]
    assert len(token_calls) == 1
    client.close()


@respx.mock
def test_account_header_from_shared_client():
    _mock_token()
    holdings = respx.get(f"{BASE}/api/v1/holdings").mock(
        return_value=httpx.Response(200, json={"items": [], "profitLoss": {}, "marketValue": {}})
    )
    client = TossClient(Config(client_id="c", client_secret="s", base_url=BASE, account_seq=5))
    state = AppState(account=5, client=client)

    _run(_command(), ["account", "holdings"], state)

    assert holdings.calls.last.request.headers["X-Tossinvest-Account"] == "5"
    client.close()


def test_meta_account_rebinds_client():
    client = TossClient(Config(client_id="c", client_secret="s", account_seq=1))
    state = AppState(account=1, client=client)

    handled = repl_mod._handle_meta(":account 9", state)

    assert handled is True
    assert client.config.account_seq == 9
    assert state.account == 9
    client.close()


def test_meta_json_toggle():
    state = AppState(json_output=False)
    repl_mod._handle_meta(":json", state)
    assert state.json_output is True
    repl_mod._handle_meta(":json", state)
    assert state.json_output is False


def test_completion_tree_has_groups_and_meta():
    tree = repl_mod._completion_tree(_command())
    assert "market" in tree and isinstance(tree["market"], dict)
    assert "price" in tree["market"]
    assert "order" in tree and "buy" in tree["order"]
    assert ":account" in tree
