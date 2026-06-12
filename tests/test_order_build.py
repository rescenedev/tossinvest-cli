"""주문 본문 구성 및 검증 로직 테스트 (서버 호출 없음)."""

import pytest

from toss_cli.api import order


def test_quantity_limit_order_body():
    body = order.build_order_body(
        symbol="005930", side="buy", order_type="limit",
        quantity="10", price="70000",
    )
    assert body == {
        "symbol": "005930",
        "side": "BUY",
        "orderType": "LIMIT",
        "quantity": "10",
        "price": "70000",
    }


def test_amount_market_order_body_us():
    body = order.build_order_body(
        symbol="AAPL", side="BUY", order_type="MARKET", order_amount="100.5",
    )
    assert body["orderAmount"] == "100.5"
    assert "price" not in body
    assert "quantity" not in body


def test_optional_fields_included():
    body = order.build_order_body(
        symbol="005930", side="BUY", order_type="LIMIT", quantity="1",
        price="100", time_in_force="cls", client_order_id="abc-1",
        confirm_high_value=True,
    )
    assert body["timeInForce"] == "CLS"
    assert body["clientOrderId"] == "abc-1"
    assert body["confirmHighValueOrder"] is True


def test_limit_requires_price():
    with pytest.raises(order.OrderValidationError):
        order.build_order_body(symbol="005930", side="BUY", order_type="LIMIT", quantity="1")


def test_market_rejects_price():
    with pytest.raises(order.OrderValidationError):
        order.build_order_body(
            symbol="005930", side="BUY", order_type="MARKET", quantity="1", price="100"
        )


def test_quantity_xor_amount_required():
    with pytest.raises(order.OrderValidationError):
        order.build_order_body(symbol="005930", side="BUY", order_type="MARKET")
    with pytest.raises(order.OrderValidationError):
        order.build_order_body(
            symbol="005930", side="BUY", order_type="MARKET",
            quantity="1", order_amount="100",
        )


def test_amount_rejects_kr_symbol():
    # 스펙: orderAmount 는 "주문 금액 (달러)" — US 전용. KR(6자리 숫자) 은 사전 거부.
    with pytest.raises(order.OrderValidationError):
        order.build_order_body(
            symbol="005930", side="BUY", order_type="MARKET", order_amount="100000"
        )


def test_amount_requires_market():
    with pytest.raises(order.OrderValidationError):
        order.build_order_body(
            symbol="AAPL", side="BUY", order_type="LIMIT", order_amount="100", price="1"
        )


def test_kr_tick_size_bands():
    from decimal import Decimal

    cases = [
        ("1500", "1"), ("3000", "5"), ("15000", "10"), ("30000", "50"),
        ("70000", "100"), ("324500", "500"), ("700000", "1000"),
    ]
    for price, tick in cases:
        assert order.kr_tick_size(Decimal(price)) == Decimal(tick), price


def test_invalid_side():
    with pytest.raises(order.OrderValidationError):
        order.build_order_body(symbol="005930", side="HOLD", order_type="MARKET", quantity="1")


def test_quantity_must_be_positive_integer():
    for bad in ("-100", "abc", "0", "1.5"):
        with pytest.raises(order.OrderValidationError):
            order.build_order_body(
                symbol="005930", side="BUY", order_type="MARKET", quantity=bad
            )


def test_modify_body_validates_price_rules():
    with pytest.raises(order.OrderValidationError):
        order.build_modify_body(order_type="LIMIT", quantity="1", price=None)
    with pytest.raises(order.OrderValidationError):
        order.build_modify_body(order_type="MARKET", quantity="1", price="100")
    body = order.build_modify_body(order_type="LIMIT", quantity="5", price="71000")
    assert body == {"orderType": "LIMIT", "quantity": "5", "price": "71000"}
