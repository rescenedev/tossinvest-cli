"""관심종목(watchlist) 커맨드: add, rm, show, groups, group, clear.

그룹(폴더) 단위로 심볼을 관리하며 ~/.toss-cli/watchlist.json 에 저장된다.
show 는 그룹별 시세판(전일 대비 등락순)이고 --watch 로 실시간 갱신한다
(전일 종가는 시작 시 1회만 조회, 갱신 루프는 배치 현재가 1콜).
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any

import typer

from ..api import market_data
from ..config import CONFIG_DIR, atomic_write
from .. import render
from ._alias import AliasGroup
from ._common import open_client, output

WATCHLIST_FILE = CONFIG_DIR / "watchlist.json"
DEFAULT_GROUP = "기본"

app = typer.Typer(help="관심종목 시세판 (그룹별 관리 · 전일 대비 등락순)", cls=AliasGroup)
group_app = typer.Typer(help="관심종목 그룹(폴더) 관리", cls=AliasGroup)
app.add_typer(group_app, name="group")


# -- storage ---------------------------------------------------------------
def _load_groups() -> dict[str, list[str]]:
    if not WATCHLIST_FILE.exists():
        return {}
    try:
        data = json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if isinstance(data, list):  # 구버전(플랫 목록) 마이그레이션
        return {DEFAULT_GROUP: [s for s in data if isinstance(s, str)]}
    if isinstance(data, dict) and isinstance(data.get("groups"), dict):
        return {
            str(name): [s for s in syms if isinstance(s, str)]
            for name, syms in data["groups"].items()
            if isinstance(syms, list)
        }
    return {}


def _save_groups(groups: dict[str, list[str]]) -> None:
    atomic_write(WATCHLIST_FILE, json.dumps({"groups": groups}, ensure_ascii=False))


def _normalize(symbol: str) -> str:
    # KR 코드(숫자 시작)는 그대로, 미국 티커는 대문자로 통일
    return symbol if symbol[:1].isdigit() else symbol.upper()


# -- 종목 관리 ----------------------------------------------------------------
@app.command("add")
def add(
    symbols: list[str] = typer.Argument(..., help="추가할 종목 심볼"),
    group: str = typer.Option(DEFAULT_GROUP, "--group", "-g", help="대상 그룹 (없으면 생성)"),
) -> None:
    """관심종목 추가."""
    groups = dict(_load_groups())
    current = list(groups.get(group, []))
    added = [s for s in (_normalize(x) for x in symbols) if s not in current]
    groups[group] = current + added
    _save_groups(groups)
    render.print_success(
        f"[{group}] 추가됨: {', '.join(added) or '(이미 전부 등록됨)'} · {len(groups[group])}종목"
    )


@app.command("rm")
def rm(
    symbols: list[str] = typer.Argument(..., help="제거할 종목 심볼"),
    group: str = typer.Option(None, "--group", "-g", help="대상 그룹 (미지정 시 전 그룹)"),
) -> None:
    """관심종목 제거."""
    targets = {_normalize(x) for x in symbols}
    groups = {
        name: [s for s in syms if s not in targets] if (group is None or name == group) else syms
        for name, syms in _load_groups().items()
    }
    _save_groups(groups)
    render.print_success("제거 완료 · " + " · ".join(f"{n} {len(s)}종목" for n, s in groups.items()))


@app.command("clear")
def clear(
    group: str = typer.Option(None, "--group", "-g", help="특정 그룹만 비우기"),
    yes: bool = typer.Option(False, "--yes", "-y", help="확인 생략"),
) -> None:
    """관심종목 비우기 (그룹 미지정 시 전체)."""
    scope = f"그룹 [{group}]" if group else "관심종목 전체"
    if not yes and not typer.confirm(f"{scope}를 비울까요?"):
        render.print_warning("취소했습니다.")
        raise typer.Exit(code=0)
    if group:
        groups = {n: s for n, s in _load_groups().items() if n != group}
        _save_groups(groups)
    else:
        _save_groups({})
    render.print_success(f"{scope}를 비웠습니다.")


# -- 그룹 관리 ----------------------------------------------------------------
@app.command("groups")
def list_groups() -> None:
    """그룹 목록."""
    groups = _load_groups()
    if not groups:
        render.print_warning("그룹이 없습니다. 예: toss watchlist add 005930 -g 반도체")
        return
    render.table(
        "관심종목 그룹",
        ["그룹", "종목 수", "종목"],
        [(name, len(syms), " ".join(syms[:8]) + (" …" if len(syms) > 8 else ""))
         for name, syms in groups.items()],
    )


@group_app.command("create")
def group_create(name: str = typer.Argument(..., help="그룹 이름")) -> None:
    """빈 그룹 생성."""
    groups = dict(_load_groups())
    if name in groups:
        render.print_warning(f"이미 존재하는 그룹입니다: {name}")
        raise typer.Exit(code=1)
    groups[name] = []
    _save_groups(groups)
    render.print_success(f"그룹 생성됨: {name}")


@group_app.command("rename")
def group_rename(
    old: str = typer.Argument(..., help="기존 이름"),
    new: str = typer.Argument(..., help="새 이름"),
) -> None:
    """그룹 이름 변경."""
    groups = dict(_load_groups())
    if old not in groups:
        render.print_error(f"그룹이 없습니다: {old}")
        raise typer.Exit(code=1)
    groups[new] = groups.pop(old)
    _save_groups(groups)
    render.print_success(f"그룹 이름 변경: {old} → {new}")


@group_app.command("delete")
def group_delete(
    name: str = typer.Argument(..., help="삭제할 그룹"),
    yes: bool = typer.Option(False, "--yes", "-y", help="확인 생략"),
) -> None:
    """그룹 삭제 (종목 포함)."""
    groups = dict(_load_groups())
    if name not in groups:
        render.print_error(f"그룹이 없습니다: {name}")
        raise typer.Exit(code=1)
    if not yes and not typer.confirm(f"그룹 [{name}] ({len(groups[name])}종목) 을 삭제할까요?"):
        render.print_warning("취소했습니다.")
        raise typer.Exit(code=0)
    del groups[name]
    _save_groups(groups)
    render.print_success(f"그룹 삭제됨: {name}")


# -- 시세판 -------------------------------------------------------------------
@app.command("show")
def show(
    ctx: typer.Context,
    group: str = typer.Option(None, "--group", "-g", help="특정 그룹만"),
    watch: float = typer.Option(None, "--watch", "-w", help="N초 간격 갱신 (Ctrl-C 종료)"),
) -> None:
    """관심종목 시세판 — 그룹별, 전일 대비 등락률 순 정렬."""
    groups = _load_groups()
    if group is not None:
        if group not in groups:
            render.print_error(f"그룹이 없습니다: {group}")
            raise typer.Exit(code=1)
        groups = {group: groups[group]}
    groups = {n: s for n, s in groups.items() if s}
    if not groups:
        render.print_warning("관심종목이 없습니다. 예: toss watchlist add 005930 AAPL (REPL: wl add 005930)")
        return

    all_symbols = sorted({s for syms in groups.values() for s in syms})

    from .market import _watch  # 공용 watch 루프

    with open_client(ctx) as (client, _config):
        prev_closes = _fetch_prev_closes(client, all_symbols)  # 갱신 루프 밖에서 1회만

        def draw():
            prices = market_data.get_prices(client, all_symbols)  # 배치 1콜
            for name, syms in groups.items():
                _render_board(name, syms, prices, prev_closes)

        if watch:
            _watch(draw, max(1.0, watch))
            return
        prices = market_data.get_prices(client, all_symbols)

    def render_all(rows: Any) -> None:
        for name, syms in groups.items():
            _render_board(name, syms, rows, prev_closes)

    output(ctx, prices, render_all)


def _fetch_prev_closes(client, symbols: list[str]) -> dict[str, Decimal]:
    """종목별 전일 종가. 실패하거나 이력이 없으면 생략."""
    closes: dict[str, Decimal] = {}
    for symbol in symbols:
        try:
            data = market_data.get_candles(client, symbol, "1d", 2, None, None)
            candles = (data or {}).get("candles", [])
            # 최신순: [0]=오늘(진행 중), [1]=전일. 이력이 1개뿐이면 시가 대비.
            raw = candles[1]["closePrice"] if len(candles) >= 2 else candles[0]["openPrice"]
            closes[symbol] = Decimal(raw)
        except Exception:
            continue
    return closes


def _render_board(
    title: str, symbols: list[str], prices: Any, prev_closes: dict[str, Decimal]
) -> None:
    by_symbol = {p.get("symbol"): p for p in (prices or []) if isinstance(p, dict)}
    rows = []
    for symbol in symbols:
        p = by_symbol.get(symbol, {})
        last_raw = p.get("lastPrice")
        change = _change_pct(last_raw, prev_closes.get(symbol))
        rows.append((symbol, last_raw, p.get("currency"), change))

    rows.sort(key=lambda r: r[3] if r[3] is not None else Decimal("-9999"), reverse=True)
    table_rows = []
    for symbol, last_raw, currency, change in rows:
        if change is None:
            change_text = "[dim]-[/dim]"
        else:
            color = "red" if change > 0 else "blue" if change < 0 else "white"
            change_text = f"[{color}]{change:+.2f}%[/{color}]"
        table_rows.append((symbol, render.fmt_decimal(last_raw), change_text, currency))
    render.table(f"관심종목 · {title} (전일 대비 등락순)", ["종목", "현재가", "등락", "통화"], table_rows)


def _change_pct(last_raw: Any, prev: Decimal | None) -> Decimal | None:
    if not last_raw or not prev:
        return None
    try:
        return (Decimal(str(last_raw)) - prev) / prev * 100
    except (InvalidOperation, ZeroDivisionError):
        return None
