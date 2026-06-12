"""로컬 거래 ledger 테스트."""

import pytest
from typer.testing import CliRunner

from toss_cli.cli import ledger
from toss_cli.cli.app import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_ledger(monkeypatch, tmp_path):
    monkeypatch.setattr(ledger, "LEDGER_FILE", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(ledger, "CONFIG_DIR", tmp_path)


def test_record_and_load_roundtrip():
    ledger.record("place", sim=True, symbol="005930", side="BUY",
                  quantity="10", orderId="SIM-1")
    ledger.record("cancel", sim=True, orderId="SIM-1")
    entries = ledger.load()
    assert len(entries) == 2
    assert entries[0]["action"] == "place" and entries[0]["mode"] == "sim"
    assert entries[1]["action"] == "cancel"


def test_sim_order_recorded_via_cli(monkeypatch, tmp_path):
    import toss_cli.sim as sim_mod
    monkeypatch.setattr(sim_mod, "SIM_STATE_FILE", tmp_path / "sim.json")
    r = runner.invoke(app, ["--sim", "order", "buy", "005930", "-q", "1", "-t", "MARKET", "-y"])
    assert r.exit_code == 0
    entries = ledger.load()
    assert entries and entries[-1]["symbol"] == "005930" and entries[-1]["action"] == "place"


def test_ledger_show_renders_table(monkeypatch, tmp_path):
    ledger.record("place", sim=True, symbol="AAPL", side="SELL", quantity="2", orderId="SIM-9")
    r = runner.invoke(app, ["ledger", "show"])
    assert "AAPL" in r.output and "place" in r.output
