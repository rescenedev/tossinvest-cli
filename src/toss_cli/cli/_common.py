"""CLI 공통 상태/헬퍼: 전역 옵션, 클라이언트 생성, 에러 처리."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

import typer

from ..client import ApiClient, TossClient
from ..config import Config, ConfigError, load_config
from ..errors import TossApiError
from ..sim import SimClient, sim_config
from .. import render


@dataclass
class AppState:
    """전역 CLI 상태 (Typer ctx.obj 에 보관).

    REPL 모드에서는 `client` 에 세션 내내 재사용할 클라이언트를 보관하여
    매 명령마다 클라이언트를 새로 만들지 않고 토큰/연결을 공유한다.
    `sim` 이 True 면 자격증명 없이 모의 클라이언트를 사용한다.
    """

    account: int | None = None
    json_output: bool = False
    csv_output: bool = False
    sim: bool = False
    client: ApiClient | None = None


def get_state(ctx: typer.Context) -> AppState:
    if not isinstance(ctx.obj, AppState):
        ctx.obj = AppState()
    return ctx.obj


def _load_config_or_exit(state: AppState) -> Config:
    try:
        config = load_config()
    except ConfigError as exc:
        render.print_error(str(exc))
        raise typer.Exit(code=2)
    return config.with_account(state.account)


def _handle_client_errors(exc: Exception) -> None:
    """공통 에러 처리: 메시지 출력 후 적절한 종료코드로 Exit."""
    if isinstance(exc, TossApiError):
        render.print_error(str(exc))
        if exc.data:
            render.console.print("[dim]data:[/dim]")
            render.print_json(exc.data)
        raise typer.Exit(code=1)
    if isinstance(exc, ConfigError):
        render.print_error(str(exc))
        raise typer.Exit(code=2)
    raise exc


@contextmanager
def open_client(ctx: typer.Context) -> Iterator[tuple[ApiClient, Config]]:
    """클라이언트를 열어 (client, config) 를 yield.

    REPL 세션이 공유 클라이언트를 주입한 경우(state.client) 그것을 재사용하고
    닫지 않는다. 그 외에는 일회성 클라이언트를 만들고 종료 시 닫는다.
    TossApiError/ConfigError 는 사용자 친화적 메시지로 변환한다.
    """
    state = get_state(ctx)

    if state.client is not None:
        try:
            yield state.client, state.client.config
        except (TossApiError, ConfigError) as exc:
            _handle_client_errors(exc)
        return

    if state.sim:
        client: ApiClient = SimClient(sim_config(state.account))
    else:
        client = TossClient(_load_config_or_exit(state))
    try:
        yield client, client.config
    except (TossApiError, ConfigError) as exc:
        _handle_client_errors(exc)
    finally:
        client.close()


def output(ctx: typer.Context, data: Any, render_fn) -> None:
    """--json 이면 원본 JSON, --csv 면 CSV, 아니면 render_fn(data) 로 표 출력."""
    state = get_state(ctx)
    if state.csv_output:
        print_csv(data)
    elif state.json_output:
        render.print_json(data)
    else:
        render_fn(data)


# 응답이 dict 일 때 CSV 행 목록으로 쓸 후보 키 (우선순위 순)
_CSV_LIST_KEYS = ("items", "candles", "orders", "asks", "result")


def print_csv(data: Any) -> None:
    """응답을 평탄화해 CSV 로 stdout 에 출력.

    - list[dict] → 그대로 행으로
    - dict 에 items/candles/orders 등 목록 키가 있으면 그 목록을 행으로
    - 그 외 dict → 단일 행
    중첩 dict 값은 'a.b' 형태로 평탄화한다.
    """
    import csv
    import sys

    rows = _csv_rows(data)
    if not rows:
        render.print_warning("CSV 로 변환할 데이터가 없습니다.")
        return
    flat = [_flatten_row(r) for r in rows]
    fields: list[str] = []
    for row in flat:
        for key in row:
            if key not in fields:
                fields.append(key)
    writer = csv.DictWriter(sys.stdout, fieldnames=fields)
    writer.writeheader()
    writer.writerows(flat)


def _csv_rows(data: Any) -> list[dict]:
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        for key in _CSV_LIST_KEYS:
            value = data.get(key)
            if isinstance(value, list) and value and all(isinstance(r, dict) for r in value):
                return value
        return [data]
    return []


def _flatten_row(row: dict, prefix: str = "") -> dict:
    flat: dict[str, Any] = {}
    for key, value in row.items():
        name = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            flat.update(_flatten_row(value, name))
        elif isinstance(value, list):
            flat[name] = ";".join(str(v) for v in value)
        else:
            flat[name] = value
    return flat
