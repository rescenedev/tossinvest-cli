"""주문/거래 커맨드: buy, sell, list, get, modify, cancel, commissions.

거래는 되돌리기 어려우므로 기본적으로 확인 프롬프트를 거칩니다.
--yes 로 건너뛸 수 있고, --dry-run 으로 전송 없이 요청만 미리 볼 수 있습니다.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

import typer

from ..api import order
from ..config import flag_enabled
from .. import render
from ._common import get_state, open_client, output

HIGH_VALUE_KRW = 100_000_000

app = typer.Typer(help="주문/거래 (매수/매도/조회/정정/취소/수수료)")


def _place(
    ctx: typer.Context,
    *,
    side: str,
    symbol: str,
    order_type: str,
    quantity: str | None,
    amount: str | None,
    price: str | None,
    tif: str | None,
    client_order_id: str | None,
    confirm_high_value: bool,
    yes: bool,
    dry_run: bool,
) -> None:
    """매수/매도 공통 처리: 본문 구성 → 확인 → 전송."""
    sim = get_state(ctx).sim
    if side == "SELL" and not sim and not dry_run and flag_enabled("TOSS_NO_SELL"):
        render.print_error(
            "TOSS_NO_SELL 설정으로 실거래 매도가 차단되어 있습니다. "
            "(.env 의 TOSS_NO_SELL 을 제거하면 해제)"
        )
        raise typer.Exit(code=2)

    if client_order_id is None:
        # 멱등키 자동 생성 — 네트워크 재시도 시 중복 주문 방지 (스펙: 10분 유효)
        client_order_id = f"toss-cli-{uuid4().hex[:24]}"

    try:
        body = order.build_order_body(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            order_amount=amount,
            price=price,
            time_in_force=tif,
            client_order_id=client_order_id,
            confirm_high_value=confirm_high_value,
        )
    except order.OrderValidationError as exc:
        render.print_error(str(exc))
        raise typer.Exit(code=2)

    estimated = _estimated_amount(quantity, price)
    side_kr = "매수" if side == "BUY" else "매도"
    render.key_values(
        f"{side_kr} 주문 확인",
        [
            ("종목", symbol),
            ("방향", f"{side} ({side_kr})"),
            ("호가유형", order_type),
            ("수량", quantity),
            ("금액", amount),
            ("가격", render.fmt_decimal(price) if price else None),
            ("예상 금액", render.fmt_decimal(estimated) if estimated is not None else None),
            ("유효조건", tif or "DAY"),
            ("멱등키", client_order_id),
        ],
    )

    if (tick := order.kr_tick_misaligned(symbol, price)) is not None:
        render.print_warning(
            f"가격이 KRX 주식 호가 단위({tick}원)에 맞지 않습니다. "
            "주식이라면 서버가 거부할 수 있습니다 (ETF 등은 단위가 다를 수 있음)."
        )
    if (
        estimated is not None and estimated >= HIGH_VALUE_KRW
        and order._is_kr_symbol(symbol) and not confirm_high_value
    ):
        render.print_warning("1억원 이상 주문 — 전송하려면 --confirm-high-value 가 필요합니다.")

    if dry_run:
        render.print_warning("dry-run: 실제 주문을 전송하지 않습니다. 요청 본문:")
        render.print_json(body)
        return

    # 1억 이상 KR 주문은 플래그 없이는 서버도 거부하므로 전송 전에 차단.
    if (
        estimated is not None and estimated >= HIGH_VALUE_KRW
        and order._is_kr_symbol(symbol) and not confirm_high_value
    ):
        render.print_error("1억원 이상 주문은 --confirm-high-value 플래그가 필요합니다.")
        raise typer.Exit(code=2)

    if not yes and not sim:  # 시뮬레이션은 가짜 거래이므로 확인 생략
        confirmed = typer.confirm(f"위 내용으로 {side_kr} 주문을 전송할까요?")
        if not confirmed:
            render.print_warning("취소했습니다.")
            raise typer.Exit(code=0)

    with open_client(ctx) as (client, config):
        data = order.create_order(client, config.require_account(), body)
    order_id = data.get("orderId") if isinstance(data, dict) else None
    tag = "[SIM] " if sim else ""
    render.print_success(f"{tag}{side_kr} 주문 접수됨. orderId={order_id}")
    output(ctx, data, lambda d: None)


@app.command("buy")
def buy(
    ctx: typer.Context,
    symbol: str = typer.Argument(..., help="종목 심볼"),
    quantity: str = typer.Option(None, "--quantity", "-q", help="주문 수량 (정수)"),
    amount: str = typer.Option(None, "--amount", help="주문 금액 (US MARKET 전용)"),
    order_type: str = typer.Option("LIMIT", "--type", "-t", help="LIMIT | MARKET"),
    price: str = typer.Option(None, "--price", "-p", help="지정가 (LIMIT 필수)"),
    tif: str = typer.Option(None, "--tif", help="DAY | CLS"),
    client_order_id: str = typer.Option(None, "--id", help="멱등성 키 (재전송 방지)"),
    confirm_high_value: bool = typer.Option(
        False, "--confirm-high-value", help="1억원 이상 주문 확인 플래그"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="확인 프롬프트 건너뛰기"),
    dry_run: bool = typer.Option(False, "--dry-run", help="전송 없이 요청만 출력"),
) -> None:
    """매수 주문."""
    _place(
        ctx, side="BUY", symbol=symbol, order_type=order_type, quantity=quantity,
        amount=amount, price=price, tif=tif, client_order_id=client_order_id,
        confirm_high_value=confirm_high_value, yes=yes, dry_run=dry_run,
    )


@app.command("sell")
def sell(
    ctx: typer.Context,
    symbol: str = typer.Argument(..., help="종목 심볼"),
    quantity: str = typer.Option(None, "--quantity", "-q", help="주문 수량 (정수)"),
    amount: str = typer.Option(None, "--amount", help="주문 금액 (US MARKET 전용)"),
    order_type: str = typer.Option("LIMIT", "--type", "-t", help="LIMIT | MARKET"),
    price: str = typer.Option(None, "--price", "-p", help="지정가 (LIMIT 필수)"),
    tif: str = typer.Option(None, "--tif", help="DAY | CLS"),
    client_order_id: str = typer.Option(None, "--id", help="멱등성 키 (재전송 방지)"),
    confirm_high_value: bool = typer.Option(
        False, "--confirm-high-value", help="1억원 이상 주문 확인 플래그"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="확인 프롬프트 건너뛰기"),
    dry_run: bool = typer.Option(False, "--dry-run", help="전송 없이 요청만 출력"),
) -> None:
    """매도 주문."""
    _place(
        ctx, side="SELL", symbol=symbol, order_type=order_type, quantity=quantity,
        amount=amount, price=price, tif=tif, client_order_id=client_order_id,
        confirm_high_value=confirm_high_value, yes=yes, dry_run=dry_run,
    )


@app.command("list")
def list_orders(
    ctx: typer.Context,
    status: str = typer.Option("OPEN", "--status", "-s", help="OPEN | CLOSED"),
    symbol: str = typer.Option(None, "--symbol", help="종목 필터"),
    date_from: str = typer.Option(None, "--from", help="시작일 (YYYY-MM-DD)"),
    date_to: str = typer.Option(None, "--to", help="종료일 (YYYY-MM-DD)"),
    limit: int = typer.Option(None, "--limit", "-n", help="조회 건수"),
    cursor: str = typer.Option(None, "--cursor", help="페이지 커서"),
    all_pages: bool = typer.Option(False, "--all", help="모든 페이지 자동 조회"),
) -> None:
    """주문 목록 조회."""
    with open_client(ctx) as (client, config):
        if all_pages:
            data = order.list_all_orders(
                client, config.require_account(), status.upper(),
                symbol=symbol, date_from=date_from, date_to=date_to, limit=limit,
            )
        else:
            data = order.list_orders(
                client, config.require_account(), status.upper(),
                symbol=symbol, date_from=date_from, date_to=date_to,
                cursor=cursor, limit=limit,
            )
    output(ctx, data, _render_orders)


@app.command("get")
def get_order(
    ctx: typer.Context,
    order_id: str = typer.Argument(..., help="주문 ID"),
) -> None:
    """주문 단건 조회."""
    with open_client(ctx) as (client, config):
        data = order.get_order(client, config.require_account(), order_id)
    output(ctx, data, lambda d: render.key_values("주문", list(d.items()) if isinstance(d, dict) else []))


@app.command("modify")
def modify_order(
    ctx: typer.Context,
    order_id: str = typer.Argument(..., help="주문 ID"),
    order_type: str = typer.Option("LIMIT", "--type", "-t", help="LIMIT | MARKET"),
    quantity: str = typer.Option(None, "--quantity", "-q", help="정정 수량"),
    price: str = typer.Option(None, "--price", "-p", help="정정 가격"),
    confirm_high_value: bool = typer.Option(False, "--confirm-high-value"),
    yes: bool = typer.Option(False, "--yes", "-y", help="확인 프롬프트 건너뛰기"),
) -> None:
    """주문 정정."""
    try:  # 확인 프롬프트 전에 본문 규칙 검증
        order.build_modify_body(
            order_type=order_type, quantity=quantity, price=price,
            confirm_high_value=confirm_high_value,
        )
    except order.OrderValidationError as exc:
        render.print_error(str(exc))
        raise typer.Exit(code=2)
    if not yes and not get_state(ctx).sim and not typer.confirm(f"주문 {order_id} 을(를) 정정할까요?"):
        render.print_warning("취소했습니다.")
        raise typer.Exit(code=0)
    with open_client(ctx) as (client, config):
        data = order.modify_order(
            client, config.require_account(), order_id,
            order_type=order_type, quantity=quantity, price=price,
            confirm_high_value=confirm_high_value,
        )
    render.print_success(f"정정 접수됨. orderId={data.get('orderId') if isinstance(data, dict) else data}")


@app.command("cancel")
def cancel_order(
    ctx: typer.Context,
    order_id: str = typer.Argument(..., help="주문 ID"),
    yes: bool = typer.Option(False, "--yes", "-y", help="확인 프롬프트 건너뛰기"),
) -> None:
    """주문 취소."""
    if not yes and not get_state(ctx).sim and not typer.confirm(f"주문 {order_id} 을(를) 취소할까요?"):
        render.print_warning("취소하지 않았습니다.")
        raise typer.Exit(code=0)
    with open_client(ctx) as (client, config):
        data = order.cancel_order(client, config.require_account(), order_id)
    render.print_success(f"취소 접수됨. orderId={data.get('orderId') if isinstance(data, dict) else data}")


@app.command("commissions")
def commissions(ctx: typer.Context) -> None:
    """매매 수수료 조회."""
    with open_client(ctx) as (client, config):
        data = order.get_commissions(client, config.require_account())
    output(ctx, data, lambda d: render.print_json(d))


def _estimated_amount(quantity: str | None, price: str | None) -> Decimal | None:
    """지정가 주문의 수량×가격 예상 금액 (계산 불가하면 None)."""
    if not quantity or not price:
        return None
    try:
        return Decimal(quantity) * Decimal(price)
    except InvalidOperation:
        return None


# -- renderers -----------------------------------------------------------
def _render_orders(data: Any) -> None:
    orders = data.get("orders", []) if isinstance(data, dict) else (data or [])
    rows = [
        (
            o.get("orderId"),
            o.get("symbol"),
            o.get("side"),
            o.get("orderType"),
            o.get("status"),
            o.get("price"),
            o.get("quantity"),
            o.get("orderedAt"),
        )
        for o in orders
    ]
    render.table(
        "주문 목록",
        ["orderId", "종목", "방향", "유형", "상태", "가격", "수량", "주문시각"],
        rows,
    )
    if isinstance(data, dict) and data.get("hasNext"):
        render.console.print(f"[dim]다음 페이지: --cursor {data.get('nextCursor')}[/dim]")
