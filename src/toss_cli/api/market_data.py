"""시세(Market Data) API. 인증만 필요하고 계좌 헤더는 불필요."""

from __future__ import annotations

from typing import Any

from ..client import TossClient


def get_prices(client: TossClient, symbols: list[str]) -> Any:
    """현재가 조회. 여러 종목을 콤마로 묶어 한 번에 조회."""
    return client.get("/api/v1/prices", params={"symbols": ",".join(symbols)})


def get_orderbook(client: TossClient, symbol: str) -> Any:
    """호가 조회."""
    return client.get("/api/v1/orderbook", params={"symbol": symbol})


def get_trades(client: TossClient, symbol: str, count: int | None = None) -> Any:
    """최근 체결 내역 조회."""
    return client.get("/api/v1/trades", params={"symbol": symbol, "count": count})


def get_price_limits(client: TossClient, symbol: str) -> Any:
    """상/하한가 조회."""
    return client.get("/api/v1/price-limits", params={"symbol": symbol})


def get_candles(
    client: TossClient,
    symbol: str,
    interval: str,
    count: int | None = None,
    before: str | None = None,
    adjusted: bool | None = None,
) -> Any:
    """캔들 차트 조회. interval: '1m' | '1d'."""
    return client.get(
        "/api/v1/candles",
        params={
            "symbol": symbol,
            "interval": interval,
            "count": count,
            "before": before,
            "adjusted": adjusted,
        },
    )
