"""인증 커맨드: login(토큰 강제 발급), logout(캐시 삭제), status."""

from __future__ import annotations

import time

import httpx
import typer

from .. import auth, render
from ..config import ConfigError, load_config
from ..errors import TossApiError

app = typer.Typer(help="인증 (토큰 발급/캐시 관리)")


@app.command("login")
def login() -> None:
    """토큰을 강제로 새로 발급하고 캐시에 저장."""
    try:
        config = load_config()
    except ConfigError as exc:
        render.print_error(str(exc))
        raise typer.Exit(code=2)
    with httpx.Client(timeout=15.0) as http:
        try:
            token = auth.get_token(config, http, force=True)
        except TossApiError as exc:
            render.print_error(str(exc))
            raise typer.Exit(code=1)
    remaining = int(token.expires_at - time.time())
    render.print_success(f"토큰 발급 완료. 약 {remaining}초 후 만료 (캐시됨).")


@app.command("logout")
def logout() -> None:
    """캐시된 토큰을 삭제."""
    if auth.clear_cache():
        render.print_success("토큰 캐시를 삭제했습니다.")
    else:
        render.print_warning("삭제할 캐시 토큰이 없습니다.")


@app.command("status")
def status() -> None:
    """현재 설정과 토큰 캐시 상태를 표시 (시크릿은 마스킹)."""
    try:
        config = load_config()
    except ConfigError as exc:
        render.print_error(str(exc))
        raise typer.Exit(code=2)
    masked = config.client_id[:4] + "…" if len(config.client_id) > 4 else "…"
    render.key_values(
        "설정",
        [
            ("base_url", config.base_url),
            ("client_id", masked),
            ("account_seq", config.account_seq),
            ("token_cache", str(auth.TOKEN_CACHE_FILE)),
        ],
    )
