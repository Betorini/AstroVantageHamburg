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
from utils.fetcher import (
    ASSET_UNIVERSE,
    MAG7,
    AssetClass,
    display_name,
    fetch_all_mag7,
    fetch_asset_class,
    fetch_ohlcv,
    get_volume_ratio,
)

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
.astro-card.bullish {
    border-color: #166534;
    background: #0a130c;
}
.astro-card.bearish {
    border-color: #991b1b;
    background: #130a0a;
}
.signal-pill {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}
.pill-strong-buy  { background: #166534; color: #4ade80; }
.pill-buy         { background: #14532d; color: #86efac; }
.pill-neutral     { background: #1e2538; color: #94a3b8; }
.pill-sell        { background: #7f1d1d; color: #fca5a5; }
.pill-strong-sell { background: #991b1b; color: #fecaca; }

/* ── Section headers ── */
.section-header {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #475569;
    margin: 24px 0 12px 0;
    border-bottom: 1px solid #1e2538;
    padding-bottom: 6px;
}
.grandpa-quote {
    font-style: italic;
    color: #fbbf24;
    font-size: 0.95rem;
    border-left: 3px solid #f59e0b;
    padding-left: 14px;
    margin: 10px 0;
}
.planet-row {
    display: flex;
    justify-content: space-between;
    padding: 5px 0;
    border-bottom: 1px solid #1a1e2d;
    font-size: 0.82rem;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] .stSelectbox label {
    color: #94a3b8 !important;
    font-size: 0.72rem !important;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
[data-testid="stSidebar"] .stSelectbox > div > div {
    background: #161a23 !important;
    border-color: #1e2538 !important;
    color: #e2e8f0 !important;
    border-radius: 8px !important;
}
.sidebar-ticker-badge {
    display: inline-block;
    background: #161a23;
    border: 1px solid #1e2538;
    border-radius: 6px;
    padding: 3px 10px;
    font-size: 0.75rem;
    color: #94a3b8;
    margin: 2px 3px;
    font-family: 'SF Mono', 'Fira Code', monospace;
}
.sidebar-section {
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #334155;
    margin: 16px 0 8px 0;
    padding-bottom: 4px;
    border-bottom: 1px solid #1a1e2d;
}
.class-pill {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    margin-bottom: 10px;
}
.class-pill-mag7       { background: #1e1b4b; color: #a78bfa; }
.class-pill-tech_small { background: #0c2a4a; color: #38bdf8; }
.class-pill-crypto     { background: #0a2e1e; color: #34d399; }
.class-pill-commodities{ background: #2a1e0a; color: #fbbf24; }
.class-pill-indices    { background: #1a1e2d; color: #94a3b8; }
</style>
""",
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────

# Human-readable labels and accent colours for each asset class
_CLASS_META: dict[str, dict] = {
    "MAG7":        {"label": "Magnificent Seven",  "icon": "🏆", "pill": "class-pill-mag7",        "color": "#a78bfa"},
    "TECH_SMALL":  {"label": "Small-Cap Tech",     "icon": "🚀", "pill": "class-pill-tech_small",  "color": "#38bdf8"},
    "CRYPTO":      {"label": "Cryptocurrencies",   "icon": "₿",  "pill": "class-pill-crypto",      "color": "#34d399"},
    "COMMODITIES": {"label": "Commodities",        "icon": "🪙", "pill": "class-pill-commodities", "color": "#fbbf24"},
    "INDICES":     {"label": "Indices",            "icon": "📊", "pill": "class-pill-indices",     "color": "#94a3b8"},
}


def render_sidebar() -> AssetClass:
    """
    Render the sidebar asset-class selector and ticker roster.

    Returns:
        The currently selected AssetClass key string, e.g. "MAG7".
    """
    with st.sidebar:
        # ── Logo ────────────────────────────────────────────────────────────
        st.markdown(
            """
            <div style="padding:12px 0 20px 0; text-align:center;">
              <div style="font-size:2rem;">🔭</div>
              <div style="font-size:1.1rem; font-weight:700;
                          background:linear-gradient(135deg,#a78bfa,#38bdf8);
                          -webkit-background-clip:text; -webkit-text-fill-color:transparent;">
                AstroVantage
              </div>
              <div style="font-size:0.68rem; color:#334155; letter-spacing:0.08em; margin-top:2px;">
                URANIAN ASTRO-FINANCE
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div class="sidebar-section">Asset Class</div>', unsafe_allow_html=True)

        # Build display options: "🏆 Magnificent Seven" etc.
        options: list[AssetClass] = list(ASSET_UNIVERSE.keys())  # type: ignore[assignment]
        display_options = [
            f"{_CLASS_META[k]['icon']} {_CLASS_META[k]['label']}" for k in options
        ]

        selected_idx = st.selectbox(
            label="Select Asset Class",
            options=range(len(options)),
            format_func=lambda i: display_options[i],
            index=0,
            label_visibility="collapsed",
        )
        selected_class: AssetClass = options[selected_idx]  # type: ignore[assignment]
        meta = _CLASS_META[selected_class]

        # Class badge
        st.markdown(
            f'<span class="class-pill {meta["pill"]}">'
            f'{meta["icon"]} {meta["label"]}</span>',
            unsafe_allow_html=True,
        )

        # ── Ticker roster for selected class ────────────────────────────────
        st.markdown('<div class="sidebar-section">Tickers in this class</div>', unsafe_allow_html=True)
        tickers = ASSET_UNIVERSE[selected_class]
        badge_html = "".join(
            f'<span class="sidebar-ticker-badge">{display_name(t)}</span>'
            for t in tickers
        )
        st.markdown(
            f'<div style="line-height:2.2;">{badge_html}</div>',
            unsafe_allow_html=True,
        )

        # ── Astro status strip ───────────────────────────────────────────────
        st.markdown('<div class="sidebar-section">Astro Status · Mar 20 2026</div>', unsafe_allow_html=True)
        st.markdown(
            """
            <div style="font-size:0.8rem; line-height:2;">
              <div>☀️ <span style="color:#a78bfa; font-weight:600;">Aries Ingress</span> — active today</div>
              <div>☿ <span style="color:#34d399; font-weight:600;">Mercury Direct</span> — tech bullish</div>
              <div>⚡ <span style="color:#fbbf24; font-weight:600;">JU = SU/UR</span> — evaluating…</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.markdown(
            '<div style="font-size:0.68rem; color:#334155; text-align:center;">'
            "For educational use only.<br>Not financial advice."
            "</div>",
            unsafe_allow_html=True,
        )

    return selected_class


def render_header(selected_class: AssetClass = "MAG7") -> None:
    meta = _CLASS_META.get(selected_class, _CLASS_META["MAG7"])
    col_logo, col_info = st.columns([3, 1])
    with col_logo:
        st.markdown(
            f"""
            <div style='display:flex; align-items:center; gap:14px; padding:10px 0;'>
              <div style='font-size:2.2rem;'>🔭</div>
              <div>
                <h1 style='margin:0; font-size:1.9rem; font-weight:700;
                           background:linear-gradient(135deg,#a78bfa,#38bdf8);
                           -webkit-background-clip:text; -webkit-text-fill-color:transparent;
                           letter-spacing:-0.02em;'>
                  AstroVantage
                </h1>
                <p style='margin:0; color:#64748b; font-size:0.82rem; letter-spacing:0.04em;'>
                  {meta["icon"]} {meta["label"].upper()} &nbsp;·&nbsp; CANSLIM + URANIAN ASTROLOGY
                </p>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_info:
        st.markdown(
            """
            <div style='text-align:right; padding-top:14px; color:#64748b; font-size:0.78rem;'>
              <div style='color:#a78bfa; font-weight:600;'>☀️ ARIES INGRESS</div>
              <div>March 20, 2026</div>
              <div style='color:#34d399;'>☿ Mercury Station Direct</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────
# Metric Cards
# ─────────────────────────────────────────────

def render_metric_cards(signal: EntrySignal) -> None:
    st.markdown('<div class="section-header">Live Metrics</div>', unsafe_allow_html=True)
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Current Price", f"${signal.price:,.2f}")
    with col2:
        rsi_delta = "Overbought ⚠️" if signal.rsi > 70 else ("Oversold 🟢" if signal.rsi < 30 else "Healthy")
        st.metric("RSI (14)", f"{signal.rsi:.1f}", delta=rsi_delta)
    with col3:
        vol_label = "Heavy 🔥" if signal.volume_ratio >= 1.5 else "Normal"
        st.metric("Volume Ratio", f"{signal.volume_ratio:.2f}x", delta=vol_label)
    with col4:
        st.metric("EMA Alignment", signal.ema_align.title())
    with col5:
        pill_class = f"pill-{signal.signal.replace('_', '-')}"
        label = signal.signal.replace("_", " ").title()
        st.markdown(
            f"""
            <div style='text-align:center; padding-top:8px;'>
              <div style='color:#94a3b8; font-size:0.72rem; text-transform:uppercase;
                          letter-spacing:0.08em; margin-bottom:6px;'>Signal</div>
              <span class='signal-pill {pill_class}'>{label}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────
# Plotly Candlestick Chart
# ─────────────────────────────────────────────

def render_price_chart(ticker: str, signal: EntrySignal) -> None:
    st.markdown('<div class="section-header">Price Action · EMA Overlay</div>', unsafe_allow_html=True)

    with st.spinner(f"Loading {ticker} chart..."):
        df = fetch_ohlcv(ticker, period="6mo", interval="1d")

    if df.empty:
        st.warning("No chart data available.")
        return

    # ── Fix 1: Normalise the DatetimeIndex ──────────────────────────────────
    # yfinance ≥0.2.x sometimes returns a tz-aware index (UTC).  Plotly's
    # add_vline / add_hline internal arithmetic fails when it tries to add an
    # int offset to a tz-aware Timestamp, producing the TypeError the user saw.
    # Strip timezone info so every timestamp is a plain, tz-naive datetime.
    if hasattr(df.index, "tz") and df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    # Ensure the index is a proper DatetimeIndex (not object/string dtype).
    df.index = pd.to_datetime(df.index)

    from core.indicators import get_ema_stack
    ema_stack = get_ema_stack(df)

    fig = go.Figure()

    # Candlesticks
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"],
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        name=ticker,
        increasing_line_color="#4ade80",
        decreasing_line_color="#f87171",
        increasing_fillcolor="#166534",
        decreasing_fillcolor="#7f1d1d",
        line_width=1,
    ))

    # EMA Lines
    ema_config = [
        ("ema21", "EMA 21", "#34d399", "solid"),
        ("ema50", "EMA 50", "#fbbf24", "dot"),
        ("ema200", "EMA 200", "#f87171", "dash"),
    ]
    for key, label, color, dash in ema_config:
        series = ema_stack[key].dropna()
        # Strip tz from EMA index to stay consistent with the normalised df
        if hasattr(series.index, "tz") and series.index.tz is not None:
            series.index = series.index.tz_localize(None)
        fig.add_trace(go.Scatter(
            x=series.index,
            y=series.values,
            name=label,
            line=dict(color=color, width=1.5, dash=dash),
            opacity=0.85,
        ))

    # ── Fix 2: Wrap every shape/annotation call in try/except ───────────────
    # Plotly's hrect / hline / vline annotation helpers can raise if the axis
    # type has not yet been inferred (before the first trace is rendered) or if
    # the requested coordinate falls outside the visible range.

    # Entry Zone shading
    if signal.entry_low > 0 and signal.entry_high > 0:
        try:
            fig.add_hrect(
                y0=signal.entry_low,
                y1=signal.entry_high,
                fillcolor="rgba(167,139,250,0.08)",
                line_color="rgba(167,139,250,0.3)",
                line_width=1,
                annotation_text="Entry Zone",
                annotation_position="right",
                annotation_font_color="#a78bfa",
                annotation_font_size=10,
            )
        except Exception:
            pass  # Non-fatal — chart still renders without the shading

    # Stop Loss line
    try:
        fig.add_hline(
            y=signal.stop_loss,
            line_color="#ef4444",
            line_dash="dot",
            line_width=1.5,
            annotation_text=f"Stop ${signal.stop_loss:.2f}",
            annotation_position="right",
            annotation_font_color="#ef4444",
            annotation_font_size=10,
        )
    except Exception:
        pass

    # ── Fix 3: Aries Ingress vertical marker ────────────────────────────────
    # Plotly's add_vline x parameter for a datetime axis must be either:
    #   (a) a pandas Timestamp / Python datetime, or
    #   (b) a Unix timestamp in *milliseconds* (int/float).
    # Passing a bare ISO string ("2026-03-20") triggers the TypeError because
    # Plotly's internal layout code does `x + offset_ms` where offset_ms is an
    # int — hence "unsupported operand type(s) for +: 'int' and 'str'".
    # Solution: convert to a tz-naive Timestamp so Plotly infers the type
    # correctly, and only draw the line when the date is within the df range.
    try:
        aries_ts = pd.Timestamp("2026-03-20")  # tz-naive Timestamp
        df_start: pd.Timestamp = df.index.min()
        df_end: pd.Timestamp = df.index.max()

        if df_start <= aries_ts <= df_end:
            # Date is inside the plotted window — draw the line normally.
            fig.add_vline(
                x=aries_ts,
                line_color="#a78bfa",
                line_dash="dash",
                line_width=1.5,
                annotation_text="☀️ Aries Ingress",
                annotation_position="top left",
                annotation_font_color="#a78bfa",
                annotation_font_size=10,
            )
        else:
            # Date is outside the window (e.g. future date not yet in data).
            # Fall back to a plain vertical shape on the last bar so the
            # annotation is still visible without triggering out-of-range errors.
            last_bar_ts = df.index[-1]
            fig.add_vline(
                x=last_bar_ts,
                line_color="#a78bfa",
                line_dash="dash",
                line_width=1.5,
                annotation_text="☀️ Aries Ingress (Mar 20)",
                annotation_position="top left",
                annotation_font_color="#a78bfa",
                annotation_font_size=10,
            )
    except Exception:
        pass  # Never crash the chart over a cosmetic annotation

    fig.update_layout(
        paper_bgcolor="#0d0f14",
        plot_bgcolor="#0d0f14",
        font_color="#94a3b8",
        height=440,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(
            gridcolor="#1a1e2d",
            showgrid=True,
            rangeslider=dict(visible=False),
            color="#475569",
        ),
        yaxis=dict(
            gridcolor="#1a1e2d",
            showgrid=True,
            color="#475569",
            tickprefix="$",
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11, color="#64748b"),
            orientation="h",
            yanchor="bottom",
            y=1.01,
            xanchor="left",
            x=0,
        ),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ─────────────────────────────────────────────
# Uranian Insight Panel
# ─────────────────────────────────────────────

def render_uranian_panel(report: DailyAstroReport) -> None:
    st.markdown('<div class="section-header">⚡ Uranian Insight Panel</div>', unsafe_allow_html=True)

    # Special date banners
    if report.aries_ingress:
        st.markdown(
            """
            <div class="astro-card bullish">
              <strong style="color:#4ade80;">☀️ ARIES INGRESS — Astrological New Year</strong>
              <p style="color:#86efac; margin:6px 0 0 0; font-size:0.88rem;">
                The Sun enters 0° Aries today, beginning the 2026 astrological cycle.
                This chart governs the next 12 months. Jupiter near Uranus in Taurus favors
                continued AI/tech infrastructure expansion.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if report.mercury_direct:
        st.markdown(
            """
            <div class="astro-card" style="border-color:#1e40af; background:#0a0f1e;">
              <strong style="color:#60a5fa;">☿ Mercury Station Direct — ~22° Pisces</strong>
              <p style="color:#93c5fd; margin:6px 0 0 0; font-size:0.88rem;">
                Mercury turns direct today after its retrograde. Historical signal for
                gap-ups in tech, communications, and software names (MSFT, GOOGL, AAPL).
                Watch for increased trading volume in the first 72 hours.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # JU = SU/UR formula evaluation
    for hit in report.active_hits:
        if "JU" in hit.formula:
            card_cls = "warning" if hit.is_active else "astro-card"
            status_color = "#fbbf24" if hit.is_active else "#64748b"
            status_label = f"✅ ACTIVE — Orb {hit.orb:.2f}°" if hit.is_active else "⬜ Inactive"
            mp = hit.midpoint

            st.markdown(
                f"""
                <div class="astro-card warning">
                  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                    <strong style="color:#fbbf24; font-size:1rem;">⚡ JU = SU/UR Formula</strong>
                    <span style="color:{status_color}; font-size:0.8rem; font-weight:700;">{status_label}</span>
                  </div>
                  <p style="color:#fde68a; font-size:0.84rem; margin:0 0 10px 0;">
                    {hit.interpretation}
                  </p>
                  <div style="color:#78716c; font-size:0.78rem; margin-bottom:12px;">
                    Midpoint SU/UR: <span style="color:#d4a853;">{mp.midpoint_sign} {mp.midpoint_sign_degree:.1f}°</span>
                    &nbsp;|&nbsp; Activating: <span style="color:#d4a853;">Jupiter</span>
                    &nbsp;|&nbsp; Aspect: <span style="color:#d4a853;">{hit.aspect:.0f}°</span>
                  </div>
                  <div class="grandpa-quote">🎩 Grandpa Bear says: "{hit.grandpa_bear_quote}"</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Planet positions table
    st.markdown('<div style="margin-top:14px;"></div>', unsafe_allow_html=True)

    with st.expander("🪐 Planet Positions (March 20, 2026)", expanded=False):
        positions = report.planet_positions
        cols = st.columns(2)
        planets_left = ["Sun", "Moon", "Mercury", "Venus", "Mars"]
        planets_right = ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
        for col, planet_list in zip(cols, [planets_left, planets_right]):
            with col:
                for name in planet_list:
                    if name in positions:
                        p = positions[name]
                        col.markdown(
                            f"""
                            <div class="planet-row">
                              <span style="color:#64748b;">{name}</span>
                              <span style="color:#e2e8f0; font-weight:500;">
                                {p.sign} {p.sign_degree:.1f}°
                              </span>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )


# ─────────────────────────────────────────────
# Signal Details + Risk Management
# ─────────────────────────────────────────────

def render_signal_detail(signal: EntrySignal) -> None:
    st.markdown('<div class="section-header">Signal Detail</div>', unsafe_allow_html=True)

    col_signals, col_risk = st.columns([1, 1])

    with col_signals:
        rows = [
            ("EMA 21", f"${signal.ema21:,.2f}", signal.price > signal.ema21),
            ("EMA 50", f"${signal.ema50:,.2f}", signal.price > signal.ema50),
            ("EMA 200", f"${signal.ema200:,.2f}", signal.price > signal.ema200),
            ("MACD", signal.macd_signal.title(), signal.macd_signal == "bullish"),
            ("EMA Alignment", signal.ema_align.title(), signal.ema_align == "bullish stack"),
            ("Pivot Breakout", "Yes ✓" if signal.pivot_break else "No", signal.pivot_break),
            ("Trend Bias", signal.trend.title(), signal.trend == "uptrend"),
        ]
        st.markdown('<div class="astro-card">', unsafe_allow_html=True)
        for label, val, is_positive in rows:
            color = "#4ade80" if is_positive else "#f87171"
            st.markdown(
                f"""
                <div style="display:flex; justify-content:space-between;
                            padding:6px 0; border-bottom:1px solid #1a1e2d;
                            font-size:0.86rem;">
                  <span style="color:#94a3b8;">{label}</span>
                  <span style="color:{color}; font-weight:600;">{val}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with col_risk:
        mid_entry = (signal.entry_low + signal.entry_high) / 2
        risk = calculate_risk_parameters(
            entry_price=mid_entry,
            stop_loss=signal.stop_loss,
            portfolio_value=100_000.0,
        )

        st.markdown(
            f"""
            <div class="astro-card">
              <div style="margin-bottom:14px;">
                <div style="color:#64748b; font-size:0.72rem; letter-spacing:0.08em; text-transform:uppercase;">Entry Zone</div>
                <div style="color:#f1f5f9; font-size:1.4rem; font-weight:700;">${signal.entry_low:,.2f} – ${signal.entry_high:,.2f}</div>
              </div>
              <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:14px;">
                <div>
                  <div style="color:#64748b; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;">Stop Loss</div>
                  <div style="color:#f87171; font-size:1.1rem; font-weight:700;">${signal.stop_loss:,.2f}</div>
                  <div style="color:#78716c; font-size:0.75rem;">{signal.stop_loss_pct*100:.1f}% below entry</div>
                </div>
                <div>
                  <div style="color:#64748b; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;">Risk/Reward</div>
                  <div style="color:#4ade80; font-size:1.1rem; font-weight:700;">1 : {risk.risk_reward:.1f}</div>
                </div>
              </div>
              <div style="border-top:1px solid #1e2538; padding-top:12px; margin-top:4px;">
                <div style="color:#64748b; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:8px;">Position Sizing ($100k Portfolio · 1% Risk)</div>
                <div style="display:flex; justify-content:space-between; font-size:0.85rem; padding:4px 0;">
                  <span style="color:#94a3b8;">Shares to buy</span>
                  <span style="color:#e2e8f0; font-weight:600;">{risk.position_size_shares}</span>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:0.85rem; padding:4px 0;">
                  <span style="color:#94a3b8;">Position value</span>
                  <span style="color:#e2e8f0; font-weight:600;">${risk.position_size_usd:,.0f}</span>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:0.85rem; padding:4px 0;">
                  <span style="color:#94a3b8;">Max loss</span>
                  <span style="color:#f87171; font-weight:600;">${risk.max_loss_usd:,.0f}</span>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Analyst notes
    if signal.notes:
        st.markdown('<div style="margin-top:12px;">', unsafe_allow_html=True)
        for note in signal.notes:
            st.markdown(
                f'<div style="color:#94a3b8; font-size:0.85rem; padding:4px 0;">{note}</div>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# All-Ticker Summary Table
# ─────────────────────────────────────────────

def render_screener_table(signals: list[EntrySignal], class_label: str = "Selected Class") -> None:
    st.markdown(
        f'<div class="section-header">Screener — {class_label}</div>',
        unsafe_allow_html=True,
    )

    header_cols = st.columns([1, 1, 1, 1.2, 1, 1, 1.2])
    headers = ["Ticker", "Price", "RSI", "EMA Align", "Vol Ratio", "MACD", "Signal"]
    for col, h in zip(header_cols, headers):
        col.markdown(
            f'<div style="color:#475569; font-size:0.72rem; font-weight:700; letter-spacing:0.08em; text-transform:uppercase;">{h}</div>',
            unsafe_allow_html=True,
        )

    for sig in signals:
        cols = st.columns([1, 1, 1, 1.2, 1, 1, 1.2])
        pill_cls = f"pill-{sig.signal.replace('_', '-')}"
        signal_label = sig.signal.replace("_", " ").title()
        macd_color = "#4ade80" if sig.macd_signal == "bullish" else "#f87171" if sig.macd_signal == "bearish" else "#94a3b8"
        rsi_color = "#fbbf24" if sig.rsi > 70 or sig.rsi < 30 else "#e2e8f0"

        vals = [
            f'<span style="color:#a78bfa; font-weight:700; font-size:0.9rem;">{sig.ticker}</span>',
            f'<span style="color:#e2e8f0;">${sig.price:,.2f}</span>',
            f'<span style="color:{rsi_color};">{sig.rsi:.1f}</span>',
            f'<span style="color:#e2e8f0; font-size:0.82rem;">{sig.ema_align.title()}</span>',
            f'<span style="color:#e2e8f0;">{sig.volume_ratio:.2f}x</span>',
            f'<span style="color:{macd_color};">{sig.macd_signal.title()}</span>',
            f'<span class="signal-pill {pill_cls}">{signal_label}</span>',
        ]
        for col, val in zip(cols, vals):
            col.markdown(val, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Deep Analysis Prompt Builder
# ─────────────────────────────────────────────

def build_deep_analysis_prompt(signal: EntrySignal, report: DailyAstroReport) -> str:
    """
    Construct the full prompt for Claude's deep trade plan analysis.
    Follows the template in .claude/skills/astro_finance.md.
    """
    ju_hit = next((h for h in report.active_hits if "JU" in h.formula), None)
    ju_status = f"ACTIVE (orb {ju_hit.orb:.2f}°)" if (ju_hit and ju_hit.is_active) else "Inactive"
    active_transits = []
    if report.aries_ingress:
        active_transits.append("Aries Ingress — Sun 0° Aries")
    if report.mercury_direct:
        active_transits.append("Mercury Station Direct ~22° Pisces")
    if ju_hit and ju_hit.is_active:
        active_transits.append(f"JU = SU/UR active (orb {ju_hit.orb:.2f}°)")

    return f"""You are AstroVantage's Deep Analysis engine, combining CAN SLIM technical analysis with Uranian Hamburg School astrology.

**CURRENT TECHNICAL DATA — {signal.ticker}**
- Price: ${signal.price:,.2f}
- RSI (14): {signal.rsi:.1f}
- EMA 21 / 50 / 200: ${signal.ema21:,.2f} / ${signal.ema50:,.2f} / ${signal.ema200:,.2f}
- EMA Alignment: {signal.ema_align}
- MACD: {signal.macd_signal}
- Volume Ratio: {signal.volume_ratio:.2f}x vs 50-day avg
- Overall Signal: {signal.signal}
- Suggested Entry Zone: ${signal.entry_low:,.2f} – ${signal.entry_high:,.2f}
- Stop Loss: ${signal.stop_loss:,.2f} ({signal.stop_loss_pct*100:.1f}% below entry)
- Risk/Reward: ~1:{signal.risk_reward:.1f}

**CURRENT ASTRO CONTEXT — March 20, 2026**
- JU = SU/UR Formula: {ju_status}
- Active Transits: {', '.join(active_transits) if active_transits else 'None'}

**YOUR TASK:**
Write a complete, professional trade plan for {signal.ticker} that includes:
1. **Entry Thesis** — combine the technical + astrological signals into a coherent narrative
2. **Exact Entry** — specific price level and the trigger condition to enter
3. **Stop Loss** — exact price and the rule behind it (max 8% per CAN SLIM)
4. **Three Price Targets** — T1 (pivot R1), T2 (measured move), T3 (stretch target)
5. **Position Sizing** — how many shares to buy given a $100,000 portfolio with 1% risk rule
6. **What Could Go Wrong?** — written as Grandpa Bear, in his plain-spoken voice
7. **30-Day Astrological Outlook** — what transits to watch for this sector through mid-April 2026

Be direct, specific, and professional. No generic disclaimers. Grandpa Bear should sound like himself."""


# ─────────────────────────────────────────────
# Main Application
# ─────────────────────────────────────────────

def main() -> None:
    # ── 1. Sidebar selector — must run before any other st.* call ───────────
    selected_class: AssetClass = render_sidebar()

    # ── 2. Header reflects the active class ─────────────────────────────────
    render_header(selected_class)
    st.markdown("---")

    # ── 3. Astro report — computed once per session ──────────────────────────
    if "astro_report" not in st.session_state:
        with st.spinner("🪐 Calculating planetary positions..."):
            st.session_state["astro_report"] = generate_daily_report()
    report: DailyAstroReport = st.session_state["astro_report"]

    # ── 4. Resolve tickers for the selected class ────────────────────────────
    tickers: list[str] = ASSET_UNIVERSE[selected_class]

    # Invalidate the screener cache whenever the user switches class so stale
    # signals from the previous class don't bleed into the new table.
    if st.session_state.get("_last_class") != selected_class:
        st.session_state.pop("screener_signals", None)
        st.session_state["_last_class"] = selected_class

    # ── 5. Dynamic horizontal tabs — one per ticker in the selected class ────
    # Tab labels use display_name() so "BTC-USD" shows as "BTC",
    # "GC=F" shows as "Gold (GC)", "^GSPC" shows as "S&P 500 (^GSPC)", etc.
    tab_labels = [display_name(t) for t in tickers]
    tabs = st.tabs(tab_labels)

    # ── 6. Per-ticker content ────────────────────────────────────────────────
    for i, ticker in enumerate(tickers):
        with tabs[i]:
            with st.spinner(f"Fetching {display_name(ticker)} data..."):
                df = fetch_ohlcv(ticker, period="6mo", interval="1d")

            if df.empty:
                st.error(
                    f"**{display_name(ticker)}** — no data returned. "
                    "Check your connection or yfinance rate limits."
                )
                continue

            signal = analyze_ticker(ticker, df)
            if signal is None:
                st.warning(
                    f"**{display_name(ticker)}** — insufficient history "
                    "(need ≥50 bars). Try a longer period."
                )
                continue

            # ── Metrics row ─────────────────────────────────────────────────
            render_metric_cards(signal)

            # ── Chart + Uranian panel side by side ──────────────────────────
            chart_col, astro_col = st.columns([3, 2])
            with chart_col:
                render_price_chart(ticker, signal)
            with astro_col:
                render_uranian_panel(report)

            # ── Signal detail + risk card ────────────────────────────────────
            render_signal_detail(signal)

            # ── Screener summary table for the whole selected class ──────────
            st.markdown("---")
            if "screener_signals" not in st.session_state:
                with st.spinner(
                    f"Running screener across all "
                    f"{_CLASS_META[selected_class]['label']} tickers…"
                ):
                    class_data = fetch_asset_class(selected_class, period="6mo")
                    st.session_state["screener_signals"] = screen_all(class_data)

            render_screener_table(
                st.session_state["screener_signals"],
                class_label=_CLASS_META[selected_class]["label"],
            )

            # ── Deep analysis ────────────────────────────────────────────────
            st.markdown("---")
            st.markdown(
                '<div class="section-header">🤖 AI Deep Analysis</div>',
                unsafe_allow_html=True,
            )
            col_btn, col_desc = st.columns([1, 3])
            with col_btn:
                deep_btn = st.button(
                    f"⚡ Analyze {display_name(ticker)}",
                    key=f"deep_{ticker}",
                    help="Generate a full AI trade plan using current technicals + transits",
                )
            with col_desc:
                st.markdown(
                    '<p style="color:#64748b; font-size:0.85rem; padding-top:10px;">'
                    "Generates a structured trade plan: entry thesis, targets, stops, "
                    "position sizing, and Grandpa Bear's risk warnings — all synthesized "
                    "from live data + astro transits."
                    "</p>",
                    unsafe_allow_html=True,
                )

            if deep_btn:
                prompt = build_deep_analysis_prompt(signal, report)
                with st.expander(
                    f"📋 Full Analysis Prompt — {display_name(ticker)}", expanded=True
                ):
                    st.markdown(
                        f'<div class="astro-card"><pre style="color:#94a3b8; '
                        f'font-size:0.78rem; white-space:pre-wrap; '
                        f'font-family:monospace;">{prompt}</pre></div>',
                        unsafe_allow_html=True,
                    )
                    st.info(
                        "💡 Copy this prompt into Claude's chat for a full trade plan, "
                        "or wire up the Anthropic API key in `.env` to auto-generate it here.",
                        icon="ℹ️",
                    )


if __name__ == "__main__":
    main()
