import os
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

# Import functions from core modules
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

# Configuration for multiple asset classes
ASSET_UNIVERSE = {
    "MAG7": MAG7,
    "CRYPTO": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"],
    "COMMODITIES": ["GC=F", "SI=F", "CL=F"]
}

def display_name(t: str) -> str:
    names = {
        "GC=F": "Gold",
        "SI=F": "Silver",
        "CL=F": "Crude Oil",
        "BTC-USD": "Bitcoin",
        "ETH-USD": "Ethereum",
        "SOL-USD": "Solana",
        "BNB-USD": "Binance Coin"
    }
    return names.get(t, t)

def fetch_asset_class_data(asset_class: str):
    tickers = ASSET_UNIVERSE.get(asset_class, MAG7)
    data_dict = {}
    for t in tickers:
        df = fetch_ohlcv(t)
        if not df.empty:
            data_dict[t] = df
    return data_dict

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
# Custom CSS - Better Contrast & Visibility
# ─────────────────────────────────────────────
st.markdown("""
<style>
    /* Main Background - Deep Professional Navy */
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #10141d !important;
        color: #ffffff !important;
    }
    
    /* Sidebar Background */
    [data-testid="stSidebar"] {
        background-color: #1a1f2c !important;
    }

    /* Table Styling - Lighter Background for readability */
    .stTable {
        background-color: #1e2533 !important;
        border-radius: 8px !important;
        border: 1px solid #334155 !important;
    }
    
    /* Table Headers and Rows */
    [data-testid="stTable"] th {
        background-color: #2d3748 !important;
        color: #a78bfa !important;
        font-weight: bold !important;
        text-transform: uppercase;
        font-size: 0.85rem;
    }
    [data-testid="stTable"] td {
        color: #f8fafc !important;
        border-bottom: 1px solid #334155 !important;
    }

    /* Section Headers */
    .section-header {
        font-size: 1.3rem;
        font-weight: 700;
        color: #fbbf24;
        margin-top: 30px;
        margin-bottom: 15px;
        padding-bottom: 8px;
        border-bottom: 2px solid #a78bfa;
    }

    /* Astro Insight Cards - Golden Highlight */
    .astro-card {
        background: #242c3d;
        border-left: 5px solid #fbbf24;
        border-radius: 8px;
        padding: 20px;
        margin: 12px 0;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    }
    
    /* Improve Metrics Visibility */
    [data-testid="stMetricValue"] {
        color: #ffffff !important;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Application UI Functions
# ─────────────────────────────────────────────
def render_header():
    st.markdown("""
        <div style='text-align: center; padding: 30px 0;'>
            <h1 style='color: #a78bfa; margin-bottom: 0;'>🔭 AstroVantage</h1>
            <p style='color: #94a3b8; font-size: 1.1rem; letter-spacing: 1px;'>
                CAN SLIM + URANIAN ASTROLOGY DASHBOARD
            </p>
        </div>
    """, unsafe_allow_html=True)

def main():
    render_header()
    
    # Sidebar
    with st.sidebar:
        st.markdown("<h2 style='color: #fbbf24;'>Controls</h2>", unsafe_allow_html=True)
        # นี่คือจุดที่ Asset Class อยู่ครับหลาน!
        selected_class = st.selectbox(
            "Select Asset Class", 
            options=list(ASSET_UNIVERSE.keys()),
            help="Switch between Tech Stocks, Crypto, and Commodities"
        )
        st.markdown("---")
        st.success("☀️ Aries Ingress Active")
        st.info("☿ Mercury Station Direct")

    # Data Processing
    with st.spinner(f"Scanning {selected_class} Markets..."):
        all_data = fetch_asset_class_data(selected_class)
        report = generate_daily_report()
        
    if not all_data:
        st.warning("Data sync in progress... Please wait.")
        return

    signals = screen_all(all_data)

    # 1. Market Screener
    st.markdown(f'<div class="section-header">{selected_class} Screener Summary</div>', unsafe_allow_html=True)
    df_display = pd.DataFrame([
        {
            "Ticker": display_name(s.ticker), 
            "Price": f"${s.price:,.2f}", 
            "RSI": f"{s.rsi:.1f}", 
            "Signal": s.signal.upper()
        }
        for s in signals
    ])
    st.table(df_display)

    # 2. Detailed Analysis
    st.markdown('<div class="section-header">Technical & Astro Deep Dive</div>', unsafe_allow_html=True)
    ticker_choice = st.selectbox("Select a ticker for detail", options=[s.ticker for s in signals], format_func=display_name)
    sig = next(s for s in signals if s.ticker == ticker_choice)

    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader(f"{display_name(ticker_choice)} Performance")
        df_chart = fetch_ohlcv(ticker_choice)
        if not df_chart.empty:
            fig = go.Figure(data=[go.Candlestick(
                x=df_chart.index, 
                open=df_chart['Open'], 
                high=df_chart['High'], 
                low=df_chart['Low'], 
                close=df_chart['Close']
            )])
            fig.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Uranian Insights")
        if report.active_hits:
            for hit in report.active_hits:
                st.markdown(f"""
                <div class="astro-card">
                    <b style="color:#fbbf24; font-size: 1.1rem;">{hit.formula}</b><br>
                    <p style="color:#e2e8f0; margin-top: 8px;">{hit.interpretation}</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.write("Planetary pictures are neutral today.")

if __name__ == "__main__":
    main()
