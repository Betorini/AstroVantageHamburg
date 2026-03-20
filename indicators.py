"""
core/indicators.py
------------------
Pure functional technical indicator calculations using pandas-ta.
No side effects — every function takes a DataFrame and returns a Series or scalar.
"""

from __future__ import annotations

import pandas as pd
import pandas_ta as ta
import numpy as np
from typing import Optional


# ─────────────────────────────────────────────
# Moving Averages
# ─────────────────────────────────────────────

def ema(series: pd.Series, period: int) -> pd.Series:
    """
    Exponential Moving Average.

    Args:
        series: Closing price series.
        period: EMA lookback period (e.g. 21, 50, 200).

    Returns:
        EMA Series aligned to input index.
    """
    result = ta.ema(series, length=period)
    return result if result is not None else pd.Series(dtype=float)


def sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    result = ta.sma(series, length=period)
    return result if result is not None else pd.Series(dtype=float)


def get_ema_stack(df: pd.DataFrame) -> dict[str, pd.Series]:
    """
    Compute the three core EMAs (21, 50, 200) from a OHLCV DataFrame.

    Returns:
        Dict with keys 'ema21', 'ema50', 'ema200' → each a pd.Series.
    """
    close: pd.Series = df["Close"]
    return {
        "ema21": ema(close, 21),
        "ema50": ema(close, 50),
        "ema200": ema(close, 200),
    }


# ─────────────────────────────────────────────
# Momentum
# ─────────────────────────────────────────────

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Relative Strength Index.

    Args:
        series: Closing price series.
        period: RSI lookback period (default 14).

    Returns:
        RSI Series (values 0–100).
    """
    result = ta.rsi(series, length=period)
    return result if result is not None else pd.Series(dtype=float)


def macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict[str, pd.Series]:
    """
    MACD — Moving Average Convergence Divergence.

    Returns:
        Dict with keys 'macd', 'signal', 'histogram'.
    """
    result: Optional[pd.DataFrame] = ta.macd(series, fast=fast, slow=slow, signal=signal)
    if result is None or result.empty:
        empty = pd.Series(dtype=float)
        return {"macd": empty, "signal": empty, "histogram": empty}
    cols = result.columns.tolist()
    return {
        "macd": result[cols[0]],
        "signal": result[cols[2]],
        "histogram": result[cols[1]],
    }


def latest_rsi(df: pd.DataFrame, period: int = 14) -> float:
    """
    Return the most recent RSI value as a scalar float.

    Returns:
        RSI float in range [0, 100], or 0.0 if unavailable.
    """
    rsi_series = rsi(df["Close"], period=period)
    if rsi_series.empty or rsi_series.isna().all():
        return 0.0
    return round(float(rsi_series.dropna().iloc[-1]), 2)


def latest_macd_signal(df: pd.DataFrame) -> str:
    """
    Return a human-readable MACD signal based on histogram direction.

    Returns:
        One of: 'bullish', 'bearish', 'neutral'
    """
    m = macd(df["Close"])
    hist = m["histogram"].dropna()
    if len(hist) < 2:
        return "neutral"
    if hist.iloc[-1] > 0 and hist.iloc[-1] > hist.iloc[-2]:
        return "bullish"
    if hist.iloc[-1] < 0 and hist.iloc[-1] < hist.iloc[-2]:
        return "bearish"
    return "neutral"


# ─────────────────────────────────────────────
# Pivot Points
# ─────────────────────────────────────────────

def pivot_points(df: pd.DataFrame) -> dict[str, float]:
    """
    Calculate classic floor pivot points from the most recent completed bar.

    Formula:
        PP = (H + L + C) / 3
        R1 = 2*PP − L  |  S1 = 2*PP − H
        R2 = PP + (H−L) |  S2 = PP − (H−L)
        R3 = H + 2*(PP−L) | S3 = L − 2*(H−PP)

    Returns:
        Dict with keys 'pp', 'r1', 'r2', 'r3', 's1', 's2', 's3'.
    """
    if len(df) < 2:
        return {}
    prev = df.iloc[-2]
    h, l, c = float(prev["High"]), float(prev["Low"]), float(prev["Close"])
    pp = (h + l + c) / 3
    return {
        "pp": round(pp, 2),
        "r1": round(2 * pp - l, 2),
        "r2": round(pp + (h - l), 2),
        "r3": round(h + 2 * (pp - l), 2),
        "s1": round(2 * pp - h, 2),
        "s2": round(pp - (h - l), 2),
        "s3": round(l - 2 * (h - pp), 2),
    }


# ─────────────────────────────────────────────
# Trend Classification
# ─────────────────────────────────────────────

def trend_bias(df: pd.DataFrame) -> str:
    """
    Classify current trend relative to EMA 200.

    Returns:
        'uptrend', 'downtrend', or 'sideways'
    """
    if df.empty or len(df) < 200:
        return "sideways"
    close = df["Close"]
    e200 = ema(close, 200).dropna()
    if e200.empty:
        return "sideways"
    latest_close = float(close.iloc[-1])
    latest_e200 = float(e200.iloc[-1])
    pct_diff = (latest_close - latest_e200) / latest_e200 * 100
    if pct_diff > 1.0:
        return "uptrend"
    if pct_diff < -1.0:
        return "downtrend"
    return "sideways"


def ema_alignment(df: pd.DataFrame) -> str:
    """
    Check if EMAs are in bullish stack order: price > EMA21 > EMA50 > EMA200.

    Returns:
        'bullish stack', 'partial', or 'bearish stack'
    """
    if df.empty or len(df) < 200:
        return "partial"
    close = df["Close"]
    e21 = ema(close, 21).dropna()
    e50 = ema(close, 50).dropna()
    e200 = ema(close, 200).dropna()
    if e21.empty or e50.empty or e200.empty:
        return "partial"
    p = float(close.iloc[-1])
    v21 = float(e21.iloc[-1])
    v50 = float(e50.iloc[-1])
    v200 = float(e200.iloc[-1])
    if p > v21 > v50 > v200:
        return "bullish stack"
    if p < v21 < v50 < v200:
        return "bearish stack"
    return "partial"
