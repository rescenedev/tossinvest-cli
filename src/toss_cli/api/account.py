"""계좌/자산(Account & Asset) API.

holdings 는 계좌 헤더(X-Tossinvest-Account)가 필요합니다.
"""

from __future__ import annotations

from typing import Any

from ..client import ApiClient


def get_accounts(client: ApiClient) -> Any:
    """계좌 목록 조회. (계좌 헤더 불필요)"""
    return client.get("/api/v1/accounts")


def get_holdings(client: ApiClient, account_seq: int, symbol: str | None = None) -> Any:
    """보유 주식 조회. symbol 지정 시 해당 종목만."""
    return client.get(
        "/api/v1/holdings",
        params={"symbol": symbol},
        account_seq=account_seq,
    )
