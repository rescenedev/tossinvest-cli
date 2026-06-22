"""네이버 금융 펀더멘털(PER·PBR·EPS 등) 조회 — 외부 참고 데이터(읽기 전용).

토스 Open API 에는 밸류에이션 지표가 없어, 공개된 네이버 금융 JSON 을 **참고용**으로
가져온다. 이 모듈은 토스 ApiClient 와 무관한 독립 HTTP 호출이며(거래·인증과 분리),
실패·미발견은 예외 대신 None 으로 우아하게 처리한다.

KR/US 모두 응답이 ``{code, key, value}`` 항목 리스트라 단일 파서로 다룬다.
- KR: ``m.stock.naver.com/api/stock/{code}/integration`` → ``totalInfos``
- US: 검색으로 ticker→reutersCode 해석 후
      ``m.stock.naver.com/front-api/stock/foreign/basic?code={reuters}`` → ``stockItemTotalInfos``
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx

SOURCE = "네이버 금융"

_BASE = "https://m.stock.naver.com"
_FRONT = f"{_BASE}/front-api"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://m.stock.naver.com/",
}
_TIMEOUT = 8.0

# 표시할 지표: (네이버 code, 라벨). 응답에 있는 것만, 이 순서대로 노출한다.
FIELDS: tuple[tuple[str, str], ...] = (
    ("per", "PER"),
    ("cnsPer", "추정 PER"),
    ("pbr", "PBR"),
    ("eps", "EPS"),
    ("cnsEps", "추정 EPS"),
    ("bps", "BPS"),
    ("dividendYieldRatio", "배당수익률"),
    ("dividend", "주당배당금"),
    ("marketValue", "시가총액"),
    ("highPriceOf52Weeks", "52주 최고"),
    ("lowPriceOf52Weeks", "52주 최저"),
    ("foreignRate", "외국인 소진율"),
)

# 대시보드 한 줄 요약에 쓰는 핵심 지표 라벨.
COMPACT_LABELS = ("PER", "PBR", "EPS", "배당수익률")

_KR_RE = re.compile(r"[0-9][0-9A-Z]{5}")  # 6자리 코드 (005930, 0193T0)
_EMPTY = {None, "", "-", "N/A", "0", "0.00"}


@dataclass(frozen=True)
class Fundamentals:
    """한 종목의 밸류에이션 지표 모음. 값은 네이버 표기 그대로(예: ``"28.57배"``)."""

    symbol: str
    name: str
    market: str  # "KR" | "US"
    metrics: tuple[tuple[str, str], ...]  # (라벨, 값)
    source: str = SOURCE

    def __bool__(self) -> bool:
        return bool(self.metrics)

    def as_dict(self) -> dict[str, Any]:
        """--json/--csv 출력용 평탄 dict."""
        return {
            "symbol": self.symbol,
            "name": self.name,
            "market": self.market,
            "source": self.source,
            **{label: value for label, value in self.metrics},
        }

    def compact(self) -> tuple[tuple[str, str], ...]:
        """대시보드용 핵심 지표만 추린 (라벨, 값) 목록."""
        wanted = dict(self.metrics)
        return tuple((label, wanted[label]) for label in COMPACT_LABELS if label in wanted)


# -- 순수 파서 (네트워크 없음) -------------------------------------------------

def is_kr_symbol(symbol: str) -> bool:
    """6자리 KR 종목코드인지 판별 (그 외는 해외 티커로 취급)."""
    return bool(_KR_RE.fullmatch(symbol.upper()))


def _pluck(items: Any) -> tuple[tuple[str, str], ...]:
    """code/key/value 항목 리스트 → 원하는 (라벨, 값) 순서로 추출. 빈 값은 제외."""
    by_code: dict[str, str] = {}
    for it in items or []:
        if isinstance(it, dict) and it.get("code"):
            value = it.get("value")
            if value not in _EMPTY:
                by_code[str(it["code"])] = str(value)
    return tuple((label, by_code[code]) for code, label in FIELDS if code in by_code)


def parse_kr(payload: Any, symbol: str) -> Fundamentals | None:
    if not isinstance(payload, dict):
        return None
    metrics = _pluck(payload.get("totalInfos"))
    if not metrics:
        return None
    name = payload.get("stockName") or symbol
    return Fundamentals(symbol=symbol, name=str(name), market="KR", metrics=metrics)


def parse_us(payload: Any, symbol: str) -> Fundamentals | None:
    if not isinstance(payload, dict):
        return None
    result = payload.get("result") if "result" in payload else payload
    if not isinstance(result, dict):
        return None
    metrics = _pluck(result.get("stockItemTotalInfos"))
    if not metrics:
        return None
    name = result.get("stockName") or result.get("stockNameEng") or symbol
    return Fundamentals(symbol=symbol, name=str(name), market="US", metrics=metrics)


def pick_reuters_code(search_payload: Any, ticker: str) -> str | None:
    """검색 응답에서 ticker 와 일치하는 해외 종목의 reutersCode (없으면 첫 후보)."""
    result = search_payload.get("result") if isinstance(search_payload, dict) else None
    items = result.get("items") if isinstance(result, dict) else None
    target = ticker.upper()
    candidates = [it for it in (items or []) if isinstance(it, dict) and it.get("reutersCode")]
    for it in candidates:
        if str(it.get("code") or "").upper() == target:
            return str(it["reutersCode"])
    return str(candidates[0]["reutersCode"]) if candidates else None


# -- 네트워크 조회 -------------------------------------------------------------

def fetch(symbol: str, *, client: httpx.Client | None = None,
          timeout: float = _TIMEOUT) -> Fundamentals | None:
    """심볼의 펀더멘털을 네이버에서 조회. 네트워크 실패·미발견 시 None."""
    own = client is None
    http = client or httpx.Client(timeout=timeout, headers=_HEADERS)
    try:
        sym = symbol.strip().upper()
        if is_kr_symbol(sym):
            return _fetch_kr(http, sym)
        return _fetch_us(http, sym)
    except (httpx.HTTPError, ValueError):
        return None
    finally:
        if own:
            http.close()


def _get_json(http: httpx.Client, url: str, params: dict[str, Any] | None = None) -> Any:
    resp = http.get(url, params=params)
    resp.raise_for_status()
    return resp.json()


def _fetch_kr(http: httpx.Client, symbol: str) -> Fundamentals | None:
    data = _get_json(http, f"{_BASE}/api/stock/{symbol}/integration")
    return parse_kr(data, symbol)


def _fetch_us(http: httpx.Client, ticker: str) -> Fundamentals | None:
    search = _get_json(http, f"{_FRONT}/search/autoComplete",
                       {"query": ticker, "target": "stock"})
    reuters = pick_reuters_code(search, ticker)
    if not reuters:
        return None
    data = _get_json(http, f"{_FRONT}/stock/foreign/basic",
                     {"code": reuters, "endType": "stock"})
    return parse_us(data, ticker)
