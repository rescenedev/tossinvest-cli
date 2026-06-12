"""주문 CLI 동작 테스트: 매도 차단 가드, 멱등키 자동 생성, 예상 금액, 호가 단위 경고.

모두 --dry-run / 전송 전 단계만 검증하므로 네트워크가 필요 없습니다.
"""

from typer.testing import CliRunner

from toss_cli.cli.app import app

runner = CliRunner()


def test_no_sell_guard_blocks_real_sell(monkeypatch):
    monkeypatch.setenv("TOSS_NO_SELL", "1")
    result = runner.invoke(app, ["order", "sell", "005930", "-q", "1", "-t", "MARKET", "-y"])
    assert result.exit_code == 2
    assert "매도가 차단" in result.output


def test_no_sell_guard_allows_sim_sell(monkeypatch, tmp_path):
    monkeypatch.setenv("TOSS_NO_SELL", "1")
    import toss_cli.sim as sim_mod
    monkeypatch.setattr(sim_mod, "SIM_STATE_FILE", tmp_path / "sim_state.json")
    # sim 모드 매도는 가드 대상이 아님 (보유 없음 에러는 무방 — 가드 메시지만 아니면 됨)
    result = runner.invoke(app, ["--sim", "order", "sell", "005930", "-q", "1", "-t", "MARKET", "-y"])
    assert "매도가 차단" not in result.output


def test_no_sell_guard_allows_dry_run(monkeypatch):
    monkeypatch.setenv("TOSS_NO_SELL", "1")
    result = runner.invoke(app, ["order", "sell", "005930", "-q", "1", "-t", "MARKET", "--dry-run"])
    assert result.exit_code == 0
    assert "dry-run" in result.output


def test_auto_client_order_id_in_dry_run():
    result = runner.invoke(app, ["order", "buy", "005930", "-q", "1", "-p", "300000", "--dry-run"])
    assert result.exit_code == 0
    assert "clientOrderId" in result.output  # --id 없이도 멱등키 자동 생성


def test_explicit_client_order_id_kept():
    result = runner.invoke(
        app, ["order", "buy", "005930", "-q", "1", "-p", "300000", "--dry-run", "--id", "my-key-1"]
    )
    assert "my-key-1" in result.output


def test_estimated_amount_shown_for_limit():
    result = runner.invoke(app, ["order", "buy", "005930", "-q", "10", "-p", "70000", "--dry-run"])
    assert "예상 금액" in result.output
    assert "700,000" in result.output


def test_high_value_hint_when_flag_missing():
    # 1,000주 × 300,000원 = 3억 → --confirm-high-value 안내
    result = runner.invoke(app, ["order", "buy", "005930", "-q", "1000", "-p", "300000", "--dry-run"])
    assert "confirm-high-value" in result.output


def test_tick_size_warning_for_misaligned_kr_price():
    # 300,050원 — 20만~50만 구간 호가 단위는 500원
    result = runner.invoke(app, ["order", "buy", "005930", "-q", "1", "-p", "300050", "--dry-run"])
    assert "호가 단위" in result.output


def test_no_tick_warning_for_aligned_price():
    result = runner.invoke(app, ["order", "buy", "005930", "-q", "1", "-p", "300000", "--dry-run"])
    assert "호가 단위" not in result.output
