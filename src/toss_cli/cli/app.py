"""메인 Typer 앱: 전역 옵션과 모든 서브커맨드를 결합."""

from __future__ import annotations

import typer

from .. import __version__
from ._common import get_state
from . import account, auth_cmd, info, market, order, stock, watchlist
from .repl import run_repl

app = typer.Typer(
    name="toss",
    help="토스증권 Open API CLI — 시세 조회부터 주문까지. (인자 없이 실행하면 REPL 시작)",
    no_args_is_help=False,
    invoke_without_command=True,
    add_completion=True,
)

app.add_typer(auth_cmd.app, name="auth")
app.add_typer(market.app, name="market")
app.add_typer(stock.app, name="stock")
app.add_typer(info.app, name="info")
app.add_typer(account.app, name="account")
app.add_typer(order.app, name="order")
app.add_typer(watchlist.app, name="watchlist")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"tossinvest-cli {__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    ctx: typer.Context,
    account_seq: int = typer.Option(
        None, "--account", "-a", help="계좌 일련번호(accountSeq). 미지정 시 TOSS_ACCOUNT_SEQ 사용."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="결과를 표 대신 원본 JSON 으로 출력."
    ),
    sim: bool = typer.Option(
        False, "--sim", help="시뮬레이션 모드 (자격증명 없이 모의 시세/주문)."
    ),
    version: bool = typer.Option(
        None, "--version", callback=_version_callback, is_eager=True, help="버전 출력 후 종료."
    ),
) -> None:
    """전역 옵션을 상태에 반영. 서브커맨드가 없으면 REPL 을 시작."""
    state = get_state(ctx)

    # REPL 세션 내 재진입(공유 클라이언트 존재)이면 세션 상태를 유지한다.
    # (account/json/sim 은 세션 시작값을 따르고, :account/:json 메타로 변경)
    if state.client is not None:
        return

    state.account = account_seq
    state.json_output = json_output
    state.sim = sim or _env_truthy("TOSS_SIM")

    if ctx.invoked_subcommand is None:
        run_repl(ctx)


def _env_truthy(name: str) -> bool:
    import os

    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


@app.command("repl")
def repl(ctx: typer.Context) -> None:
    """대화형 셸을 시작 (토큰/연결을 세션 내내 재사용)."""
    run_repl(ctx)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
