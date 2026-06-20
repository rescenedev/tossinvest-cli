"""인증 커맨드: login(토큰 강제 발급), logout(캐시 삭제), status."""

from __future__ import annotations

import time

import httpx
import typer

from .. import auth, render
from ..config import (
    ConfigError,
    keychain_available,
    keychain_delete,
    keychain_get,
    keychain_set,
    load_config,
)
from ..errors import TossApiError
from ._alias import AliasGroup

app = typer.Typer(help="인증 (토큰 발급/캐시 관리)", cls=AliasGroup)
keychain_app = typer.Typer(help="macOS Keychain 에 자격증명 저장/조회/삭제", cls=AliasGroup)
app.add_typer(keychain_app, name="keychain")


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
            ("keychain", "사용 가능" if keychain_available() else "비활성 (macOS 전용)"),
        ],
    )


@keychain_app.command("set")
def keychain_set_cmd(
    client_id: str = typer.Option(None, "--client-id", help="미지정 시 프롬프트"),
    client_secret: str = typer.Option(None, "--client-secret", help="미지정 시 프롬프트(가림)"),
) -> None:
    """client_id / client_secret 을 macOS Keychain 에 저장.

    저장 후에는 .env 없이도 자격증명을 불러옵니다 (우선순위: env > .env > Keychain > toml).
    """
    if not keychain_available():
        render.print_error("Keychain 은 macOS 에서만 사용할 수 있습니다.")
        raise typer.Exit(code=2)
    cid = client_id or typer.prompt("client_id")
    secret = client_secret or typer.prompt("client_secret", hide_input=True)
    try:
        keychain_set("client_id", cid)
        keychain_set("client_secret", secret)
    except ConfigError as exc:
        render.print_error(str(exc))
        raise typer.Exit(code=1)
    render.print_success("Keychain 에 자격증명을 저장했습니다. 이제 .env 없이 동작합니다.")


@keychain_app.command("status")
def keychain_status() -> None:
    """Keychain 에 저장된 자격증명 존재 여부 (값은 노출 안 함)."""
    if not keychain_available():
        render.print_warning("Keychain 은 macOS 에서만 사용할 수 있습니다.")
        return
    rows = []
    for account in ("client_id", "client_secret"):
        value = keychain_get(account)
        rows.append((account, "저장됨 ✓" if value else "[dim]없음[/dim]"))
    render.key_values("Keychain (tossinvest-cli)", rows)


@keychain_app.command("clear")
def keychain_clear(
    yes: bool = typer.Option(False, "--yes", "-y", help="확인 생략"),
) -> None:
    """Keychain 에 저장된 자격증명을 삭제."""
    if not keychain_available():
        render.print_warning("Keychain 은 macOS 에서만 사용할 수 있습니다.")
        return
    if not yes and not typer.confirm("Keychain 의 tossinvest-cli 자격증명을 삭제할까요?"):
        render.print_warning("취소했습니다.")
        raise typer.Exit(code=0)
    removed = sum(keychain_delete(a) for a in ("client_id", "client_secret"))
    render.print_success(f"Keychain 항목 {removed}개를 삭제했습니다.")
