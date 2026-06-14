"""REPL 메타 명령(:json·:account·:tick·:reset·:clear) 디스패치 테스트."""

import pytest

from toss_cli.cli._common import AppState
from toss_cli.cli.repl import _handle_meta


@pytest.fixture
def state(monkeypatch, tmp_path):
    import toss_cli.sim as sim_mod
    from toss_cli.sim import SimClient, sim_config
    monkeypatch.setattr(sim_mod, "SIM_STATE_FILE", tmp_path / "sim.json")
    return AppState(account=1, sim=True, client=SimClient(sim_config(1)))


def test_json_toggle(state):
    assert _handle_meta(":json", state) is True
    assert state.json_output is True
    _handle_meta(":json", state)
    assert state.json_output is False


def test_account_change(state):
    _handle_meta(":account 5", state)
    assert state.account == 5
    assert state.client.config.account_seq == 5


def test_account_invalid_keeps_value(state):
    assert _handle_meta(":account abc", state) is True
    assert state.account == 1


def test_account_missing_arg(state):
    assert _handle_meta(":account", state) is True  # 사용법 안내, 변경 없음
    assert state.account == 1


def test_tick_shifts_in_sim(state):
    p1 = state.client.get("/api/v1/prices", params={"symbols": "005930"})[0]["lastPrice"]
    _handle_meta(":tick 10", state)
    p2 = state.client.get("/api/v1/prices", params={"symbols": "005930"})[0]["lastPrice"]
    assert float(p2) > float(p1)


def test_tick_blocked_outside_sim():
    st = AppState(account=1, sim=False, client=None)
    assert _handle_meta(":tick", st) is True  # 경고만, 예외 없음


def test_unknown_meta_warns(state):
    assert _handle_meta(":bogus", state) is True
