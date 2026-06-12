"""주문/거래(Order) API.

모든 엔드포인트가 계좌 헤더(X-Tossinvest-Account)를 요구합니다.
주문 생성은 수량 기반(quantity)과 금액 기반(orderAmount, US MARKET 전용)을
모두 지원합니다.
"""

from __future__ import annotations

from typing import Any

from ..client import TossClient

SIDES = ("BUY", "SELL")
ORDER_TYPES = ("LIMIT", "MARKET")
TIME_IN_FORCE = ("DAY", "CLS")


class OrderValidationError(ValueError):
    """주문 파라미터 조합이 잘못된 경우 (서버 호출 전 검증)."""


def _is_kr_symbol(symbol: str) -> bool:
    """KRX 심볼 여부. 6자리 영숫자이며 숫자로 시작 (예: 005930, 0193T0).

    US 는 영문 티커(영문 시작)라서 첫 글자로 구분된다.
    """
    return len(symbol) == 6 and symbol[0].isdigit() and symbol.isalnum()


# KRX 주식 호가 단위 (가격 상한 미만 구간 → 단위). ETF/ELW 등은 단위가 다르므로
# 검증은 차단이 아닌 경고로만 사용한다.
KR_TICK_BANDS: tuple[tuple[int, int], ...] = (
    (2_000, 1), (5_000, 5), (20_000, 10), (50_000, 50),
    (200_000, 100), (500_000, 500),
)
KR_TICK_MAX = 1_000


def kr_tick_size(price: "Decimal") -> "Decimal":
    """KRX 주식 가격대별 호가 단위."""
    from decimal import Decimal

    for upper, tick in KR_TICK_BANDS:
        if price < upper:
            return Decimal(tick)
    return Decimal(KR_TICK_MAX)


def kr_tick_misaligned(symbol: str, price: str | None) -> "Decimal | None":
    """KR 지정가가 호가 단위에 맞지 않으면 해당 단위를 반환 (맞으면 None).

    ETF 등 단위가 다른 상품이 있어 차단 근거가 아닌 경고 용도.
    """
    from decimal import Decimal, InvalidOperation

    if not price or not _is_kr_symbol(symbol):
        return None
    try:
        value = Decimal(price)
    except InvalidOperation:
        return None
    tick = kr_tick_size(value)
    return tick if value % tick != 0 else None


def build_order_body(
    *,
    symbol: str,
    side: str,
    order_type: str,
    quantity: str | None = None,
    order_amount: str | None = None,
    price: str | None = None,
    time_in_force: str | None = None,
    client_order_id: str | None = None,
    confirm_high_value: bool = False,
) -> dict[str, Any]:
    """주문 요청 본문을 구성하고 기본 검증을 수행.

    스펙 규칙:
    - quantity 와 order_amount 는 동시에 사용 불가, 하나는 필수.
    - LIMIT 은 price 필수, MARKET 은 price 사용 불가.
    - order_amount(금액 기반)는 MARKET 만 허용.
    """
    side = side.upper()
    order_type = order_type.upper()
    if side not in SIDES:
        raise OrderValidationError(f"side 는 {SIDES} 중 하나여야 합니다: {side}")
    if order_type not in ORDER_TYPES:
        raise OrderValidationError(f"orderType 은 {ORDER_TYPES} 중 하나여야 합니다: {order_type}")

    if (quantity is None) == (order_amount is None):
        raise OrderValidationError("quantity 또는 order_amount 중 정확히 하나를 지정해야 합니다.")

    if order_amount is not None and order_type != "MARKET":
        raise OrderValidationError("금액 기반 주문(order_amount)은 MARKET 만 허용됩니다.")

    if order_amount is not None and _is_kr_symbol(symbol):
        raise OrderValidationError("금액 기반 주문(order_amount)은 미국 주식 전용입니다.")

    if order_type == "LIMIT" and not price:
        raise OrderValidationError("LIMIT 주문은 price 가 필수입니다.")
    if order_type == "MARKET" and price:
        raise OrderValidationError("MARKET 주문에는 price 를 전달할 수 없습니다.")

    body: dict[str, Any] = {
        "symbol": symbol,
        "side": side,
        "orderType": order_type,
    }
    if quantity is not None:
        body["quantity"] = quantity
    if order_amount is not None:
        body["orderAmount"] = order_amount
    if price is not None:
        body["price"] = price
    if time_in_force is not None:
        body["timeInForce"] = time_in_force.upper()
    if client_order_id is not None:
        body["clientOrderId"] = client_order_id
    if confirm_high_value:
        body["confirmHighValueOrder"] = True
    return body


