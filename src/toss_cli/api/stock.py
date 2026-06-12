"""종목 정보(Stock Info) API."""

from __future__ import annotations

from typing import Any

from ..client import TossClient


def get_stocks(client: TossClient, symbols: list[str]) -> Any:
    """종목 기본 정보 조회 (여러 종목 콤마 결합)."""
    return client.get("/api/v1/stocks", params={"symbols": ",".join(symbols)})


def get_stock_warnings(client: TossClient, symbol: str) -> Any:
    """매수 유의사항 조회."""
    return client.get(f"/api/v1/stocks/{symbol}/warnings")
