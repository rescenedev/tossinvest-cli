"""차트 기술지표 순수 함수 테스트."""

import pytest

from toss_cli.cli.indicators import (
    bollinger,
    disparity,
    disparity_latest,
    period_to_count,
    rsi_series,
    sma,
)


def test_sma_alignment_and_values():
    assert sma([1, 2, 3, 4, 5], 3) == [2.0, 3.0, 4.0]   # 3개 (입력 5 - period 3 + 1)


def test_rsi_bounds():
    assert all(v == 100.0 for v in rsi_series([float(100 + i) for i in range(30)], 14))
    assert all(v == 0.0 for v in rsi_series([float(100 - i) for i in range(30)], 14))
    assert rsi_series([1, 2, 3], 14) == []   # 데이터 부족


def test_bollinger_shape_and_ordering():
    closes = [float(100 + (i % 5)) for i in range(40)]
    upper, lower = bollinger(closes, 20, 2.0)
    assert len(upper) == len(lower) == 40 - 20 + 1
    assert all(up >= lo for up, lo in zip(upper, lower))


def test_disparity_alignment_and_values():
    # sma([1,2,3,4,5],3) == [2,3,4] → 이격도 = 종가/MA*100
    assert disparity([1, 2, 3, 4, 5], 3) == [3 / 2 * 100, 4 / 3 * 100, 5 / 4 * 100]


def test_disparity_100_when_flat():
    # 가격이 일정하면 이동평균과 같아 이격도는 항상 100.
    assert disparity([50.0] * 10, 5) == [100.0] * 6


def test_disparity_latest_and_insufficient():
    assert disparity_latest([1, 2, 3, 4, 5], 3) == pytest.approx(5 / 4 * 100)
    assert disparity_latest([1, 2], 5) is None   # 데이터 부족
    assert disparity_latest([10, 20, 30], 0) is None


def test_period_to_count():
    assert period_to_count("1w") == 5
    assert period_to_count("3m") == 66
    assert period_to_count("1Y") == 260   # 대소문자 무시
    with pytest.raises(ValueError):
        period_to_count("99x")
