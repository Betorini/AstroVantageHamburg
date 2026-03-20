import os
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

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
    "CRYPTO": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"],
    "COMMODITIES": ["GC=F", "SI=F", "CL=F"]
}

def display_name(t: str) -> str:
    names = {"GC=F": "Gold", "SI=F": "Silver", "CL=F": "Crude Oil"}
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
# Page Configuration
# ─────────────────────────────────────────────
st.set_page_config(page_title="AstroVantage", page_icon="🔭", layout="wide")

# ─────────────────────────────────────────────
# Custom CSS - Bright Gold & High Contrast
# ─────────────────────────────────────────────
st.markdown("""
<style>
    /* Main Background */
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #16181c !important; 
        color: #ffffff !important;
    }
    
    [data-testid="stSidebar"] {
        background-color: #1c1f26 !important;
    }

    /* Target Metrics to be BRIGHT GOLD */
    [data-testid="stMetricValue"] {
        color: #FFD700 !important; /* Bright Gold */
        font-weight: 800 !important;
        font-size: 2.2rem !important;
    }
    [data-testid="stMetricLabel"] {
        color: #ffffff !important;
        font-size: 0.9rem !important;
        letter-spacing: 0.1em !important;
    }

    /* Table Styling */
    .stTable {
        background-color: transparent !important;
    }
    [data-testid="stTable"] th {
        color: #FFD700 !important; /* Gold Headers */
        background-color: #1c1f26 !important;
        font-size: 0.85rem !important;
    }
    [data-testid="stTable"] td {
        color: #ffffff !important;
        border-bottom: 1px solid #2d333f !important;
        font-size: 1rem !important;
    }

    /* Section Headers in Gold */
    h1, h2, h3, h4 {
        color: #FFD700 !important;
    }

    /* Entry Zone Box */
    .entry-box {
        background: #1c1f26;
        border: 2px solid #FFD700;
        padding: 20px;
        border-radius: 12px;
    }
    
    .astro-panel {
        background: #1c1f26;
        border: 1px solid #444;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Application UI
# ─────────────────────────────────────────────
def main():
    # Header
    col_h1, col_h2 = st.columns([2, 1])
    with col_h1:
        st.markdown("<h1 style='margin:0;'>🔭 AstroVantage</h1>", unsafe_allow_html=True)
        st.markdown("<p style='color:#ffffff;'>MAGNIFICENT SEVEN · CANSLIM + URANIAN ASTROLOGY</p>", unsafe_allow_html=True)
    with col_h2:
        st.markdown("<div style='text-align:right; color:#FFD700; font-size:1rem; font-weight:bold;'>☀️ ARIES INGRESS<br>March 20, 2026</div>", unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.markdown("<h3 style='color:#FFD700;'>Navigation</h3>", unsafe_allow_html=True)
        selected_class = st.selectbox("Select Asset Class", options=list(ASSET_UNIVERSE.keys()))
        st.markdown("---")
        st.info("☿ Mercury Station Direct")

    # Data Sync
    with st.spinner("Syncing with stars..."):
        all_data = fetch_asset_class_data(selected_class)
        report = generate_daily_report()
        signals = screen_all(all_data)

    # 1. LIVE METRICS - GOLD THEME
    ticker_choice = st.selectbox("Analyze Ticker", options=[s.ticker for s in signals], format_func=display_name)
    sig = next(s for s in signals if s.ticker == ticker_choice)

    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("CURRENT PRICE", f"${sig.price:,.2f}")
    m2.metric("RSI (14)", f"{sig.rsi:.1f}")
    m3.metric("VOLUME RATIO", f"{sig.volume_ratio:.2f}x")
    m4.metric("SIGNAL", sig.signal.upper())

    # 2. MAIN DASHBOARD AREA
    col_chart, col_astro = st.columns([2, 1])

    with col_chart:
        st.markdown("### PRICE ACTION")
        df_chart = fetch_ohlcv(ticker_choice)
        if not df_chart.empty:
            fig = go.Figure(data=[go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'])])
            fig.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=450, margin=dict(l=0,r=0,t=0,b=0))
            st.plotly_chart(fig, use_container_width=True)
        
        # Entry Zone Detail
        st.markdown(f"""
        <div class="entry-box">
            <small style='color:#ffffff;'>ENTRY ZONE</small>
            <h2 style='margin:0; color:#FFD700;'>${sig.price * 0.98:,.2f} – ${sig.price * 1.02:,.2f}</h2>
            <div style='display:flex; justify-content:space-between; margin-top:15px;'>
                <div><small style='color:#ffffff;'>STOP LOSS</small><br><b style='color:#ef4444;'>${sig.price * 0.92:,.2f}</b></div>
                <div><small style='color:#ffffff;'>RISK/REWARD</small><br><b style='color:#22c55e;'>1 : 2.0</b></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_astro:
        st.markdown("### URANIAN INSIGHTS")
        for hit in report.active_hits:
            st.markdown(f"""
            <div class="astro-panel">
                <div style="color:#FFD700; font-weight:bold;">⚡ {hit.formula}</div>
                <div style="font-size:0.9rem; color:#ffffff; line-height:1.5; margin-top:5px;">{hit.interpretation}</div>
            </div>
            """, unsafe_allow_html=True)

    # 3. SCREENER TABLE
    st.markdown(f"### SCREENER — {selected_class}")
    df_screen = pd.DataFrame([{
        "TICKER": s.ticker, "PRICE": f"${s.price:,.2f}", "RSI": f"{s.rsi:.1f}", 
        "VOL RATIO": f"{s.volume_ratio:.2f}x", "SIGNAL": s.signal.upper()
    } for s in signals])
    st.table(df_screen)

if __name__ == "__main__":
    main()
