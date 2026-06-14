"""OAuth2 Client Credentials 토큰 발급 및 캐싱.

토큰은 만료 시간과 함께 ~/.toss-cli/token.json 에 저장되어
유효한 동안 재사용됩니다. 만료 60초 전부터는 새로 발급합니다.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

import httpx

from .config import CONFIG_DIR, TOKEN_CACHE_FILE, Config, atomic_write
from .errors import TossApiError

TOKEN_PATH = "/oauth2/token"
# 만료 직전 토큰을 피하기 위한 안전 여유(초)
EXPIRY_SKEW_SECONDS = 60


@dataclass(frozen=True)
class Token:
    access_token: str
    token_type: str
    expires_at: float  # epoch seconds

    def is_valid(self, now: float) -> bool:
        return now < (self.expires_at - EXPIRY_SKEW_SECONDS)

    @property
    def header_value(self) -> str:
        return f"{self.token_type} {self.access_token}"


def _cache_key(config: Config) -> str:
    # client_id 별로 캐시를 구분 (base_url 포함).
    return f"{config.base_url}::{config.client_id}"


def _read_cache(config: Config) -> Token | None:
    if not TOKEN_CACHE_FILE.exists():
        return None
    try:
        raw = json.loads(TOKEN_CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    entry = raw.get(_cache_key(config))
    if not isinstance(entry, dict):
        return None
    try:
        return Token(
            access_token=entry["access_token"],
            token_type=entry["token_type"],
            expires_at=float(entry["expires_at"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _write_cache(config: Config, token: Token) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing: dict[str, object] = {}
    if TOKEN_CACHE_FILE.exists():
        try:
            existing = json.loads(TOKEN_CACHE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}
    existing[_cache_key(config)] = {
        "access_token": token.access_token,
        "token_type": token.token_type,
        "expires_at": token.expires_at,
    }
    # 원자적 쓰기 + 교체 전 0o600 — 부분 쓰기·동시 쓰기·권한 노출 방지.
    atomic_write(TOKEN_CACHE_FILE, json.dumps(existing), mode=0o600)


def issue_token(config: Config, http: httpx.Client) -> Token:
    """토큰 엔드포인트에 client_credentials grant 로 토큰을 요청."""
    response = http.post(
        config.base_url + TOKEN_PATH,
        data={
            "grant_type": "client_credentials",
            "client_id": config.client_id,
            "client_secret": config.client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if response.status_code >= 400:
        body: object
        try:
            body = response.json()
        except ValueError:
            body = response.text
        raise TossApiError.from_response(response.status_code, body)

    payload = response.json()
    expires_in = int(payload.get("expires_in", 0))
    return Token(
        access_token=payload["access_token"],
        token_type=payload.get("token_type", "Bearer"),
        expires_at=time.time() + expires_in,
    )


def get_token(config: Config, http: httpx.Client, *, force: bool = False) -> Token:
    """유효한 캐시 토큰이 있으면 재사용, 없으면 새로 발급 후 캐싱."""
    now = time.time()
    if not force:
        cached = _read_cache(config)
        if cached and cached.is_valid(now):
            return cached
    token = issue_token(config, http)
    _write_cache(config, token)
    return token


def clear_cache() -> bool:
    """캐시된 토큰을 삭제. 삭제했으면 True."""
    if TOKEN_CACHE_FILE.exists():
        TOKEN_CACHE_FILE.unlink()
        return True
    return False
