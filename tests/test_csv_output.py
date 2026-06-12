"""--csv 전역 출력 테스트."""

from typer.testing import CliRunner

from toss_cli.cli._common import _csv_rows, _flatten_row
from toss_cli.cli.app import app

runner = CliRunner()


def test_flatten_nested_dict():
    assert _flatten_row({"a": 1, "b": {"c": 2, "d": {"e": 3}}}) == {"a": 1, "b.c": 2, "b.d.e": 3}


def test_csv_rows_extracts_known_list_keys():
    assert _csv_rows([{"x": 1}]) == [{"x": 1}]
    assert _csv_rows({"candles": [{"o": 1}], "nextBefore": None}) == [{"o": 1}]
    assert _csv_rows({"orders": [{"id": "a"}]}) == [{"id": "a"}]
    assert _csv_rows({"single": 1}) == [{"single": 1}]


def test_cli_csv_output_sim(monkeypatch, tmp_path):
    import toss_cli.sim as sim_mod
    monkeypatch.setattr(sim_mod, "SIM_STATE_FILE", tmp_path / "sim.json")
    result = runner.invoke(app, ["--sim", "--csv", "market", "price", "005930"])
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert lines[0].startswith("symbol")  # CSV 헤더
    assert "005930" in lines[1]
