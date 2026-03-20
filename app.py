import os
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

# Import functions from your core modules
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

# Mock definitions for missing components
ASSET_UNIVERSE = {"MAG7": MAG7}
AssetClass = str
def display_name(t): return t
def fetch_asset_class(c): return fetch_all_mag7()

load_dotenv()

# ─────────────────────────────────────────────
# Page Configuration
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="AstroVantage",
    page_icon="🔭",
    layout="wide",
)

# ─────────────────────────────────────────────
# Custom CSS - Optimized for Visibility
# ─────────────────────────────────────────────
st.markdown("""
<style>
    /* Main Background */
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #0d0f14 !important;
        color: #ffffff !important;
    }
    
    /* Table Styling for High Contrast */
    .stTable {
        background-color: #161a23 !important;
        border-radius: 10px !important;
        overflow: hidden !important;
        border: 1px solid #2d3748 !important;
    }
    
    /* Table Text and Cell Borders */
    [data-testid="stTable"] td, [data-testid="stTable"] th {
        color: #f1f5f9 !important;
        border-bottom: 1px solid #1e2538 !important;
        padding: 12px !important;
    }
    
    /* Section Headers */
    .section-header {
        font-size: 1.2rem;
        font-weight: 700;
        color: #a78bfa;
        margin-top: 25px;
        margin-bottom: 15px;
        padding-bottom: 5px;
        border-bottom: 2px solid #3e3e5e;
    }

    /* Astro Insight Cards */
    .astro-card {
        background: #1c212c;
        border-left: 4px solid #fbbf24;
        border-radius: 6px;
        padding: 15px;
        margin: 10px 0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Application UI Functions
# ─────────────────────────────────────────────
def render_header():
    st.markdown("""
        <div style='text-align: center; padding: 20px;'>
            <h1 style='color: #a78bfa;'>🔭 AstroVantage</h1>
            <p style='color: #64748b;'>CAN SLIM + URANIAN ASTROLOGY DASHBOARD</p>
        </div>
    """, unsafe_allow_html=True)

def main():
    render_header()
    
    # Sidebar
    with st.sidebar:
        st.title("Settings")
        selected_class = st.selectbox("Asset Class", options=list(ASSET_UNIVERSE.keys()))
        st.info("Aries Ingress Active ☀️")

    # Data Processing
    with st.spinner("Calculating Stars and Stocks..."):
        all_data = fetch_asset_class(selected_class)
        report = generate_daily_report()
        
    if not all_data:
        st.error("No data found.")
        return

    signals = screen_all(all_data)

    # Display Screener Table
    st.markdown('<div class="section-header">Market Screener Summary</div>', unsafe_allow_html=True)
    df_display = pd.DataFrame([
        {"Ticker": s.ticker, "Price": f"${s.price:.2f}", "RSI": f"{s.rsi:.1f}", "Signal": s.signal.upper()}
        for s in signals
    ])
    st.table(df_display)

    # Detailed Analysis
    st.markdown('<div class="section-header">Detailed Deep Dive</div>', unsafe_allow_html=True)
    ticker = st.selectbox("Pick a ticker", options=[s.ticker for s in signals])
    sig = next(s for s in signals if s.ticker == ticker)

    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader(f"{ticker} Price Action")
        df_chart = fetch_ohlcv(ticker)
        fig = go.Figure(data=[go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'])])
        fig.update_layout(template="plotly_dark", margin=dict(l=0,r=0,b=0,t=0))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Uranian Insights")
        for hit in report.active_hits:
            st.markdown(f"""
            <div class="astro-card">
                <b style="color:#fbbf24;">{hit.formula}</b><br>
                <small>{hit.interpretation}</small>
            </div>
            """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
