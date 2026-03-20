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

# Configuration for multiple asset classes
ASSET_UNIVERSE = {
    "MAG7": MAG7,
    "CRYPTO": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"],
    "COMMODITIES": ["GC=F", "SI=F", "CL=F"] # Gold, Silver, Crude Oil
}

def display_name(t: str) -> str:
    names = {
        "GC=F": "Gold",
        "SI=F": "Silver",
        "CL=F": "Crude Oil",
        "BTC-USD": "Bitcoin",
        "ETH-USD": "Ethereum"
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
# Custom CSS - English Only & High Contrast
# ─────────────────────────────────────────────
st.markdown("""
<style>
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #0d0f14 !important;
        color: #ffffff !important;
    }
    .stTable {
        background-color: #161a23 !important;
        border-radius: 10px !important;
        overflow: hidden !important;
        border: 1px solid #2d3748 !important;
    }
    [data-testid="stTable"] td, [data-testid="stTable"] th {
        color: #f1f5f9 !important;
        border-bottom: 1px solid #1e2538 !important;
        padding: 12px !important;
    }
    .section-header {
        font-size: 1.2rem;
        font-weight: 700;
        color: #a78bfa;
        margin-top: 25px;
        margin-bottom: 15px;
        padding-bottom: 5px;
        border-bottom: 2px solid #3e3e5e;
    }
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
# Application UI
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
    
    # Sidebar Selection
    with st.sidebar:
        st.title("Navigation")
        selected_class = st.selectbox("Select Asset Class", options=list(ASSET_UNIVERSE.keys()))
        st.success("Aries Ingress Active ☀️")

    # Data Processing
    with st.spinner(f"Analyzing {selected_class} stars..."):
        all_data = fetch_asset_class_data(selected_class)
        report = generate_daily_report()
        
    if not all_data:
        st.warning("Gathering market data... Please wait.")
        return

    signals = screen_all(all_data)

    # Market Summary
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

    # Analysis Section
    st.markdown('<div class="section-header">Deep Dive Analysis</div>', unsafe_allow_html=True)
    ticker_choice = st.selectbox("Pick a ticker", options=[s.ticker for s in signals], format_func=display_name)
    sig = next(s for s in signals if s.ticker == ticker_choice)

    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader(f"{display_name(ticker_choice)} Chart")
        df_chart = fetch_ohlcv(ticker_choice)
        if not df_chart.empty:
            fig = go.Figure(data=[go.Candlestick(
                x=df_chart.index, 
                open=df_chart['Open'], 
                high=df_chart['High'], 
                low=df_chart['Low'], 
                close=df_chart['Close']
            )])
            fig.update_layout(template="plotly_dark", margin=dict(l=0,r=0,b=0,t=0))
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Uranian Insights")
        if report.active_hits:
            for hit in report.active_hits:
                st.markdown(f"""
                <div class="astro-card">
                    <b style="color:#fbbf24;">{hit.formula}</b><br>
                    <small>{hit.interpretation}</small>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.write("No major planetary hits today.")

if __name__ == "__main__":
    main()
