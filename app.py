import os
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

# Core Module Imports
from core.astro_logic import DailyAstroReport, generate_daily_report
from core.screener import (
    EntrySignal,
    analyze_ticker,
    calculate_risk_parameters,
    screen_all,
)
from utils.fetcher import (
    MAG7,
    fetch_all_mag7,
    fetch_ohlcv,
    get_volume_ratio,
)

# Configuration
ASSET_UNIVERSE = {
    "MAG7": MAG7,
    "CRYPTO": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD"],
    "COMMODITIES": ["GC=F", "SI=F", "CL=F", "HG=F"]
}

def display_name(t: str) -> str:
    names = {"GC=F": "Gold", "SI=F": "Silver", "CL=F": "Crude Oil", "HG=F": "Copper"}
    return names.get(t, t)

def fetch_asset_class_data(asset_class: str):
    tickers = ASSET_UNIVERSE.get(asset_class, MAG7)
    data_dict = {}
    for t in tickers:
        df = fetch_ohlcv(t)
        if not df.empty: data_dict[t] = df
    return data_dict

load_dotenv()

# ─────────────────────────────────────────────
# Page Configuration & Adaptive CSS
# ─────────────────────────────────────────────
st.set_page_config(page_title="AstroVantage", page_icon="🔭", layout="wide")

st.markdown("""
<style>
    /* Adaptive & Pro Dark Theme */
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #111418 !important; 
        color: #f1f5f9 !important;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] { background-color: #1a1d23 !important; }

    /* Bright Gold Accents */
    h1, h2, h3, .gold-text { color: #FFD700 !important; font-weight: 700 !important; }
    
    [data-testid="stMetricValue"] {
        color: #FFD700 !important;
        font-weight: 800 !important;
        font-size: clamp(1.5rem, 5vw, 2.2rem) !important; /* Adaptive Font */
    }

    /* Professional Cards */
    .st-emotion-cache-1r6slb0 { /* Metric Container */
        background-color: #1e222a !important;
        border: 1px solid #334155 !important;
        border-radius: 12px !important;
    }

    .astro-card {
        background: #1e222a;
        border-left: 5px solid #FFD700;
        border-radius: 8px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }

    /* Adaptive Table */
    .stTable { width: 100% !important; overflow-x: auto !important; }
    [data-testid="stTable"] th { color: #FFD700 !important; background-color: #2d333f !important; }

    /* Button Styling */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        border: 1px solid #FFD700;
        color: #FFD700;
        background-color: transparent;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #FFD700;
        color: #111418;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Main Logic
# ─────────────────────────────────────────────
def main():
    # Header
    col_title, col_status = st.columns([3, 1])
    with col_title:
        st.markdown("<h1 style='margin-bottom:0;'>🔭 AstroVantage</h1>", unsafe_allow_html=True)
        st.caption("FINANCIAL ASTROLOGY & QUANT SCREENER")
    with col_status:
        st.markdown("<div style='text-align:right; color:#FFD700;'><b>☀️ ARIES INGRESS</b><br><small>Equinox Cycle 2026</small></div>", unsafe_allow_html=True)

    # Sidebar Controls
    with st.sidebar:
        st.markdown("<h3 class='gold-text'>Navigation</h3>", unsafe_allow_html=True)
        selected_class = st.selectbox("Market Universe", options=list(ASSET_UNIVERSE.keys()))
        
        # 🔄 Manual Refresh Button
        if st.button("🔄 Manual Refresh"):
            st.cache_data.clear()
            st.rerun()
            
        st.markdown("---")
        st.info("☿ Mercury Station Direct")
        st.warning("⚠️ High Volatility Expected")

    # Data Processing
    with st.spinner("Calculating Planetary Aspects..."):
        all_data = fetch_asset_class_data(selected_class)
        # ปู่ใส่สูตร Financial Astro ในส่วน report นี้ครับ
        report = generate_daily_report() 
        signals = screen_all(all_data)

    if not signals:
        st.error("No market data available.")
        return

    # 1. LIVE PERFORMANCE (Adaptive Grid)
    ticker_choice = st.selectbox("Select Asset to Inspect", options=[s.ticker for s in signals], format_func=display_name)
    sig = next(s for s in signals if s.ticker == ticker_choice)

    st.markdown("---")
    # Adaptive Metrics
    m1, m2, m3, m4 = st.columns([1,1,1,1])
    m1.metric("PRICE", f"${sig.price:,.2f}")
    m2.metric("RSI", f"{sig.rsi:.1f}")
    m3.metric("VOL RATIO", f"{sig.volume_ratio:.2f}x")
    m4.metric("SIGNAL", sig.signal.upper())

    # 2. DASHBOARD LAYOUT (Adaptive Columns)
    col_chart, col_astro = st.columns([2, 1])

    with col_chart:
        st.markdown("<h3 class='gold-text'>Technical Chart</h3>", unsafe_allow_html=True)
        df_chart = fetch_ohlcv(ticker_choice)
        if not df_chart.empty:
            fig = go.Figure(data=[go.Candlestick(
                x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close']
            )])
            fig.update_layout(
                template="plotly_dark", 
                paper_bgcolor='rgba(0,0,0,0)', 
                plot_bgcolor='rgba(0,0,0,0)', 
                height=400,
                margin=dict(l=10, r=10, t=0, b=0)
            )
            st.plotly_chart(fig, use_container_width=True)

        # Entry Zone Detail
        st.markdown(f"""
        <div style="background:#1e222a; border:1px solid #334155; padding:20px; border-radius:12px;">
            <div style="color:#FFD700; font-weight:bold; margin-bottom:10px;">🎯 GANN ENTRY ZONE</div>
            <div style="font-size:1.8rem; font-weight:bold;">${sig.price * 0.98:,.2f} – ${sig.price * 1.01:,.2f}</div>
            <div style="margin-top:10px; color:#ef4444;">Stop Loss: ${sig.price * 0.93:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    with col_astro:
        st.markdown("<h3 class='gold-text'>Financial Astro Pictures</h3>", unsafe_allow_html=True)
        # แสดงผลสูตรพระเคราะห์สนธิ
