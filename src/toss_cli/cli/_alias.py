"""명령 약어(prefix) 해석을 지원하는 Typer 그룹.

`toss o list` → `toss order list`, `toss acc h` → `toss account holdings`
처럼 고유하게 식별되는 접두어를 전체 명령으로 풀어 준다.
접두어가 여러 명령에 걸리면(예: 최상위 `a` = account/auth) 후보를 보여 주고 멈춘다.
정확한 이름은 항상 우선하므로 기존 동작은 그대로 유지된다.
"""

from __future__ import annotations

# Typer 가 click 을 벤더링하므로 동일한 타입을 그대로 사용한다.
from typer._click.core import Command, Context
from typer.core import TyperGroup


class AliasGroup(TyperGroup):
    """고유 접두어를 전체 명령 이름으로 해석하는 그룹."""

    def get_command(self, ctx: Context, cmd_name: str) -> Command | None:
        # 1) 정확한 이름이 있으면 그대로.
        exact = super().get_command(ctx, cmd_name)
        if exact is not None:
            return exact

        # 2) 접두어로 시작하는 명령을 찾는다.
        matches = [name for name in self.list_commands(ctx) if name.startswith(cmd_name)]
        if not matches:
            return None
        if len(matches) == 1:
            return super().get_command(ctx, matches[0])

        # 3) 모호하면 후보를 알려 주고 종료.
        candidates = ", ".join(sorted(matches))
        ctx.fail(f"'{cmd_name}' 는 모호합니다. 후보: {candidates}")
