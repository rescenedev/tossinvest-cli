"""rich 기반 출력 헬퍼. 표/JSON/패널을 일관되게 렌더링."""

from __future__ import annotations

import json
from typing import Any, Iterable, Sequence

from rich.console import Console
from rich.json import JSON
from rich.markup import escape
from rich.table import Table

console = Console()
err_console = Console(stderr=True)


def print_json(data: Any) -> None:
    console.print(JSON(json.dumps(data, ensure_ascii=False, default=str)))


def print_error(message: str) -> None:
    # message 는 사용자/API 데이터 → 대괄호([400 x] 등)가 rich 마크업으로
    # 오인되지 않도록 escape. 라벨만 마크업으로 둔다.
    err_console.print("[bold red]오류:[/bold red]", escape(message))


def print_success(message: str) -> None:
    console.print("[bold green]✓[/bold green]", escape(message))


def print_warning(message: str) -> None:
    console.print("[bold yellow]![/bold yellow]", escape(message))


def table(title: str, columns: Sequence[str], rows: Iterable[Sequence[Any]]) -> None:
    """간단한 표를 출력. 값은 str 로 변환."""
    tbl = Table(title=title, header_style="bold cyan", title_style="bold")
    for col in columns:
        tbl.add_column(col)
    for row in rows:
        tbl.add_row(*[_fmt(c) for c in row])
    console.print(tbl)


def key_values(title: str, pairs: Iterable[tuple[str, Any]]) -> None:
    """key-value 쌍을 2열 표로 출력."""
    tbl = Table(title=title, show_header=False, title_style="bold")
    tbl.add_column("field", style="cyan", no_wrap=True)
    tbl.add_column("value")
    for key, value in pairs:
        tbl.add_row(str(key), _fmt(value))
    console.print(tbl)


def _fmt(value: Any) -> str:
    if value is None:
        return "[dim]-[/dim]"
    if isinstance(value, bool):
        return "예" if value else "아니오"
    return str(value)


def fmt_decimal(value: Any) -> str:
    """천 단위 구분 기호를 넣은 숫자 문자열. 정수는 소수점 없이, 그 외 소수 2자리."""
    from decimal import Decimal, InvalidOperation

    if value is None or value == "":
        return "[dim]-[/dim]"
    try:
        num = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return str(value)
    if num == num.to_integral_value():
        return f"{num:,.0f}"
    return f"{num:,.2f}"


def short_dt(value: Any) -> str:
    """ISO8601 → 'YYYY-MM-DD HH:MM' (없으면 -)."""
    if not value:
        return "[dim]-[/dim]"
    return str(value).replace("T", " ")[:16]
