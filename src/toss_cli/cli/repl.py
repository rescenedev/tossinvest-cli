"""대화형 REPL 셸.

`toss repl` 로 진입하면 토큰/HTTP 클라이언트를 세션 내내 유지한 채
`market price 005930`, `order buy 005930 -q 10 -p 70000` 처럼 명령만 입력한다.
기존 Click 명령 트리를 그대로 재사용하므로 모든 서브커맨드/옵션/도움말이
CLI 와 동일하게 동작한다.

Typer 의 click 백엔드는 배포본에 따라 표준 `click` 이거나 벤더링된
`typer._click` 일 수 있어, 아래 `_click_backend()` 로 양쪽을 모두 지원한다.
prompt_toolkit 이 있으면 히스토리/자동완성, 없으면 input() 으로 폴백한다.
"""

from __future__ import annotations

import re
import shlex
from types import ModuleType

import typer

from ..client import TossClient
from ..config import CONFIG_DIR, ConfigError, load_config
from ..sim import SimClient, reset_state, sim_config
from .. import render
from ._common import AppState, get_state

EXIT_WORDS = {"exit", "quit", ":exit", ":quit", ":q"}
HELP_WORDS = {"help", ":help", "?", ":?"}
HISTORY_FILE = CONFIG_DIR / "repl_history"

# 그룹/명령 숏컷. 예) `m p 005930` → `market price 005930`
GROUP_ALIASES = {
    "m": "market", "s": "stock", "i": "info",
    "a": "account", "o": "order", "au": "auth",
}
CMD_ALIASES = {
    "market": {"p": "price", "ob": "orderbook", "t": "trades", "c": "candles",
               "ch": "chart", "l": "limits"},
    "stock": {"i": "info", "w": "warnings"},
    "info": {"x": "fx", "cal": "calendar"},
    "account": {"l": "list", "h": "holdings", "bp": "buying-power", "se": "sellable"},
    "order": {"b": "buy", "sl": "sell", "l": "list", "g": "get",
              "mod": "modify", "c": "cancel", "cm": "commissions"},
}

# KR: 6자리 영숫자(숫자 시작, 예: 005930·0193T0) | US: 대문자 티커 (예: AAPL·BRK.B)
_SYMBOL_RE = re.compile(r"[0-9][0-9A-Z]{5}|[A-Z][A-Z0-9.]{0,9}")
_QTY_RE = re.compile(r"([+-]?)(\d{1,5})")  # 수량 (부호 + 1~5자리). 음수=매도
_PRICE_RE = re.compile(r"\d+(\.\d+)?")


def _click_backend() -> ModuleType:
    """현재 Typer 가 사용하는 click 모듈(표준 또는 벤더링)을 반환."""
    try:
        import click  # type: ignore

        return click
    except ImportError:  # 벤더링된 click (typer._click)
        from typer import _click  # type: ignore

        return _click


_click = _click_backend()
ClickException = _click.ClickException
Abort = _click.exceptions.Abort


def _is_group(command: object) -> bool:
    """그룹(하위 명령을 가진 멀티커맨드)인지 판별."""
    return isinstance(getattr(command, "commands", None), dict)


def run_repl(ctx: typer.Context) -> None:
    """REPL 진입점. 글로벌 옵션(account/json)을 세션 기본값으로 사용."""
    state = get_state(ctx)
    sim = state.sim

    if not sim:
        try:
            config = load_config().with_account(state.account)
            client: object = TossClient(config)
        except ConfigError:
            # 자격증명이 없으면 에러 대신 시뮬레이션 모드로 자동 전환.
            render.print_warning("자격증명이 없어 시뮬레이션 모드로 시작합니다. (실거래는 --sim 없이 자격증명 설정 후)")
            sim = True

    if sim:
        config = sim_config(state.account)
        client = SimClient(config)

    # 세션 동안 공유할 단일 클라이언트
    session_state = AppState(
        account=config.account_seq,
        json_output=state.json_output,
        sim=sim,
        client=client,
    )

    # Typer 앱 → Click 명령 트리 (지연 import 로 순환참조 방지).
    from .app import app as typer_app

    command = typer.main.get_command(typer_app)

    _print_banner(config, session_state.sim)
    prompt = _make_prompt(command)

    try:
        while True:
            try:
                line = prompt("toss> ")
            except EOFError:  # Ctrl-D
                break
            except KeyboardInterrupt:  # Ctrl-C: 현재 입력만 취소
                continue

            line = line.strip()
            if not line:
                continue
            if line in EXIT_WORDS:
                break
            if line in HELP_WORDS:
                _print_help(command)
                continue
            if line.startswith(":"):
                if _handle_meta(line, session_state):
                    continue

            _dispatch(command, line, session_state)
    finally:
        client.close()
        render.console.print("[dim]세션을 종료합니다.[/dim]")


