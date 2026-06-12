"""토스 Open API HTTP 클라이언트.

- 모든 요청에 Bearer 토큰 자동 첨부
- 계좌 헤더(X-Tossinvest-Account) 주입 헬퍼
- 429(rate limit) 시 Retry-After 만큼 대기 후 재시도
- 에러 응답을 TossApiError 로 변환
"""

from __future__ import annotations

import time
from typing import Any, Mapping, Protocol

import httpx

from . import __version__
from .auth import get_token
from .config import Config
from .errors import TossApiError

ACCOUNT_HEADER = "X-Tossinvest-Account"
USER_AGENT = f"tossinvest-cli/{__version__}"
DEFAULT_TIMEOUT = 15.0
MAX_RETRIES = 2


class ApiClient(Protocol):
    """TossClient / SimClient 가 공유하는 최소 인터페이스."""

    @property
    def config(self) -> Config: ...

    def get(self, path: str, *, params: Mapping[str, Any] | None = ...,
            account_seq: int | None = ...) -> Any: ...

    def post(self, path: str, *, json_body: Any | None = ...,
             account_seq: int | None = ...) -> Any: ...

    def use_account(self, account_seq: int | None) -> None: ...

    def close(self) -> None: ...


class TossClient:
    """동기 API 클라이언트. context manager 로 사용하세요."""

    def __init__(self, config: Config, *, timeout: float = DEFAULT_TIMEOUT):
        self._config = config
        self._http = httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT})

    # -- lifecycle -------------------------------------------------------
    def __enter__(self) -> "TossClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    @property
    def config(self) -> Config:
        return self._config

    def use_account(self, account_seq: int | None) -> None:
        """세션 계좌를 변경 (Config 는 불변이므로 새 사본으로 교체)."""
        self._config = self._config.with_account(account_seq)

    # -- low level -------------------------------------------------------
    def _auth_header(self) -> dict[str, str]:
        token = get_token(self._config, self._http)
        return {"Authorization": token.header_value}

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any | None = None,
        account_seq: int | None = None,
    ) -> Any:
        """인증된 요청을 보내고 파싱된 JSON 본문을 반환.

        2xx 가 아니면 TossApiError 를 발생. 429 는 Retry-After 만큼 대기 후 재시도.
        """
        url = self._config.base_url + path
        clean_params = _drop_none(params) if params else None

        attempt = 0
        while True:
            headers = self._auth_header()
            if account_seq is not None:
                headers[ACCOUNT_HEADER] = str(account_seq)

            response = self._http.request(
                method,
                url,
                params=clean_params,
                json=json_body,
                headers=headers,
            )

            if response.status_code == 429 and attempt < MAX_RETRIES:
                wait = _retry_after_seconds(response.headers)
                time.sleep(wait)
                attempt += 1
                continue

            return _handle_response(response)

    # -- verbs -----------------------------------------------------------
    def get(self, path: str, *, params: Mapping[str, Any] | None = None,
            account_seq: int | None = None) -> Any:
        return self.request("GET", path, params=params, account_seq=account_seq)

    def post(self, path: str, *, json_body: Any | None = None,
             account_seq: int | None = None) -> Any:
        return self.request("POST", path, json_body=json_body, account_seq=account_seq)


def _drop_none(params: Mapping[str, Any]) -> dict[str, Any]:
    """None 값 파라미터는 쿼리에서 제외 (불변: 새 dict 반환)."""
    return {k: v for k, v in params.items() if v is not None}


MAX_RETRY_WAIT_SECONDS = 30.0


def _retry_after_seconds(headers: httpx.Headers, default: float = 1.0) -> float:
    """Retry-After 대기 시간. 서버 값이 비정상적으로 커도 상한으로 캡."""
    raw = headers.get("Retry-After")
    if not raw:
        return default
    try:
        return min(max(0.0, float(raw)), MAX_RETRY_WAIT_SECONDS)
    except ValueError:
        return default


def _handle_response(response: httpx.Response) -> Any:
    if response.status_code == 204 or not response.content:
        return None
    try:
        body = response.json()
    except ValueError:
        body = response.text
    if response.status_code >= 400:
        raise TossApiError.from_response(response.status_code, body)
    return _unwrap_envelope(body)


def _unwrap_envelope(body: Any) -> Any:
    """공통 응답 봉투 {"result": ...} 를 벗겨 실제 payload 만 반환.

    스펙(ApiResponse)상 성공 응답은 result 키 하나만 갖는다. OAuth2 토큰 응답은
    이 클라이언트를 거치지 않으므로(auth.py) 여기서 고려하지 않는다.
    """
    if isinstance(body, dict) and set(body.keys()) == {"result"}:
        return body["result"]
    return body
