"""
app.py
------
AstroVantage — Main Streamlit Application
Dark-themed dashboard for Mag 7 stock entry analysis combining
CAN SLIM technical analysis with Uranian Hamburg School astrology.

Run with: streamlit run app.py
"""

from __future__ import annotations

import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from core.astro_logic import DailyAstroReport, generate_daily_report
from core.screener import (
    EntrySignal,
    RiskParameters,
    analyze_ticker,
    calculate_risk_parameters,
    screen_all,
)
# --- ส่วนที่ปู่แก้ไขให้เชื่อมต่อกับ fetcher.py ได้เป๊ะๆ ---
from utils.fetcher import (
    MAG7,
    fetch_all_mag7,
    fetch_ohlcv,
    get_volume_ratio,
)

# สร้างตัวแปรเสริม (Mock Data) เพื่อให้แอปทำงานได้โดยไม่ Error
ASSET_UNIVERSE = {"MAG7": MAG7}
AssetClass = str

def display_name(t: str) -> str:
    return t

def fetch_asset_class(asset_class: str):
    return fetch_all_mag7()
# --------------------------------------------------

load_dotenv()

# ─────────────────────────────────────────────
# Page Configuration
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="AstroVantage",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# Custom CSS — Dark Professional Theme
# ─────────────────────────────────────────────

st.markdown(
    """
<style>
/* ── Global ── */
html, body, [data-testid="stAppViewContainer"] {
    background-color: #0d0f14 !important;
    color: #e2e8f0;
    font-family: 'Inter', 'SF Pro Display', system-ui, sans-serif;
}
[data-testid="stSidebar"] { background-color: #111318 !important; }
[data-testid="stHeader"] { background-color: transparent !important; }

/* ── Metric cards ── */
[data-testid="metric-container"] {
    background: #161a23;
    border: 1px solid #1e2538;
    border-radius: 10px;
    padding: 16px 20px;
}
[data-testid="stMetricValue"] { color: #f1f5f9 !important; font-size: 1.6rem !important; }
[data-testid="stMetricLabel"] { color: #94a3b8 !important; font-size: 0.75rem !important; letter-spacing: 0.06em; text-transform: uppercase; }
[data-testid="stMetricDelta"] { font-size: 0.8rem !important; }

/* ── Tabs ── */
[data-testid="stTabs"] button {
    color: #64748b;
    border-radius: 6px 6px 0 0;
    font-weight: 500;
    font-size: 0.85rem;
    letter-spacing: 0.03em;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #a78bfa !important;
    border-bottom: 2px solid #a78bfa !important;
    background: #161a23 !important;
}

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg, #4f46e5, #7c3aed) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 10px 22px !important;
    letter-spacing: 0.02em;
    transition: opacity 0.2s;
}
.stButton > button:hover { opacity: 0.88; }

/* ── Alert / Info boxes ── */
.astro-card {
    background: #12151e;
    border: 1px solid #1e2538;
    border-radius: 12px;
    padding: 18px 22px;
    margin: 8px 0;
}
.astro-card.warning {
    border-color: #854d0e;
    background: #1a130a;
}
.astro-card.
