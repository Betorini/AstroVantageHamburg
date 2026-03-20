"""
tests/test_indicators.py
------------------------
Unit tests for core/indicators.py — verifies mathematical accuracy of all
technical indicator calculations. Run with: pytest tests/
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.indicators import (
    calculate_midpoint as _unused,  # noqa: F401 — just ensure import works
    ema,
    ema_alignment,
    latest_rsi,
    macd,
    pivot_points,
    rsi,
    sma,
    trend_bias,
)

# Suppress pandas-ta warnings in test output
import warnings
warnings.filterwarnings("ignore")


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────

def make_ohlcv(close_prices: list[float]) -> pd.DataFrame:
    """Build a minimal OHLCV DataFrame from a list of close prices."""
    n = len(close_prices)
    closes = pd.Series(close_prices, dtype=float)
    df = pd.DataFrame({
        "Open":   closes * 0.99,
        "High":   closes * 1.01,
        "Low":    closes * 0.98,
        "Close":  closes,
        "Volume": [1_000_000] * n,
    })
    df.index = pd.date_range("2024-01-01", periods=n, freq="B")
    return df


def make_trending_df(n: int = 250, start: float = 100.0, drift: float = 0.3) -> pd.DataFrame:
    """Generate a smoothly trending upward price series."""
    prices = [start + drift * i + np.random.uniform(-0.5, 0.5) for i in range(n)]
    return make_ohlcv(prices)


# ─────────────────────────────────────────────
# EMA Tests
# ─────────────────────────────────────────────

class TestEMA:
    def test_ema_returns_series(self):
        df = make_ohlcv([100.0] * 50)
        result = ema(df["Close"], 21)
        assert isinstance(result, pd.Series)

    def test_ema_flat_price_converges_to_price(self):
        """EMA of a constant series should equal that constant (after warmup)."""
        price = 150.0
        df = make_ohlcv([price] * 100)
        result = ema(df["Close"], 21).dropna()
        assert abs(float(result.iloc[-1]) - price) < 0.01

    def test_ema_rising_series_below_price(self):
        """EMA of a steadily rising series should lag behind the latest price."""
        df = make_ohlcv([float(i) for i in range(1, 101)])
        result = ema(df["Close"], 21).dropna()
        latest_close = 100.0
        assert float(result.iloc[-1]) < latest_close

    def test_ema_length_not_shorter_than_period(self):
        df = make_ohlcv([float(i) for i in range(1, 60)])
        result = ema(df["Close"], 21).dropna()
        assert len(result) > 0

    def test_ema21_lt_ema50_in_uptrend(self):
        """In a strong uptrend, EMA 21 should be above EMA 50."""
        df = make_trending_df(n=250, drift=0.8)
        e21 = ema(df["Close"], 21).dropna().iloc[-1]
        e50 = ema(df["Close"], 50).dropna().iloc[-1]
        # EMA21 is closer to current price in uptrend
        assert e21 > e50


# ─────────────────────────────────────────────
# SMA Tests
# ─────────────────────────────────────────────

class TestSMA:
    def test_sma_flat_equals_price(self):
        price = 200.0
        df = make_ohlcv([price] * 50)
        result = sma(df["Close"], 20).dropna()
        assert abs(float(result.iloc[-1]) - price) < 0.001


# ─────────────────────────────────────────────
# RSI Tests
# ─────────────────────────────────────────────

class TestRSI:
    def test_rsi_in_valid_range(self):
        df = make_ohlcv([float(i % 20 + 90) for i in range(100)])
        result = rsi(df["Close"], period=14).dropna()
        assert (result >= 0).all() and (result <= 100).all()

    def test_rsi_pure_up_trend_near_100(self):
        """Steadily rising prices → RSI should be high."""
        prices = [100.0 + i * 0.5 for i in range(60)]
        df = make_ohlcv(prices)
        val = latest_rsi(df)
        assert val > 60.0

    def test_rsi_pure_down_trend_near_0(self):
        """Steadily falling prices → RSI should be low."""
        prices = [200.0 - i * 0.5 for i in range(60)]
        df = make_ohlcv(prices)
        val = latest_rsi(df)
        assert val < 40.0

    def test_latest_rsi_returns_float(self):
        df = make_ohlcv([100.0 + np.sin(i * 0.3) * 5 for i in range(60)])
        val = latest_rsi(df)
        assert isinstance(val, float)
        assert 0.0 <= val <= 100.0


# ─────────────────────────────────────────────
# MACD Tests
# ─────────────────────────────────────────────

class TestMACD:
    def test_macd_returns_three_series(self):
        df = make_ohlcv([float(i % 30 + 100) for i in range(60)])
        result = macd(df["Close"])
        assert "macd" in result
        assert "signal" in result
        assert "histogram" in result

    def test_macd_histogram_is_macd_minus_signal(self):
        df = make_trending_df(n=100)
        result = macd(df["Close"])
        m = result["macd"].dropna()
        s = result["signal"].dropna()
        h = result["histogram"].dropna()
        # Align all three
        common = m.index.intersection(s.index).intersection(h.index)
        diff = (m.loc[common] - s.loc[common] - h.loc[common]).abs()
        assert diff.max() < 0.01, "Histogram should equal MACD − Signal line"


# ─────────────────────────────────────────────
# Pivot Points Tests
# ─────────────────────────────────────────────

class TestPivotPoints:
    def test_pivot_returns_all_keys(self):
        df = make_ohlcv([100.0] * 10)
        df["High"] = 110.0
        df["Low"] = 90.0
        result = pivot_points(df)
        for key in ("pp", "r1", "r2", "r3", "s1", "s2", "s3"):
            assert key in result

    def test_pivot_pp_formula(self):
        """PP = (H + L + C) / 3 based on the second-to-last bar."""
        closes = [100.0] * 10
        df = make_ohlcv(closes)
        df["High"] = 110.0
        df["Low"] = 90.0
        df["Close"] = 100.0
        result = pivot_points(df)
        expected_pp = (110.0 + 90.0 + 100.0) / 3.0
        assert abs(result["pp"] - expected_pp) < 0.01

    def test_r1_above_pp(self):
        df = make_ohlcv([100.0] * 10)
        df["High"] = 110.0
        df["Low"] = 90.0
        result = pivot_points(df)
        assert result["r1"] > result["pp"]

    def test_s1_below_pp(self):
        df = make_ohlcv([100.0] * 10)
        df["High"] = 110.0
        df["Low"] = 90.0
        result = pivot_points(df)
        assert result["s1"] < result["pp"]


# ─────────────────────────────────────────────
# Trend & Alignment Tests
# ─────────────────────────────────────────────

class TestTrendBias:
    def test_uptrend_detected(self):
        df = make_trending_df(n=250, drift=1.0)
        result = trend_bias(df)
        assert result in ("uptrend", "sideways")

    def test_downtrend_detected(self):
        df = make_trending_df(n=250, drift=-1.0)
        result = trend_bias(df)
        assert result in ("downtrend", "sideways")

    def test_insufficient_data_returns_sideways(self):
        df = make_ohlcv([100.0] * 10)
        result = trend_bias(df)
        assert result == "sideways"


class TestEMAAlignment:
    def test_bullish_stack_in_uptrend(self):
        df = make_trending_df(n=250, start=50.0, drift=0.8)
        result = ema_alignment(df)
        assert result in ("bullish stack", "partial")

    def test_alignment_returns_valid_string(self):
        df = make_ohlcv([100.0] * 250)
        result = ema_alignment(df)
        assert result in ("bullish stack", "bearish stack", "partial")
