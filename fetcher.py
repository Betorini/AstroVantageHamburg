"""
utils/fetcher.py
----------------
Cached multi-asset market data fetching via yfinance.
All network calls use @st.cache_data to prevent redundant API hits.

Asset classes supported
-----------------------
  Equities   — plain symbols, e.g. "NVDA"
  Crypto     — MUST use the "-USD" suffix (e.g. "BTC-USD").
               Without it yfinance may resolve "SOL" as Reata Pharmaceuticals
               instead of Solana, silently returning wrong price data.
  Futures    — "=F" suffix (e.g. "GC=F" for Gold, "SI=F" for Silver).
  Indices    — "^" prefix  (e.g. "^GSPC" for S&P 500, "^IXIC" for Nasdaq).

Ticker formatting is the responsibility of the caller (or this module's
constants). fetch_ohlcv() never rewrites a symbol — it trusts the value
passed in and documents exactly what format each class requires.
"""

from __future__ import annotations

import logging
from typing import Literal, Optional

import pandas as pd
import streamlit as st
import yfinance as yf

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Asset Class Type
# ─────────────────────────────────────────────────────────────────────────────

AssetClass = Literal["MAG7", "TECH_SMALL", "CRYPTO", "COMMODITIES", "INDICES"]

# ─────────────────────────────────────────────────────────────────────────────
# Master Asset Dictionary
# ─────────────────────────────────────────────────────────────────────────────
#
# Formatting rules enforced here so callers never have to think about them:
#
#   Crypto      → append "-USD"   BTC-USD, ETH-USD …
#                 yfinance looks up crypto as "<BASE>-<QUOTE>" pairs.
#                 "SOL" without the suffix resolves to a biotech stock (Reata
#                 Pharmaceuticals, ticker SOL), returning completely wrong data.
#
#   Futures     → append "=F"    GC=F (Gold), SI=F (Silver) …
#                 This selects the front-month continuous contract.
#
#   Indices     → prepend "^"    ^GSPC, ^IXIC …
#                 yfinance uses the CBOE/Yahoo index symbol convention.
#
#   Equities    → plain symbol   NVDA, MSFT, PLTR …
#                 No suffix or prefix required.

ASSET_UNIVERSE: dict[AssetClass, list[str]] = {
    # ── Magnificent Seven large-cap growth stocks ──────────────────────────
    "MAG7": [
        "NVDA",   # NVIDIA — AI / GPU
        "MSFT",   # Microsoft — cloud + AI
        "GOOGL",  # Alphabet — search + cloud
        "AMZN",   # Amazon — e-comm + AWS
        "META",   # Meta — social + AR/VR
        "TSLA",   # Tesla — EV + energy
        "AAPL",   # Apple — consumer hardware
    ],

    # ── Small / mid-cap high-growth tech & AI plays ───────────────────────
    "TECH_SMALL": [
        "PLTR",   # Palantir — data analytics / defence AI
        "SOFI",   # SoFi Technologies — fintech
        "AI",     # C3.ai — enterprise AI software
        "PATH",   # UiPath — RPA / automation
        "MSTR",   # MicroStrategy — BTC treasury / BI
        "MARA",   # Marathon Digital — Bitcoin mining
    ],

    # ── Cryptocurrencies — "-USD" suffix is MANDATORY ─────────────────────
    #    Without it, yfinance may silently resolve the bare ticker to an
    #    unrelated equity (e.g. SOL → Reata Pharmaceuticals).
    "CRYPTO": [
        "BTC-USD",   # Bitcoin
        "ETH-USD",   # Ethereum
        "SOL-USD",   # Solana   ← "SOL" (no suffix) = wrong stock ticker
        "ADA-USD",   # Cardano
        "DOT-USD",   # Polkadot
        "LINK-USD",  # Chainlink
    ],

    # ── Commodities — "=F" selects the front-month futures contract ────────
    "COMMODITIES": [
        "GC=F",   # Gold (COMEX front-month)
        "SI=F",   # Silver (COMEX front-month)
    ],

    # ── Benchmark indices — "^" prefix is required by Yahoo Finance ────────
    "INDICES": [
        "^GSPC",  # S&P 500
        "^IXIC",  # Nasdaq Composite
    ],
}

