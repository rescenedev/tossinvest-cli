"""보유 종목 렌더링 헬퍼 테스트: 소수비율 → %, 통화별 금액 dict 표시."""

from toss_cli.cli.account import _currency_amounts, _percent


def test_percent_converts_fraction_to_percent():
    # 스펙: rate 는 소수비율 (0.1077 = 10.77%)
    assert "+10.77%" in _percent("0.1077")
    assert "-19.62%" in _percent("-0.1962")


def test_percent_handles_missing():
    assert _percent(None) == "[dim]-[/dim]"
    assert _percent("") == "[dim]-[/dim]"


def test_currency_amounts_renders_multi_currency_dict():
    out = _currency_amounts({"krw": "11653850", "usd": "69065.021567"})
    assert "11,653,850 KRW" in out
    assert "69,065.02 USD" in out


def test_currency_amounts_signed_colors_each_part():
    out = _currency_amounts({"krw": "-2092670", "usd": "137188.638645"}, signed=True)
    assert "[red]-2,092,670[/red] KRW" in out
    assert "[green]+137,188.64[/green] USD" in out


def test_currency_amounts_scalar_passthrough():
    assert _currency_amounts("12345") == "12,345"
    assert _currency_amounts(None) == "[dim]-[/dim]"
