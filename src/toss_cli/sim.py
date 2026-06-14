"""시뮬레이션(모의) 클라이언트.

실제 자격증명 없이 토스 Open API 와 동일한 인터페이스로 동작한다.
네트워크 호출 없이 결정적(deterministic) 모의 시세를 만들고, 주문은
파일(`~/.toss-cli/sim_state.json`)에 저장해 조회/정정/취소가 이어지게 한다.

API 모듈은 `client.get/post` 만 호출하므로 TossClient 와 교체 가능하다.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping

from .config import CONFIG_DIR, Config, atomic_write
from .errors import TossApiError

SIM_STATE_FILE = CONFIG_DIR / "sim_state.json"
START_CASH = {"KRW": "100000000", "USD": "100000"}  # 모의 초기 예수금


def sim_config(account_seq: int | None) -> Config:
    """시뮬레이션용 더미 설정 (자격증명 불필요)."""
    return Config(
        client_id="SIM",
        client_secret="SIM",
        base_url="sim://local",
        account_seq=account_seq if account_seq is not None else 1,
    )


def is_kr(symbol: str) -> bool:
    return symbol.isdigit()


def price_for(symbol: str) -> tuple[Decimal, str]:
    """심볼에서 결정적 모의 현재가를 만든다."""
    if is_kr(symbol):
        base = 10000 + (int(symbol) % 90000)
        # 100원 호가단위로 정렬
        return Decimal(base - base % 100), "KRW"
    h = sum(ord(c) for c in symbol.upper())
    return Decimal(10 + h % 490), "USD"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal(1)) if value == value.to_integral() else value)


# --------------------------------------------------------------------------
# 상태 (예수금/포지션/주문) 영속화
# --------------------------------------------------------------------------
def _default_state() -> dict[str, Any]:
    return {"cash": dict(START_CASH), "positions": {}, "orders": [],
            "counter": 0, "priceShiftPct": 0.0}


def load_state() -> dict[str, Any]:
    if not SIM_STATE_FILE.exists():
        return _default_state()
    try:
        data = json.loads(SIM_STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _default_state()
    base = _default_state()
    base.update(data if isinstance(data, dict) else {})
    return base


def save_state(state: dict[str, Any]) -> None:
    atomic_write(SIM_STATE_FILE, json.dumps(state, ensure_ascii=False))


def reset_state() -> None:
    save_state(_default_state())


class SimClient:
    """TossClient 와 동일한 표면(get/post/use_account/close/config)을 갖는 모의 클라이언트."""

    def __init__(self, config: Config):
        self._config = config
        self._state = load_state()

    # -- interface -------------------------------------------------------
    @property
    def config(self) -> Config:
        return self._config

    def use_account(self, account_seq: int | None) -> None:
        self._config = self._config.with_account(account_seq)

    def reload(self) -> None:
        """디스크의 시뮬레이션 상태를 다시 읽어들인다 (초기화 후 동기화용)."""
        self._state = load_state()

    # -- 모의 시세 (가격 이동 반영) -------------------------------------
    def _factor(self) -> Decimal:
        return Decimal(1) + Decimal(str(self._state.get("priceShiftPct", 0))) / 100

    def _quote(self, symbol: str) -> tuple[Decimal, str]:
        """현재 모의 시세 = 기준가 × 시장이동계수, 호가단위로 반올림."""
        base, cur = price_for(symbol)
        price = base * self._factor()
        if cur == "KRW":
            price = (price / 100).quantize(Decimal(1)) * 100  # 100원 단위
        else:
            price = price.quantize(Decimal("0.01"))
        return price, cur

    def shift_price(self, pct: float) -> float:
        """전체 모의 시세를 pct% 만큼 이동시키고 누적 이동률을 반환."""
        current = float(self._state.get("priceShiftPct", 0)) + pct
        self._state["priceShiftPct"] = current
        save_state(self._state)
        return current

    def close(self) -> None:
        save_state(self._state)

    def get(self, path: str, *, params: Mapping[str, Any] | None = None,
            account_seq: int | None = None) -> Any:
        return self.request("GET", path, params=params, account_seq=account_seq)

    def post(self, path: str, *, json_body: Any | None = None,
             account_seq: int | None = None) -> Any:
        return self.request("POST", path, json_body=json_body, account_seq=account_seq)

    # -- dispatch --------------------------------------------------------
    def request(self, method: str, path: str, *, params=None, json_body=None,
                account_seq: int | None = None) -> Any:
        params = params or {}
        segs = path.strip("/").split("/")
        result = self._route(method.upper(), segs, params, json_body)
        save_state(self._state)
        return result

    def _route(self, method, segs, params, body) -> Any:
        # /api/v1/...
        tail = segs[2:] if len(segs) >= 2 else segs
        if method == "GET" and tail == ["prices"]:
            return self._prices(params)
        if method == "GET" and tail == ["orderbook"]:
            return self._orderbook(params["symbol"])
        if method == "GET" and tail == ["trades"]:
            return self._trades(params["symbol"], int(params.get("count") or 10))
        if method == "GET" and tail == ["price-limits"]:
            return self._price_limits(params["symbol"])
        if method == "GET" and tail == ["candles"]:
            return self._candles(params["symbol"], int(params.get("count") or 5))
        if method == "GET" and tail == ["stocks"]:
            return [self._stock(s) for s in str(params["symbols"]).split(",")]
        if method == "GET" and len(tail) == 3 and tail[0] == "stocks" and tail[2] == "warnings":
            return []
        if method == "GET" and tail == ["exchange-rate"]:
            return self._exchange_rate(params)
        if method == "GET" and tail[:1] == ["market-calendar"]:
            return self._calendar(tail[1] if len(tail) > 1 else "KR", params.get("date"))
        if method == "GET" and tail == ["accounts"]:
            return self._accounts()
        if method == "GET" and tail == ["holdings"]:
            return self._holdings(params.get("symbol"))
        if method == "GET" and tail == ["buying-power"]:
            return {"currency": params.get("currency", "KRW"),
                    "cashBuyingPower": self._state["cash"].get(params.get("currency", "KRW"), "0")}
        if method == "GET" and tail == ["sellable-quantity"]:
            pos = self._state["positions"].get(params["symbol"])
            return {"sellableQuantity": pos["quantity"] if pos else "0"}
        if method == "GET" and tail == ["commissions"]:
            return [{"marketCountry": "KR", "commissionRate": "0.00015"},
                    {"marketCountry": "US", "commissionRate": "0.0025"}]
        if method == "GET" and tail == ["orders"]:
            return self._list_orders(params)
        if method == "POST" and tail == ["orders"]:
            return self._create_order(body or {})
        if method == "GET" and len(tail) == 2 and tail[0] == "orders":
            return self._get_order(tail[1])
        if method == "POST" and len(tail) == 3 and tail[0] == "orders" and tail[2] == "modify":
            return self._modify_order(tail[1], body or {})
        if method == "POST" and len(tail) == 3 and tail[0] == "orders" and tail[2] == "cancel":
            return self._cancel_order(tail[1])
        raise TossApiError(404, "sim-not-implemented", f"[SIM] 미구현 경로: {method} /{'/'.join(segs)}")

    # -- market data -----------------------------------------------------
    def _prices(self, params) -> list[dict]:
        out = []
        for sym in str(params["symbols"]).split(","):
            price, cur = self._quote(sym)
            out.append({"symbol": sym, "lastPrice": _money(price),
                        "currency": cur, "timestamp": _now()})
        return out

    def _orderbook(self, symbol) -> dict:
        price, cur = self._quote(symbol)
        step = Decimal(100) if cur == "KRW" else Decimal("0.01")
        asks = [{"price": _money(price + step * i), "volume": str(100 * (i + 1))} for i in range(1, 6)]
        bids = [{"price": _money(price - step * i), "volume": str(100 * (i + 1))} for i in range(1, 6)]
        return {"timestamp": _now(), "currency": cur, "asks": asks, "bids": bids}

    def _trades(self, symbol, count) -> list[dict]:
        price, cur = self._quote(symbol)
        return [{"price": _money(price), "volume": str(10 + i), "timestamp": _now(),
                 "currency": cur} for i in range(count)]

    def _price_limits(self, symbol) -> dict:
        price, cur = self._quote(symbol)
        return {"symbol": symbol, "currency": cur,
                "upperLimit": _money(price * Decimal("1.3")),
                "lowerLimit": _money(price * Decimal("0.7"))}

    def _candles(self, symbol, count) -> dict:
        # 스펙(CandlePageResponse) 형태 — 결정적 모의 캔들 (최신순, 일 단위 과거로)
        from datetime import datetime, timedelta, timezone

        price, cur = self._quote(symbol)
        base_dt = datetime.now(timezone.utc)
        candles = []
        for i in range(count):
            wobble = Decimal(1) + Decimal(((i * 7) % 9) - 4) / Decimal(100)  # ±4% 결정적 변동
            close = price * wobble
            candles.append({
                "timestamp": (base_dt - timedelta(days=i)).isoformat(),
                "openPrice": _money(close * Decimal("0.99")),
                "highPrice": _money(close * Decimal("1.02")),
                "lowPrice": _money(close * Decimal("0.97")),
                "closePrice": _money(close),
                "volume": str(10000 + i * 100),
                "currency": cur,
            })
        return {"candles": candles, "nextBefore": None}

    def _stock(self, symbol) -> dict:
        _, cur = price_for(symbol)
        country = "KR" if is_kr(symbol) else "US"
        return {"symbol": symbol, "name": f"[SIM] {symbol}",
                "marketCountry": country, "currency": cur}

    def _exchange_rate(self, params) -> dict:
        return {"baseCurrency": params.get("baseCurrency", "USD"),
                "quoteCurrency": params.get("quoteCurrency", "KRW"),
                "rate": "1350.0", "timestamp": _now()}

    def _calendar(self, country, date) -> dict:
        return {"country": country, "date": date or "2026-06-03",
                "isOpen": True, "openTime": "09:00", "closeTime": "15:30"}

    # -- account ---------------------------------------------------------
    def _accounts(self) -> list[dict]:
        return [{"accountNo": "SIM-0001-01", "accountSeq": 1, "accountType": "BROKERAGE"}]

    def _holdings(self, symbol_filter) -> dict:
        # 스펙(HoldingsOverview) 형태: 요약 금액은 통화별 dict, rate 는 소수비율.
        items = []
        purchase_by_cur: dict[str, Decimal] = {}
        value_by_cur: dict[str, Decimal] = {}
        for sym, pos in self._state["positions"].items():
            if symbol_filter and sym != symbol_filter:
                continue
            qty = Decimal(pos["quantity"])
            if qty == 0:
                continue
            avg = Decimal(pos["avgPrice"])
            last, cur = self._quote(sym)
            purchase = qty * avg
            value = qty * last
            key = cur.lower()
            purchase_by_cur[key] = purchase_by_cur.get(key, Decimal(0)) + purchase
            value_by_cur[key] = value_by_cur.get(key, Decimal(0)) + value
            pl = value - purchase
            rate = (pl / purchase) if purchase else Decimal(0)
            items.append({
                "symbol": sym, "name": f"[SIM] {sym}", "marketCountry": "KR" if is_kr(sym) else "US",
                "currency": cur, "quantity": pos["quantity"],
                "purchasedAt": pos.get("firstBoughtAt"),
                "lastPrice": _money(last), "averagePurchasePrice": _money(avg),
                "marketValue": {"purchaseAmount": _money(purchase), "amount": _money(value),
                                "amountAfterCost": _money(value)},
                "profitLoss": {"amount": _money(pl), "amountAfterCost": _money(pl),
                               "rate": f"{rate:.4f}", "rateAfterCost": f"{rate:.4f}"},
                "dailyProfitLoss": {"amount": "0", "rate": "0.0000"},
                "cost": {"commission": "0", "tax": None},
            })
        # 요약 수익률은 통화 무시 단순 합산 기준 (sim 단순화; 실 API 는 원화 환산).
        total_purchase = sum(purchase_by_cur.values(), Decimal(0))
        total_pl = sum(value_by_cur.values(), Decimal(0)) - total_purchase
        rate = (total_pl / total_purchase) if total_purchase else Decimal(0)
        pl_by_cur = {
            cur: _money(value_by_cur[cur] - purchase_by_cur.get(cur, Decimal(0)))
            for cur in value_by_cur
        }
        return {
            "totalPurchaseAmount": {c: _money(v) for c, v in purchase_by_cur.items()},
            "marketValue": {"amount": {c: _money(v) for c, v in value_by_cur.items()},
                            "amountAfterCost": {c: _money(v) for c, v in value_by_cur.items()}},
            "profitLoss": {"amount": pl_by_cur, "amountAfterCost": pl_by_cur,
                           "rate": f"{rate:.4f}", "rateAfterCost": f"{rate:.4f}"},
            "dailyProfitLoss": {"amount": {}, "rate": "0.0000"},
            "items": items,
        }

    # -- orders ----------------------------------------------------------
    def _create_order(self, body) -> dict:
        client_order_id = body.get("clientOrderId")
        if client_order_id:
            for o in self._state["orders"]:
                if o.get("clientOrderId") == client_order_id:
                    return {"orderId": o["orderId"]}  # 멱등 재반환

        symbol = body["symbol"]
        side = body["side"]
        order_type = body["orderType"]

        # 매도는 보유 수량 내에서만 — 초과 매도로 현금이 부풀지 않게 거부 (실 API 동일)
        if side == "SELL":
            held = Decimal(self._state["positions"].get(symbol, {}).get("quantity", "0"))
            want = Decimal(body.get("quantity") or "0")
            if want > held:
                raise TossApiError(
                    400, "insufficient-quantity",
                    f"[SIM] 매도 가능 수량({held})을 초과했습니다: {want}",
                )

        _, cur = price_for(symbol)
        self._state["counter"] += 1
        order_id = f"SIM-{self._state['counter']:06d}"

        last, _ = self._quote(symbol)
        order: dict[str, Any] = {
            "orderId": order_id, "symbol": symbol, "side": side, "orderType": order_type,
            "timeInForce": body.get("timeInForce", "DAY"), "price": body.get("price"),
            "quantity": body.get("quantity"), "orderAmount": body.get("orderAmount"),
            "currency": cur, "orderedAt": _now(), "canceledAt": None,
            "clientOrderId": client_order_id, "execution": {},
        }

        if order_type == "MARKET":
            # 즉시 체결 시뮬레이션
            if body.get("orderAmount"):
                qty = (Decimal(body["orderAmount"]) / last).quantize(Decimal(1))
            else:
                qty = Decimal(body.get("quantity", "0"))
            self._apply_fill(symbol, side, qty, last)
            order["quantity"] = str(qty)
            order["status"] = "FILLED"
            order["execution"] = {"filledQuantity": str(qty), "filledPrice": _money(last)}
        else:
            order["status"] = "PENDING"  # 지정가는 미체결 상태로 보관

        self._state["orders"].append(order)
        return {"orderId": order_id}

    def _apply_fill(self, symbol, side, qty: Decimal, price: Decimal) -> None:
        positions = self._state["positions"]
        cash = self._state["cash"]
        cur = price_for(symbol)[1]
        pos = positions.get(symbol, {"quantity": "0", "avgPrice": "0"})
        held = Decimal(pos["quantity"])
        avg = Decimal(pos["avgPrice"])
        if side == "BUY":
            new_qty = held + qty
            new_avg = ((held * avg) + (qty * price)) / new_qty if new_qty else Decimal(0)
            # 신규 진입(보유 0 → 매수)이면 최초 매수 시점을 기록.
            bought_at = pos.get("firstBoughtAt") if held > 0 else _now()
            positions[symbol] = {
                "quantity": str(new_qty), "avgPrice": _money(new_avg),
                "firstBoughtAt": bought_at, "lastTradeAt": _now(),
            }
            cash[cur] = _money(Decimal(cash.get(cur, "0")) - qty * price)
        else:  # SELL
            new_qty = held - qty
            remaining = max(new_qty, Decimal(0))
            positions[symbol] = {
                "quantity": str(remaining), "avgPrice": _money(avg),
                # 전량 매도면 매수 시점 초기화.
                "firstBoughtAt": pos.get("firstBoughtAt") if remaining > 0 else None,
                "lastTradeAt": _now(),
            }
            cash[cur] = _money(Decimal(cash.get(cur, "0")) + qty * price)

    def _list_orders(self, params) -> dict:
        status = params.get("status", "OPEN")
        open_states = {"PENDING", "PENDING_CANCEL", "PENDING_REPLACE", "PARTIAL_FILLED"}
        want_open = status == "OPEN"
        orders = [
            o for o in self._state["orders"]
            if (o["status"] in open_states) == want_open
            and (not params.get("symbol") or o["symbol"] == params["symbol"])
        ]
        return {"orders": orders, "nextCursor": None, "hasNext": False}

    def _get_order(self, order_id) -> dict:
        for o in self._state["orders"]:
            if o["orderId"] == order_id:
                return o
        raise TossApiError(404, "order-not-found", f"[SIM] 주문을 찾을 수 없습니다: {order_id}")

    def _modify_order(self, order_id, body) -> dict:
        o = self._get_order(order_id)
        if body.get("quantity") is not None:
            o["quantity"] = body["quantity"]
        if body.get("price") is not None:
            o["price"] = body["price"]
        o["status"] = "REPLACED"
        return {"orderId": order_id}

    def _cancel_order(self, order_id) -> dict:
        o = self._get_order(order_id)
        o["status"] = "CANCELED"
        o["canceledAt"] = _now()
        return {"orderId": order_id}