# Convenience flat list kept for backwards-compatibility with app.py imports
MAG7: list[str] = ASSET_UNIVERSE["MAG7"]

# Flat list of every tracked ticker across all classes
ALL_TICKERS: list[str] = [t for tickers in ASSET_UNIVERSE.values() for t in tickers]


# ─────────────────────────────────────────────────────────────────────────────
# Ticker Classification Helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_asset_class(ticker: str) -> AssetClass | None:
    """
    Return the AssetClass a ticker belongs to, or None if not in the universe.

    Example:
        get_asset_class("BTC-USD")  →  "CRYPTO"
        get_asset_class("NVDA")     →  "MAG7"
        get_asset_class("XYZ")      →  None
    """
    for asset_class, tickers in ASSET_UNIVERSE.items():
        if ticker in tickers:
            return asset_class  # type: ignore[return-value]
    return None


def is_crypto(ticker: str) -> bool:
    """True when ticker ends with a '-USD' (or any '-XXX') quote suffix."""
    return "-" in ticker


def is_futures(ticker: str) -> bool:
    """True when ticker ends with '=F' (continuous futures contract)."""
    return ticker.endswith("=F")


def is_index(ticker: str) -> bool:
    """True when ticker starts with '^' (exchange index)."""
    return ticker.startswith("^")


def display_name(ticker: str) -> str:
    """
    Return a human-friendly display label for a ticker.

    Examples:
        "BTC-USD" → "BTC"
        "GC=F"    → "Gold (GC)"
        "^GSPC"   → "S&P 500 (^GSPC)"
        "NVDA"    → "NVDA"
    """
    _index_labels: dict[str, str] = {
        "^GSPC": "S&P 500",
        "^IXIC": "Nasdaq",
        "^DJI":  "Dow Jones",
        "^VIX":  "VIX",
    }
    _futures_labels: dict[str, str] = {
        "GC=F": "Gold",
        "SI=F": "Silver",
        "CL=F": "Crude Oil",
        "NG=F": "Natural Gas",
    }
    if ticker in _index_labels:
        return f"{_index_labels[ticker]} ({ticker})"
    if ticker in _futures_labels:
        return f"{_futures_labels[ticker]} ({ticker.replace('=F', '')})"
    if is_crypto(ticker):
        return ticker.split("-")[0]   # "BTC-USD" → "BTC"
    return ticker


# ─────────────────────────────────────────────────────────────────────────────
# DataFrame Normalisation (internal helper — not cached)
# ─────────────────────────────────────────────────────────────────────────────

