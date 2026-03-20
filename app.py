import os
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

# Import core modules
try:
    from core.astro_logic import DailyAstroReport, generate_daily_report
    from core.screener import analyze_ticker, screen_all
    from utils.fetcher import MAG7, fetch_ohlcv
except ImportError:
    st.error("Missing core modules. Please check your folder structure.")

# ─────────────────────────────────────────────
# 🛠️ Define Missing Functions
# ─────────────────────────────────────────────
ASSET_UNIVERSE = {
    "MAG7": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA"],
    "CRYPTO": ["BTC-USD", "ETH-USD", "SOL-USD"],
    "COMMODITIES": ["GC=F", "SI=F", "CL=F"]
}

def display_name(t: str) -> str:
    names = {"GC=F": "Gold", "SI=F": "Silver", "CL=F": "Crude Oil"}
    return names.get(t, t)

# ปู่เพิ่มฟังก์ชันที่ขาดไปตรงนี้ครับ!
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
st.set_page_config(page_title="AstroVantage", page_icon="🔭", layout="wide")

st.markdown("""
<style>
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #16181c !important; 
        color: #ffffff !important;
    }
    [data-testid="stSidebar"] {
        background-color: #1c1f26 !important;
    }
    [data-testid="stMetricValue"] {
        color: #FFD700 !important;
        font-weight: 800 !important;
        font-size: 2.2rem !important;
    }
    h1, h2, h3 { color: #FFD700 !important; }
    .astro-card {
        background: #1e222a;
        border-left: 4px solid #FFD700;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 10px;
    }
    .stTable { background-color: transparent !important; }
    [data-testid="stTable"] th { color: #FFD700 !important; }
</style>
""", unsafe_allow_html=True)

def main():
    # Header
    col_t, col_s = st.columns([3, 1])
    with col_t:
        st.markdown("<h1 style='margin:0;'>🔭 AstroVantage</h1>", unsafe_allow_html=True)
        st.caption("CAN SLIM + URANIAN ASTROLOGY DASHBOARD")
    with col_s:
        st.markdown("<div style='text-align:right; color:#FFD700;'><b>☀️ ARIES INGRESS</b><br>March 20, 2026</div>", unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.markdown("### Navigation")
        selected_class = st.selectbox("Market Universe", options=list(ASSET_UNIVERSE.keys()))
        if st.button("🔄 Manual Refresh"):
            st.cache_data.clear()
            st.rerun()
        st.markdown("---")
        st.info("☿ Mercury Station Direct")

    # Execution
    try:
        with st.spinner("Syncing Stars & Markets..."):
            all_data = fetch_asset_class_data(selected_class)
            signals = screen_all(all_data)
            report = generate_daily_report()

        if not signals:
            st.warning("No data found for this asset class.")
            return

        ticker_choice = st.selectbox("Analyze Ticker", options=[s.ticker for s in signals], format_func=display_name)
        sig = next(s for s in signals if s.ticker == ticker_choice)

        st.markdown("---")
        
        # Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("PRICE", f"${sig.price:,.2f}")
        m2.metric("RSI", f"{sig.rsi:.1f}")
        m3.metric("VOL RATIO", f"{sig.volume_ratio:.2f}x")
        m4.metric("SIGNAL", sig.signal.upper())

        # Main Layout
        col_left, col_right = st.columns([2, 1])

        with col_left:
            st.markdown("### Technical View")
            df_chart = fetch_ohlcv(ticker_choice)
            if not df_chart.empty:
                fig = go.Figure(data=[go.Candlestick(
                    x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close']
                )])
                fig.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=400)
                st.plotly_chart(fig, use_container_width=True)
            
            # Gann Entry Box
            st.markdown(f"""
            <div style="background:#1e222a; border:1px solid #FFD700; padding:15px; border-radius:10px;">
                <span style="color:#FFD700; font-weight:bold;">🎯 GANN ENTRY ZONE:</span> 
                <b style="font-size:1.5rem; margin-left:10px; color:#ffffff;">${sig.price * 0.98:,.2f} - ${sig.price * 1.01:,.2f}</b>
            </div>
            """, unsafe_allow_html=True)

        with col_right:
            st.markdown("### Financial Astro")
            # Show formulas from report or default list
            formulas =
