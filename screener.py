"""
core/screener.py
----------------
Pivot breakout detection and Buy/Sell signal generation.
Returns typed dataclasses — no UI or side-effect code here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

from core.indicators import (
    ema,
    ema_alignment,
    get_ema_stack,
    latest_macd_signal,
    latest_rsi,
    pivot_points,
    trend_bias,
)
from utils.fetcher import get_volume_ratio


# ─────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────

SignalStrength = Literal["strong_buy", "buy", "neutral", "sell", "strong_sell"]


@dataclass
class EntrySignal:
    ticker: str
    price: float
    signal: SignalStrength
    entry_low: float
    entry_high: float
    stop_loss: float
    stop_loss_pct: float          # e.g. 0.075 means 7.5%
    pivot_break: bool
    volume_ratio: float           # current / 50-day avg
    rsi: float
    macd_signal: str
    ema21: float
    ema50: float
    ema200: float
    ema_align: str
    trend: str
    risk_reward: float            # approximate R:R to next resistance
    notes: list[str] = field(default_factory=list)


@dataclass
class RiskParameters:
    entry_price: float
    stop_loss: float
    stop_pct: float               # fraction, e.g. 0.075
    position_size_shares: int     # shares to buy given portfolio + risk rules
    position_size_usd: float
    max_loss_usd: float
    risk_reward: float


# ─────────────────────────────────────────────
# Core Signal Logic
# ─────────────────────────────────────────────

def detect_pivot_breakout(df: pd.DataFrame, volume_threshold: float = 1.5) -> bool:
    """
    Detect if today's bar represents a pivot point breakout with volume confirmation.

    Criteria:
        1. Today's close > yesterday's high (price breakout)
        2. Current volume ratio ≥ volume_threshold (default 1.5x)

    Args:
        df:                 OHLCV DataFrame.
        volume_threshold:   Minimum volume ratio vs 50-day avg.

    Returns:
        True if breakout confirmed, False otherwise.
    """
    if len(df) < 3:
        return False
    today_close = float(df["Close"].iloc[-1])
    prev_high = float(df["High"].iloc[-2])
    vol_ratio = get_volume_ratio(df, lookback=50)
    return today_close > prev_high and vol_ratio >= volume_threshold


def calculate_entry_zone(df: pd.DataFrame) -> tuple[float, float]:
    """
    Calculate the recommended entry zone as (low, high).

    Method:
        - Low  = EMA 21 (dynamic support)
        - High = Latest close (don't chase above close)

    Returns:
        Tuple of (entry_low, entry_high) rounded to 2 decimal places.
    """
    if df.empty:
        return (0.0, 0.0)
    close = df["Close"]
    e21 = ema(close, 21).dropna()
    if e21.empty:
        return (round(float(close.iloc[-1]) * 0.97, 2), round(float(close.iloc[-1]), 2))
    entry_low = round(float(e21.iloc[-1]), 2)
    entry_high = round(float(close.iloc[-1]), 2)
    return (entry_low, entry_high)


def calculate_stop_loss(entry_price: float, max_pct: float = 0.08) -> tuple[float, float]:
    """
    Calculate stop-loss price and actual percentage below entry.

    CAN SLIM Rule: Never exceed 8% below purchase price.

    Args:
        entry_price: Midpoint of the entry zone.
        max_pct:     Maximum allowed stop distance (default 8%).

    Returns:
        Tuple of (stop_price, actual_pct) — actual_pct as fraction (e.g. 0.075).
    """
    stop_price = round(entry_price * (1 - max_pct), 2)
    return (stop_price, max_pct)


def calculate_risk_parameters(
    entry_price: float,
    stop_loss: float,
    portfolio_value: float = 100_000.0,
    risk_fraction: float = 0.01,
    next_resistance: float | None = None,
) -> RiskParameters:
    """
    Calculate position sizing and risk metrics.

    Formula:
        risk_per_share = entry_price - stop_loss
        position_size  = (portfolio_value * risk_fraction) / risk_per_share

    Args:
        entry_price:      Planned entry price.
        stop_loss:        Stop-loss price level.
        portfolio_value:  Total portfolio size in USD (default $100k).
        risk_fraction:    Fraction of portfolio to risk per trade (default 1%).
        next_resistance:  Target price for R:R calculation.

    Returns:
        RiskParameters dataclass.
    """
    risk_per_share = entry_price - stop_loss
    if risk_per_share <= 0:
        risk_per_share = entry_price * 0.08

    dollar_risk = portfolio_value * risk_fraction
    shares = max(1, int(dollar_risk / risk_per_share))
    position_usd = round(shares * entry_price, 2)
    max_loss = round(shares * risk_per_share, 2)
    stop_pct = round(risk_per_share / entry_price, 4)

    if next_resistance and next_resistance > entry_price:
        reward = next_resistance - entry_price
        rr = round(reward / risk_per_share, 2)
    else:
        # Default: assume 2:1 R:R target
        rr = 2.0

    return RiskParameters(
        entry_price=round(entry_price, 2),
        stop_loss=round(stop_loss, 2),
        stop_pct=stop_pct,
        position_size_shares=shares,
        position_size_usd=position_usd,
        max_loss_usd=max_loss,
        risk_reward=rr,
    )


def _classify_signal(
    rsi_val: float,
    macd_sig: str,
    ema_align: str,
    pivot_break: bool,
    vol_ratio: float,
    trend: str,
) -> SignalStrength:
    """
    Classify overall entry signal strength from combined indicators.

    Scoring rubric:
        +2 strong_buy conditions: bullish EMA stack + pivot break + heavy volume
        +1 buy conditions: above EMA 200, bullish MACD, RSI 45–65
        Negative: bearish stack, oversold RSI, downtrend
    """
    score = 0

    if ema_align == "bullish stack":
        score += 2
    elif ema_align == "partial":
        score += 1

    if pivot_break:
        score += 2

    if vol_ratio >= 1.5:
        score += 1

    if macd_sig == "bullish":
        score += 1
    elif macd_sig == "bearish":
        score -= 1

    if 45 <= rsi_val <= 65:
        score += 1
    elif rsi_val > 75:
        score -= 1
    elif rsi_val < 30:
        score -= 2

    if trend == "uptrend":
        score += 1
    elif trend == "downtrend":
        score -= 2

    if score >= 6:
        return "strong_buy"
    if score >= 3:
        return "buy"
    if score <= -2:
        return "strong_sell"
    if score < 0:
        return "sell"
    return "neutral"


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def analyze_ticker(ticker: str, df: pd.DataFrame) -> EntrySignal | None:
    """
    Full analysis pipeline for a single ticker.

    Args:
        ticker: Stock symbol.
        df:     OHLCV DataFrame (minimum 200 bars recommended).

    Returns:
        EntrySignal dataclass, or None if data is insufficient.
    """
    if df.empty or len(df) < 50:
        return None

    close = df["Close"]
    price = round(float(close.iloc[-1]), 2)

    emas = get_ema_stack(df)
    e21 = float(emas["ema21"].dropna().iloc[-1]) if not emas["ema21"].dropna().empty else price
    e50 = float(emas["ema50"].dropna().iloc[-1]) if not emas["ema50"].dropna().empty else price
    e200 = float(emas["ema200"].dropna().iloc[-1]) if not emas["ema200"].dropna().empty else price

    rsi_val = latest_rsi(df)
    macd_sig = latest_macd_signal(df)
    align = ema_alignment(df)
    trend = trend_bias(df)
    vol_ratio = get_volume_ratio(df)
    pivot_break = detect_pivot_breakout(df)

    entry_low, entry_high = calculate_entry_zone(df)
    mid_entry = (entry_low + entry_high) / 2
    stop_price, stop_pct = calculate_stop_loss(mid_entry)

    pivots = pivot_points(df)
    r1 = pivots.get("r1", price * 1.03)
    rr = round((r1 - mid_entry) / max(mid_entry - stop_price, 0.01), 2) if mid_entry > stop_price else 2.0

    signal = _classify_signal(rsi_val, macd_sig, align, pivot_break, vol_ratio, trend)

    notes: list[str] = []
    if pivot_break:
        notes.append("✅ Pivot breakout with volume confirmation")
    if vol_ratio >= 1.5:
        notes.append(f"📊 Volume {vol_ratio:.1f}x above 50-day average")
    if align == "bullish stack":
        notes.append("📈 EMA 21 > 50 > 200 — clean bullish alignment")
    if rsi_val > 70:
        notes.append("⚠️ RSI overbought — wait for pullback to EMA 21")
    if trend == "downtrend":
        notes.append("🚫 Price below EMA 200 — no long entries per CAN SLIM rules")

    return EntrySignal(
        ticker=ticker,
        price=price,
        signal=signal,
        entry_low=entry_low,
        entry_high=entry_high,
        stop_loss=stop_price,
        stop_loss_pct=stop_pct,
        pivot_break=pivot_break,
        volume_ratio=vol_ratio,
        rsi=rsi_val,
        macd_signal=macd_sig,
        ema21=round(e21, 2),
        ema50=round(e50, 2),
        ema200=round(e200, 2),
        ema_align=align,
        trend=trend,
        risk_reward=rr,
        notes=notes,
    )


def screen_all(data: dict[str, pd.DataFrame]) -> list[EntrySignal]:
    """
    Run full analysis on all tickers in the data dict.

    Args:
        data: Dict of ticker → OHLCV DataFrame.

    Returns:
        List of EntrySignal dataclasses, sorted by signal strength (best first).
    """
    rank: dict[str, int] = {
        "strong_buy": 0, "buy": 1, "neutral": 2, "sell": 3, "strong_sell": 4
    }
    results = []
    for ticker, df in data.items():
        sig = analyze_ticker(ticker, df)
        if sig:
            results.append(sig)
    results.sort(key=lambda s: rank.get(s.signal, 99))
    return results