def _normalise_df(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """
    Apply consistent post-processing to a raw yfinance DataFrame.

    Steps
    -----
    1. Flatten a MultiIndex column header (yfinance ≥0.2.x wraps single-ticker
       downloads in a two-level MultiIndex: (field, symbol)).
    2. Ensure the DatetimeIndex is tz-naive (strip UTC if present).
       Plotly's add_vline arithmetic requires tz-naive Timestamps.
    3. Keep only the five canonical OHLCV columns; drop everything else
       (e.g. "Dividends", "Stock Splits").
    4. Drop any rows where all five columns are NaN (common for index / crypto
       on market holidays).

    Args:
        df:     Raw DataFrame returned by yf.download().
        ticker: Symbol string — used only for logging.

    Returns:
        Cleaned DataFrame, or an empty DataFrame if the input is unusable.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    # Step 1 — flatten MultiIndex
    if isinstance(df.columns, pd.MultiIndex):
        # MultiIndex shape: (field, symbol) — keep the field level only
        df.columns = df.columns.get_level_values(0)

    # Step 2 — normalise index to tz-naive DatetimeIndex
    df.index = pd.to_datetime(df.index)
    df.index.name = "Date"
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)

    # Step 3 — keep only OHLCV columns that actually exist
    wanted = ["Open", "High", "Low", "Close", "Volume"]
    present = [col for col in wanted if col in df.columns]
    if not present:
        logger.warning("fetch_ohlcv(%s): none of %s found in columns %s",
                       ticker, wanted, list(df.columns))
        return pd.DataFrame()

    df = df[present].copy()

    # Step 4 — Indices and crypto sometimes have NaN Volume on holidays;
    # drop rows where Close itself is NaN, but keep rows where only Volume is NaN.
    df = df[df["Close"].notna()]

    # Fill missing Volume with 0 (indices like ^GSPC report no volume)
    if "Volume" in df.columns:
        df["Volume"] = df["Volume"].fillna(0)

    return df


# ─────────────────────────────────────────────────────────────────────────────
# Core Fetch Functions
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def fetch_ohlcv(ticker: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """
    Fetch OHLCV data for a single ticker from yfinance.

    Supports all asset classes in ASSET_UNIVERSE.  The ticker symbol must
    already be correctly formatted before being passed here:

        Equities   → plain symbol          "NVDA"
        Crypto     → "<BASE>-USD" suffix   "BTC-USD"   (NOT "BTC")
        Futures    → "=F" suffix           "GC=F"
        Indices    → "^" prefix            "^GSPC"

    The function never mutates or guesses the format — the caller is
    responsible for using the correct symbol.  All tickers in ASSET_UNIVERSE
    are already correctly formatted.

    Args:
        ticker:   Symbol string (see formatting rules above).
        period:   yfinance period string: "1d" "5d" "1mo" "3mo" "6mo"
                  "1y" "2y" "5y" "10y" "ytd" "max".
        interval: Bar size: "1m" "2m" "5m" "15m" "30m" "60m" "90m"
                  "1h" "1d" "5d" "1wk" "1mo" "3mo".
                  Note — intraday intervals (< "1d") are only available for
                  the past 60 days regardless of the period argument.

    Returns:
        DataFrame with columns [Open, High, Low, Close, Volume] indexed by a
        tz-naive DatetimeIndex.  Returns an *empty* DataFrame on any failure
        so callers can check `df.empty` without a try/except.
    """
    try:
        raw: pd.DataFrame = yf.download(
            ticker,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True,   # Adjusts for splits & dividends automatically
            actions=False,      # Exclude dividend / split columns
        )
        df = _normalise_df(raw, ticker)
        if df.empty:
            logger.warning("fetch_ohlcv(%s): download returned empty data", ticker)
        return df

    except Exception as exc:
        # Surface a non-fatal warning in the Streamlit UI so the user knows
        # which ticker failed, then return an empty DataFrame — the rest of
        # the dashboard continues to function normally.
        st.warning(
            f"⚠️ **{display_name(ticker)}** — could not fetch market data: "
            f"`{type(exc).__name__}: {exc}`"
        )
        logger.exception("fetch_ohlcv(%s) failed", ticker)
        return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def fetch_info(ticker: str) -> dict:
    """
    Fetch metadata and fundamentals for a ticker via yfinance.

    For equities this includes marketCap, trailingPE, sector, etc.
    For crypto / futures / indices the dict is sparser but still useful
    (e.g. regularMarketPrice, fiftyTwoWeekHigh / Low).

    Returns:
        Info dict, or an empty dict on failure.
    """
    try:
        info: dict = yf.Ticker(ticker).info
        return info if isinstance(info, dict) else {}
    except Exception as exc:
        logger.warning("fetch_info(%s) failed: %s", ticker, exc)
        return {}


@st.cache_data(ttl=60, show_spinner=False)
def fetch_latest_price(ticker: str) -> Optional[float]:
    """
    Fetch the most recent closing price for a ticker.

    Uses a 5-day window so the function works even on weekends / holidays
    when the most recent bar is a few days old.

    Returns:
        Latest closing price as float, or None on failure.
    """
    df = fetch_ohlcv(ticker, period="5d", interval="1d")
    if df.empty or "Close" not in df.columns:
        return None
    return round(float(df["Close"].iloc[-1]), 6)


# ─────────────────────────────────────────────────────────────────────────────
# Batch Fetch Helpers
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def fetch_asset_class(
    asset_class: AssetClass,
    period: str = "6mo",
    interval: str = "1d",
) -> dict[str, pd.DataFrame]:
    """
    Fetch OHLCV for every ticker in a named asset class.

    Args:
        asset_class: One of "MAG7", "TECH_SMALL", "CRYPTO",
                     "COMMODITIES", "INDICES".
        period:      yfinance period string (default "6mo").
        interval:    Bar interval (default "1d").

    Returns:
        Dict mapping ticker → OHLCV DataFrame.
        Tickers that fail return an empty DataFrame rather than raising;
        filter with `{k: v for k, v in result.items() if not v.empty}`.
    """
    tickers = ASSET_UNIVERSE.get(asset_class, [])
    return {
        t: fetch_ohlcv(t, period=period, interval=interval)
        for t in tickers
    }


@st.cache_data(ttl=300, show_spinner=False)
def fetch_all_mag7(period: str = "6mo") -> dict[str, pd.DataFrame]:
    """
    Fetch OHLCV data for all Magnificent Seven tickers.

    Preserved for backwards-compatibility with app.py and screener.py.
    Internally delegates to fetch_asset_class("MAG7", ...).

    Returns:
        Dict mapping ticker symbol → OHLCV DataFrame.
    """
    return fetch_asset_class("MAG7", period=period)


@st.cache_data(ttl=300, show_spinner=False)
def fetch_universe(
    asset_classes: list[AssetClass] | None = None,
    period: str = "6mo",
    interval: str = "1d",
) -> dict[str, pd.DataFrame]:
    """
    Fetch OHLCV data for multiple asset classes in one call.

    Args:
        asset_classes: List of class keys to include.  Pass None to fetch
                       *all* classes in ASSET_UNIVERSE.
        period:        yfinance period string.
        interval:      Bar interval.

    Returns:
        Flat dict of ticker → OHLCV DataFrame across all requested classes.

    Example:
        data = fetch_universe(["MAG7", "CRYPTO"])
        df_btc = data["BTC-USD"]
        df_nvda = data["NVDA"]
    """
    classes: list[AssetClass] = (
        list(ASSET_UNIVERSE.keys()) if asset_classes is None else asset_classes
    )
    result: dict[str, pd.DataFrame] = {}
    for cls in classes:
        result.update(fetch_asset_class(cls, period=period, interval=interval))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Volume & Market Microstructure Helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_volume_ratio(df: pd.DataFrame, lookback: int = 50) -> float:
    """
    Calculate today's volume as a multiple of the N-day average.

    Used by core/screener.py to confirm CAN SLIM pivot breakouts
    (requirement: volume ≥ 1.5× the 50-day average on breakout day).

    Note: Indices (^GSPC, ^IXIC) report zero volume from yfinance.
    The helper returns 0.0 in that case rather than dividing by zero.

    Args:
        df:       OHLCV DataFrame with a "Volume" column.
        lookback: Window for the baseline average (default 50 bars).

    Returns:
        Float ratio — e.g. 1.73 means 73 % above the average.
        Returns 0.0 when data is insufficient or volume is zero.
    """
    if df.empty or "Volume" not in df.columns or len(df) < 2:
        return 0.0
    # Use the N bars *before* the current bar as the baseline
    baseline = df["Volume"].iloc[-lookback - 1:-1]
    avg_vol: float = float(baseline.mean())
    if avg_vol == 0.0:
        return 0.0
    current_vol: float = float(df["Volume"].iloc[-1])
    return round(current_vol / avg_vol, 2)


def get_price_change_pct(df: pd.DataFrame, periods: int = 1) -> float:
    """
    Return the percentage price change over the last N bars.

    Args:
        df:      OHLCV DataFrame.
        periods: Number of bars to look back (default 1 = daily change).

    Returns:
        Percentage change as float (e.g. 2.34 means +2.34 %).
        Returns 0.0 on insufficient data.
    """
    if df.empty or "Close" not in df.columns or len(df) < periods + 1:
        return 0.0
    prev = float(df["Close"].iloc[-(periods + 1)])
    curr = float(df["Close"].iloc[-1])
    if prev == 0.0:
        return 0.0
    return round((curr - prev) / prev * 100, 4)
