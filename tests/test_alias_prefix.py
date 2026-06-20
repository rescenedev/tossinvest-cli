"""명령 약어(prefix) 해석 테스트: 고유 접두어는 풀리고, 모호하면 후보를 보여 준다.

모두 --sim 또는 --help 단계만 검증하므로 네트워크가 필요 없습니다.
"""

from typer.testing import CliRunner

from toss_cli.cli.app import app

runner = CliRunner()


def test_unique_prefix_resolves_subcommand():
    # o -> order, list 는 sim 에서 빈 목록이라도 정상 종료
    result = runner.invoke(app, ["--sim", "o", "list"])
    assert result.exit_code == 0
    assert "주문 목록" in result.output


def test_unique_prefix_resolves_account():
    result = runner.invoke(app, ["--sim", "acc", "list"])
    assert result.exit_code == 0
    assert "계좌 목록" in result.output


def test_nested_prefix_resolves_to_leaf():
    # o b -> order buy (--help 로 디스패치만 확인)
    result = runner.invoke(app, ["--sim", "o", "b", "--help"])
    assert result.exit_code == 0
    assert "SYMBOL" in result.output


def test_three_level_prefix():
    # au k -> auth keychain (그룹 도움말)
    result = runner.invoke(app, ["au", "k", "--help"])
    assert result.exit_code == 0
    assert "keychain" in result.output.lower() or "Keychain" in result.output


def test_ambiguous_top_level_prefix_reports_candidates():
    # a -> account, auth
    result = runner.invoke(app, ["--sim", "a", "list"])
    assert result.exit_code != 0
    assert "account" in result.output and "auth" in result.output


def test_ambiguous_nested_prefix_reports_candidates():
    # order c -> cancel, commissions
    result = runner.invoke(app, ["--sim", "order", "c"])
    assert result.exit_code != 0
    assert "cancel" in result.output and "commissions" in result.output


def test_exact_name_still_wins():
    result = runner.invoke(app, ["--sim", "order", "list"])
    assert result.exit_code == 0
    assert "주문 목록" in result.output


def test_unknown_prefix_is_error():
    result = runner.invoke(app, ["--sim", "zzz"])
    assert result.exit_code != 0
