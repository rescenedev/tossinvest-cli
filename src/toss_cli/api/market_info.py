"""시장 정보(Market Info) API: 환율, 거래 캘린더."""

from __future__ import annotations

from typing import Any

from ..client import TossClient


def get_exchange_rate(
    client: TossClient,
    base_currency: str,
    quote_currency: str,
    date_time: str | None = None,
) -> Any:
    """환율 조회. 예: base=USD, quote=KRW."""
    return client.get(
        "/api/v1/exchange-rate",
        params={
            "baseCurrency": base_currency,
            "quoteCurrency": quote_currency,
            "dateTime": date_time,
        },
    )


def get_kr_calendar(client: TossClient, date: str | None = None) -> Any:
    """한국 시장 거래 캘린더 (date 예: 2026-03-25)."""
    return client.get("/api/v1/market-calendar/KR", params={"date": date})


def get_us_calendar(client: TossClient, date: str | None = None) -> Any:
    """미국 시장 거래 캘린더."""
    return client.get("/api/v1/market-calendar/US", params={"date": date})
