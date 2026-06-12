"""rich 기반 출력 헬퍼. 표/JSON/패널을 일관되게 렌더링."""

from __future__ import annotations

import json
from typing import Any, Iterable, Sequence

from rich.console import Console
from rich.json import JSON
from rich.table import Table

console = Console()
err_console = Console(stderr=True)


def print_json(data: Any) -> None:
    console.print(JSON(json.dumps(data, ensure_ascii=False, default=str)))


def print_error(message: str) -> None:
    err_console.print(f"[bold red]오류:[/bold red] {message}")


def print_success(message: str) -> None:
    console.print(f"[bold green]✓[/bold green] {message}")


def print_warning(message: str) -> None:
    console.print(f"[bold yellow]![/bold yellow] {message}")


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
