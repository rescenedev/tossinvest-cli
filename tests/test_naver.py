"""네이버 금융 펀더멘털 조회 — 순수 파서 + 네트워크(respx) 테스트."""

import httpx
import respx

from toss_cli.api import naver

# code/key/value 항목 샘플 (KR integration.totalInfos 형태)
_KR_TOTALINFOS = [
    {"code": "marketValue", "key": "시총", "value": "2,066조 6,595억"},
    {"code": "per", "key": "PER", "value": "28.57배"},
    {"code": "eps", "key": "EPS", "value": "12,372원"},
    {"code": "cnsPer", "key": "추정PER", "value": "7.96배"},
    {"code": "pbr", "key": "PBR", "value": "4.92배"},
    {"code": "bps", "key": "BPS", "value": "71,907원"},
    {"code": "dividendYieldRatio", "key": "배당수익률", "value": "0.47%"},
    {"code": "openPrice", "key": "시가", "value": "351,000"},  # 무시 대상
]

_US_TOTALINFOS = [
    {"code": "marketValue", "key": "시총", "value": "4조 3,959억 USD"},
    {"code": "per", "key": "PER", "value": "36.35배"},
    {"code": "eps", "key": "EPS", "value": "8.23"},
    {"code": "pbr", "key": "PBR", "value": "41.22배"},
    {"code": "dividendYieldRatio", "key": "배당수익률", "value": "0.36%"},
]


# -- 순수 파서 ----------------------------------------------------------------

def test_is_kr_symbol():
    assert naver.is_kr_symbol("005930")
    assert naver.is_kr_symbol("0193T0")   # 영숫자 6자리도 KR
    assert not naver.is_kr_symbol("AAPL")
    assert not naver.is_kr_symbol("BRK.B")


def test_pluck_order_and_skips_empty():
    items = [
        {"code": "pbr", "key": "PBR", "value": "4.92배"},
        {"code": "per", "key": "PER", "value": "28.57배"},
        {"code": "eps", "key": "EPS", "value": "-"},        # 빈 값 → 제외
        {"code": "dividend", "key": "주당배당금", "value": "0"},  # 0 → 제외
    ]
    out = naver._pluck(items)
    # FIELDS 순서를 따르므로 PER 가 PBR 보다 먼저, EPS/주당배당금 은 빠진다.
    assert out == (("PER", "28.57배"), ("PBR", "4.92배"))


def test_parse_kr():
    f = naver.parse_kr({"stockName": "삼성전자", "totalInfos": _KR_TOTALINFOS}, "005930")
    assert f and f.market == "KR" and f.name == "삼성전자"
    d = dict(f.metrics)
    assert d["PER"] == "28.57배" and d["PBR"] == "4.92배" and d["EPS"] == "12,372원"
    assert "추정 PER" in d
    assert f.compact() == (("PER", "28.57배"), ("PBR", "4.92배"),
                           ("EPS", "12,372원"), ("배당수익률", "0.47%"))


def test_parse_kr_empty_returns_none():
    assert naver.parse_kr({"totalInfos": []}, "005930") is None
    assert naver.parse_kr("nope", "005930") is None


def test_parse_us_wrapped_in_result():
    payload = {"result": {"stockName": "애플", "stockItemTotalInfos": _US_TOTALINFOS}}
    f = naver.parse_us(payload, "AAPL")
    assert f and f.market == "US" and f.name == "애플"
    assert dict(f.metrics)["PER"] == "36.35배"


def test_pick_reuters_code_prefers_exact_code():
    payload = {"result": {"items": [
        {"code": "AAPLW", "reutersCode": "AAPLW.O"},
        {"code": "AAPL", "reutersCode": "AAPL.O"},
    ]}}
    assert naver.pick_reuters_code(payload, "AAPL") == "AAPL.O"


def test_pick_reuters_code_none_when_absent():
    assert naver.pick_reuters_code({"result": {"items": []}}, "AAPL") is None


def test_as_dict_flattens_metrics():
    f = naver.parse_kr({"stockName": "삼성전자", "totalInfos": _KR_TOTALINFOS}, "005930")
    d = f.as_dict()
    assert d["symbol"] == "005930" and d["source"] == naver.SOURCE
    assert d["PER"] == "28.57배"


# -- 네트워크 (respx) ----------------------------------------------------------

@respx.mock
def test_fetch_kr_calls_integration():
    route = respx.get("https://m.stock.naver.com/api/stock/005930/integration").mock(
        return_value=httpx.Response(200, json={"stockName": "삼성전자", "totalInfos": _KR_TOTALINFOS})
    )
    f = naver.fetch("005930")
    assert route.called
    assert f and f.market == "KR" and dict(f.metrics)["PER"] == "28.57배"


@respx.mock
def test_fetch_us_resolves_then_basic():
    respx.get("https://m.stock.naver.com/front-api/search/autoComplete").mock(
        return_value=httpx.Response(200, json={"result": {"items": [
            {"code": "AAPL", "reutersCode": "AAPL.O", "name": "애플"}
        ]}})
    )
    basic = respx.get("https://m.stock.naver.com/front-api/stock/foreign/basic").mock(
        return_value=httpx.Response(200, json={"result": {
            "stockName": "애플", "stockItemTotalInfos": _US_TOTALINFOS}})
    )
    f = naver.fetch("AAPL")
    assert basic.called
    # foreign/basic 호출 시 해석된 reutersCode 가 전달됐는지
    assert basic.calls[0].request.url.params["code"] == "AAPL.O"
    assert f and f.market == "US" and dict(f.metrics)["PER"] == "36.35배"


@respx.mock
def test_fetch_returns_none_on_http_error():
    respx.get("https://m.stock.naver.com/api/stock/005930/integration").mock(
        return_value=httpx.Response(500)
    )
    assert naver.fetch("005930") is None


@respx.mock
def test_fetch_us_none_when_unresolved():
    respx.get("https://m.stock.naver.com/front-api/search/autoComplete").mock(
        return_value=httpx.Response(200, json={"result": {"items": []}})
    )
    assert naver.fetch("NOPE") is None