def _dispatch(command, line: str, session_state: AppState) -> None:
    """한 줄을 파싱·확장해 Click 명령 트리로 실행. 예외는 잡아 셸을 유지."""
    try:
        tokens = shlex.split(line)
    except ValueError as exc:
        render.print_error(f"입력 파싱 실패: {exc}")
        return

    args = expand_aliases(tokens)

    try:
        command.main(
            args=args,
            prog_name="toss",
            standalone_mode=False,
            obj=session_state,
        )
    except Abort:
        render.print_warning("중단했습니다.")
    except ClickException as exc:
        exc.show()  # 사용법/인자 오류 등은 Click 형식으로 표시
    except typer.Exit:
        pass  # open_client 등에서 발생한 정상 종료 신호 — 셸은 유지
    except KeyboardInterrupt:
        render.print_warning("중단했습니다.")
    except Exception as exc:  # noqa: BLE001 - 셸이 죽지 않도록 최종 방어
        render.print_error(f"{type(exc).__name__}: {exc}")


def expand_aliases(tokens: list[str]) -> list[str]:
    """숏컷/베어심볼 입력을 정식 명령 인자로 확장.

    - `m p 005930`      → market price 005930
    - `005930`          → market price 005930
    - `005930 000660`   → market price 005930 000660
    - `005930 100`      → order buy 005930 -q 100 -t MARKET
    - `005930 -100`     → order sell 005930 -q 100 -t MARKET   (음수=매도)
    - `005930 100 70000`→ order buy 005930 -q 100 -p 70000     (지정가)
    """
    if not tokens:
        return tokens

    first = tokens[0]

    # 단독 숏컷: p → 보유 종목(포트폴리오). 뒤 인자는 holdings 옵션으로 통과 (예: p -s 005930)
    if first in ("p", "port", "포트"):
        return ["account", "holdings", *tokens[1:]]

    # 단독 숏컷: c <심볼> → 캔들 차트 (추세 보기)
    if first in ("c", "chart", "차트") and len(tokens) >= 2:
        return ["market", "chart", *tokens[1:]]

    if _SYMBOL_RE.fullmatch(first):
        return _expand_symbol(tokens)

    group = GROUP_ALIASES.get(first, first)
    out = [group]
    if len(tokens) >= 2:
        cmd_map = CMD_ALIASES.get(group, {})
        out.append(cmd_map.get(tokens[1], tokens[1]))
        out.extend(tokens[2:])
    return out


def _expand_symbol(tokens: list[str]) -> list[str]:
    symbol = tokens[0]
    rest = tokens[1:]

    # 모두 심볼이면 다중 현재가 조회.
    if all(_SYMBOL_RE.fullmatch(t) for t in tokens):
        return ["market", "price", *tokens]

    qty_match = _QTY_RE.fullmatch(rest[0]) if rest else None
    if qty_match:
        sign, num = qty_match.groups()
        side = "sell" if sign == "-" else "buy"
        args = ["order", side, symbol, "-q", num]
        extra = rest[1:]
        if extra and _PRICE_RE.fullmatch(extra[0]):
            args += ["-p", extra[0]]   # 지정가
            extra = extra[1:]
        else:
            args += ["-t", "MARKET"]   # 가격 없으면 시장가
        args += extra                  # 나머지 플래그(-y 등) 통과
        return args

    # 그 외에는 현재가 조회로 폴백.
    return ["market", "price", symbol, *rest]


def _handle_meta(line: str, session_state: AppState) -> bool:
    """`:` 로 시작하는 메타 명령 처리. 처리했으면 True."""
    parts = line.split()
    cmd = parts[0]
    if cmd == ":reset":
        if not session_state.sim:
            render.print_warning(":reset 는 시뮬레이션 모드에서만 사용할 수 있습니다.")
            return True
        reset_state()
        if isinstance(session_state.client, SimClient):
            session_state.client.reload()
        render.print_success("시뮬레이션 상태(예수금/포지션/주문)를 초기화했습니다.")
        return True
    if cmd in (":account", ":use"):
        if len(parts) < 2:
            render.print_warning("사용법: :account <accountSeq>")
            return True
        try:
            seq = int(parts[1])
        except ValueError:
            render.print_error(f"accountSeq 는 정수여야 합니다: {parts[1]}")
            return True
        client = session_state.client
        assert client is not None
        client.use_account(seq)
        session_state.account = seq
        render.print_success(f"계좌를 {seq} 로 변경했습니다.")
        return True
    if cmd == ":json":
        session_state.json_output = not session_state.json_output
        render.print_success(f"JSON 출력: {'켜짐' if session_state.json_output else '꺼짐'}")
        return True
    if cmd == ":tick":
        if not session_state.sim:
            render.print_warning(":tick 는 시뮬레이션 모드에서만 사용할 수 있습니다.")
            return True
        try:
            pct = float(parts[1]) if len(parts) > 1 else 1.0
        except ValueError:
            render.print_error(f"퍼센트 값이 숫자가 아닙니다: {parts[1]}")
            return True
        client = session_state.client
        assert isinstance(client, SimClient)
        total = client.shift_price(pct)
        render.print_success(f"모의 시세를 {pct:+g}% 이동했습니다. (누적 {total:+g}%)  `p` 로 손익 확인")
        return True
    if cmd in (":clear", ":cls"):
        render.console.clear()
        return True
    render.print_warning(f"알 수 없는 메타 명령: {cmd} (:help 참고)")
    return True