def create_order(client: TossClient, account_seq: int, body: dict[str, Any]) -> Any:
    """주문 생성. OrderOperationResponse({orderId}) 반환."""
    return client.post("/api/v1/orders", json_body=body, account_seq=account_seq)


def list_orders(
    client: TossClient,
    account_seq: int,
    status: str,
    *,
    symbol: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> Any:
    """주문 목록 조회. status: 'OPEN' | 'CLOSED'."""
    return client.get(
        "/api/v1/orders",
        params={
            "status": status,
            "symbol": symbol,
            "from": date_from,
            "to": date_to,
            "cursor": cursor,
            "limit": limit,
        },
        account_seq=account_seq,
    )


MAX_LIST_PAGES = 100


def list_all_orders(
    client: TossClient,
    account_seq: int,
    status: str,
    *,
    symbol: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """주문 목록 전체 페이지를 cursor 를 따라가며 수집."""
    orders: list[Any] = []
    cursor: str | None = None
    for _ in range(MAX_LIST_PAGES):
        page = list_orders(
            client, account_seq, status,
            symbol=symbol, date_from=date_from, date_to=date_to,
            cursor=cursor, limit=limit,
        )
        if not isinstance(page, dict):
            orders.extend(page or [])
            break
        orders.extend(page.get("orders", []))
        if not page.get("hasNext"):
            break
        cursor = page.get("nextCursor")
        if not cursor:
            break
    return {"orders": orders, "hasNext": False}


def get_order(client: TossClient, account_seq: int, order_id: str) -> Any:
    """주문 단건 조회."""
    return client.get(f"/api/v1/orders/{order_id}", account_seq=account_seq)


def modify_order(
    client: TossClient,
    account_seq: int,
    order_id: str,
    *,
    order_type: str,
    quantity: str | None = None,
    price: str | None = None,
    confirm_high_value: bool = False,
) -> Any:
    """주문 정정."""
    body: dict[str, Any] = {"orderType": order_type.upper()}
    if quantity is not None:
        body["quantity"] = quantity
    if price is not None:
        body["price"] = price
    if confirm_high_value:
        body["confirmHighValueOrder"] = True
    return client.post(
        f"/api/v1/orders/{order_id}/modify", json_body=body, account_seq=account_seq
    )


def cancel_order(client: TossClient, account_seq: int, order_id: str) -> Any:
    """주문 취소."""
    return client.post(f"/api/v1/orders/{order_id}/cancel", account_seq=account_seq)


def get_buying_power(client: TossClient, account_seq: int, currency: str) -> Any:
    """매수 가능 금액 조회. currency: KRW | USD."""
    return client.get(
        "/api/v1/buying-power",
        params={"currency": currency},
        account_seq=account_seq,
    )


def get_sellable_quantity(client: TossClient, account_seq: int, symbol: str) -> Any:
    """판매 가능 수량 조회."""
    return client.get(
        "/api/v1/sellable-quantity",
        params={"symbol": symbol},
        account_seq=account_seq,
    )


def get_commissions(client: TossClient, account_seq: int) -> Any:
    """매매 수수료 조회."""
    return client.get("/api/v1/commissions", account_seq=account_seq)
