"""차트 기술지표 순수 계산 — SMA · 볼린저밴드 · Wilder RSI · 기간 프리셋.

모두 입력 리스트에 대한 의존성 없는 순수 함수다 (typer/렌더링과 분리).
정렬 규약: SMA·볼린저는 입력의 `[period-1:]`, RSI 는 `[period:]` 와 일치한다.
"""

from __future__ import annotations

# 기간 프리셋 → 일봉 수 (거래일 기준 근사)
PERIOD_COUNTS: dict[str, int] = {"1w": 5, "1m": 22, "3m": 66, "6m": 130, "1y": 260}


def period_to_count(period: str) -> int:
    """기간 프리셋 문자열 → 일봉 수. 미지원 값이면 ValueError."""
    try:
        return PERIOD_COUNTS[period.lower()]
    except KeyError:
        raise ValueError(
            f"period 는 {', '.join(PERIOD_COUNTS)} 중 하나여야 합니다: {period}"
        ) from None


def sma(values: list[float], period: int) -> list[float]:
    """단순 이동평균. 결과는 values[period-1:] 와 정렬."""
    return [
        sum(values[i - period + 1 : i + 1]) / period
        for i in range(period - 1, len(values))
    ]


def bollinger(closes: list[float], period: int, k: float) -> tuple[list[float], list[float]]:
    """볼린저밴드 (상단, 하단). 결과는 closes[period-1:] 와 정렬."""
    middles = sma(closes, period)
    upper, lower = [], []
    for i, mid in enumerate(middles):
        window = closes[i : i + period]
        var = sum((v - mid) ** 2 for v in window) / period
        std = var**0.5
        upper.append(mid + k * std)
        lower.append(mid - k * std)
    return upper, lower


def rsi_series(closes: list[float], period: int) -> list[float]:
    """Wilder RSI. 결과는 closes[period:] 와 정렬 (데이터 부족 시 빈 리스트)."""
    if len(closes) <= period:
        return []
    gains = [max(closes[i] - closes[i - 1], 0.0) for i in range(1, len(closes))]
    losses = [max(closes[i - 1] - closes[i], 0.0) for i in range(1, len(closes))]

    def to_rsi(avg_gain: float, avg_loss: float) -> float:
        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0
        return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)

    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    values = [to_rsi(avg_g, avg_l)]
    for i in range(period, len(gains)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
        values.append(to_rsi(avg_g, avg_l))
    return values