def _print_banner(config, sim: bool) -> None:
    acct = config.account_seq if config.account_seq is not None else "(미설정)"
    mode = "[bold yellow]SIM[/bold yellow] " if sim else ""
    render.console.print(
        f"{mode}[bold cyan]토스증권 Open API REPL[/bold cyan]  "
        f"[dim]계좌={acct} · base={config.base_url}[/dim]"
    )
    render.console.print(
        "[dim]명령 입력. 예) [/dim][green]m p 005930[/green][dim] · "
        "[/dim][green]005930[/green][dim](시세) · [/dim]"
        "[green]005930 100[/green][dim](100주 매수) · "
        "도움말: [/dim][green]?[/green][dim] · 종료: exit[/dim]"
    )


def _print_help(command) -> None:
    _print_command_reference(command)
    render.key_values(
        "메타 명령",
        [
            ("개별 도움말", "<명령> --help  (예: order buy --help)"),
            (":account <seq>", "세션 계좌 변경"),
            (":json", "JSON 출력 토글"),
            (":tick [%]", "모의 시세 이동 (sim 전용, 기본 +1%) → 손익 변화"),
            (":reset", "시뮬레이션 상태 초기화 (sim 전용)"),
            (":clear", "화면 지우기"),
            ("exit / quit / Ctrl-D", "종료"),
        ],
    )
    render.table(
        "숏컷",
        ["입력", "동작"],
        [
            ("p", "보유 종목 (수량/손익/매수일)"),
            ("c 005930", "캔들 차트 (추세 확인, c AAPL -i 1m 도 가능)"),
            ("m p 005930", "market price 005930 (그룹/명령 약어)"),
            ("005930", "현재가 조회"),
            ("005930 000660", "여러 종목 현재가"),
            ("005930 100", "100주 시장가 매수"),
            ("005930 -100", "100주 시장가 매도 (음수=매도)"),
            ("005930 100 70000", "100주 지정가(70000) 매수"),
            ("005930 100 -y", "확인 없이 매수"),
        ],
    )
    render.console.print(
        "[dim]약어 — 그룹: m=market s=stock i=info a=account o=order · "
        "예: o b(order buy), a h(account holdings), m ob(orderbook)[/dim]"
    )


def _print_command_reference(command) -> None:
    """Typer 명령 트리에서 전체 서브커맨드를 약어와 함께 나열."""
    reverse_group = {full: short for short, full in GROUP_ALIASES.items()}
    rows = []
    for gname in sorted(getattr(command, "commands", {})):
        group = command.commands[gname]
        subcommands = getattr(group, "commands", None)
        if not subcommands:
            rows.append((gname, "", _short_help(group)))
            continue
        galias = reverse_group.get(gname)
        alias_map = {full: short for short, full in CMD_ALIASES.get(gname, {}).items()}
        for cname in sorted(subcommands):
            alias = alias_map.get(cname)
            shortcut = f"{galias} {alias}" if galias and alias else ""
            rows.append((f"{gname} {cname}", shortcut, _short_help(subcommands[cname])))
    render.table("전체 명령", ["명령", "약어", "설명"], rows)


def _short_help(cmd) -> str:
    text = (getattr(cmd, "help", None) or getattr(cmd, "short_help", None) or "").strip()
    return text.splitlines()[0] if text else ""


def _make_prompt(command):
    """prompt_toolkit 이 있으면 히스토리/자동완성 프롬프트, 없으면 input().

    stdin 이 TTY 가 아니면(파이프/스크립트) 라인 기반 input() 으로 폴백한다.
    """
    import sys

    if not sys.stdin.isatty():
        return lambda msg: input(msg)
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import NestedCompleter
        from prompt_toolkit.history import FileHistory
    except ImportError:
        return lambda msg: input(msg)

    completer = NestedCompleter.from_nested_dict(_completion_tree(command))
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    session = PromptSession(
        history=FileHistory(str(HISTORY_FILE)),
        completer=completer,
        complete_while_typing=True,
    )
    return lambda msg: session.prompt(msg)


def _completion_tree(command) -> dict:
    """Click 명령 트리에서 자동완성용 중첩 dict 를 구성."""
    tree: dict[str, object] = {}
    for name, sub in getattr(command, "commands", {}).items():
        if _is_group(sub):
            tree[name] = {child: None for child in sub.commands}
        else:
            tree[name] = None
    # 그룹 약어를 동일한 하위 트리로 매핑.
    for alias, full in GROUP_ALIASES.items():
        if full in tree:
            tree[alias] = tree[full]
    for meta in ("p", "help", "exit", "quit", ":account", ":json", ":tick", ":reset", ":clear"):
        tree.setdefault(meta, None)
    return tree
