"""
utils/fetcher.py
----------------
Cached market data fetching via yfinance.
All functions use @st.cache_data to prevent redundant API calls.
"""

from __future__ import annotations

import streamlit as st
import yfinance as yf
import pandas as pd
from typing import Optional


MAG7: list[str] = ["NVDA", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "AAPL"]


@st.cache_data(ttl=300, show_spinner=False)
def fetch_ohlcv(ticker: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """
    Fetch OHLCV data for a single ticker from yfinance.

    Args:
        ticker:   Stock symbol, e.g. "NVDA"
        period:   Lookback period string accepted by yfinance, e.g. "6mo", "1y"
        interval: Bar interval, e.g. "1d", "1h"

    Returns:
        DataFrame with columns [Open, High, Low, Close, Volume] indexed by datetime.
        Returns empty DataFrame on failure.
    """
    try:
        df: pd.DataFrame = yf.download(
            ticker,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True,
        )
        if df.empty:
            return pd.DataFrame()
        df.index = pd.to_datetime(df.index)
        df.index.name = "Date"
        # Flatten MultiIndex columns if present (yfinance ≥0.2.x)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    except Exception as exc:
        st.warning(f"⚠️ Could not fetch data for {ticker}: {exc}")
        return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def fetch_info(ticker: str) -> dict:
    """
    Fetch metadata / fundamentals for a ticker.

    Returns:
        Dict with keys like marketCap, trailingPE, sector, etc.
        Returns empty dict on failure.
    """
    try:
        info: dict = yf.Ticker(ticker).info
        return info
    except Exception:
        return {}


@st.cache_data(ttl=60, show_spinner=False)
def fetch_latest_price(ticker: str) -> Optional[float]:
    """
    Fetch the most recent closing price for a ticker.

    Returns:
        Latest closing price as float, or None on failure.
    """
    df = fetch_ohlcv(ticker, period="5d", interval="1d")
    if df.empty:
        return None
    return float(df["Close"].iloc[-1])


@st.cache_data(ttl=300, show_spinner=False)
def fetch_all_mag7(period: str = "6mo") -> dict[str, pd.DataFrame]:
    """
    Fetch OHLCV data for all Magnificent Seven tickers.

    Returns:
        Dict mapping ticker symbol → OHLCV DataFrame.
    """
    return {ticker: fetch_ohlcv(ticker, period=period) for ticker in MAG7}


def get_volume_ratio(df: pd.DataFrame, lookback: int = 50) -> float:
    """
    Calculate current volume as a ratio of the N-day average volume.

    Args:
        df:       OHLCV DataFrame with a 'Volume' column.
        lookback: Number of days for the average (default 50).

    Returns:
        Ratio as float. Returns 0.0 if insufficient data.
    """
    if df.empty or len(df) < 2:
        return 0.0
    avg_vol: float = float(df["Volume"].iloc[-lookback:-1].mean())
    if avg_vol == 0:
        return 0.0
    current_vol: float = float(df["Volume"].iloc[-1])
    return round(current_vol / avg_vol, 2)
