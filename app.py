"""
app.py
------
AstroVantage — Streamlit Dashboard
Bright-Gold / Charcoal theme combining CAN SLIM technical screening
with Uranian Hamburg School financial astrology.

Run: streamlit run app.py
"""

from __future__ import annotations

from typing import Optional

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
    fetch_ohlcv,
    get_volume_ratio,
)

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# Asset Universe  (app-level — self-contained, no fetcher dependency for layout)
# ─────────────────────────────────────────────────────────────────────────────

APP_UNIVERSE: dict[str, list[str]] = {
    "MAG7": [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA",
    ],
    "CRYPTO": [
        "BTC-USD", "ETH-USD", "SOL-USD",
    ],
    "COMMODITIES": [
        "GC=F",    # Gold
        "SI=F",    # Silver
        "CL=F",    # Crude Oil
    ],
}

CLASS_META: dict[str, dict] = {
    "MAG7": {
        "label": "Magnificent Seven",
        "icon": "🏆",
        "accent": "#FFD700",
        "description": "Large-cap AI & tech leaders",
    },
    "CRYPTO": {
        "label": "Cryptocurrencies",
        "icon": "₿",
        "accent": "#34d399",
        "description": "BTC · ETH · SOL",
    },
    "COMMODITIES": {
        "label": "Commodities",
        "icon": "🪙",
        "accent": "#fb923c",
        "description": "Gold · Silver · Crude Oil",
    },
}

TICKER_LABELS: dict[str, str] = {
    "GC=F":    "Gold",
    "SI=F":    "Silver",
    "CL=F":    "Crude Oil",
    "BTC-USD": "BTC",
    "ETH-USD": "ETH",
    "SOL-USD": "SOL",
}


def ticker_label(t: str) -> str:
    """Return a human-friendly display name for a raw yfinance ticker."""
    return TICKER_LABELS.get(t, t)


# ─────────────────────────────────────────────────────────────────────────────
# Page config  (must be the first Streamlit call in the file)
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AstroVantage",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Global CSS — Bright Gold / Charcoal theme
# ─────────────────────────────────────────────────────────────────────────────

st.markdown(
    """
<style>
:root {
    --bg-main:      #16181c;
    --bg-card:      #1e2028;
    --bg-sidebar:   #12141a;
    --bg-alt:       #1a1c22;
    --gold:         #FFD700;
    --gold-dim:     #b8a000;
    --gold-muted:   #5a4e00;
    --green:        #22c55e;
    --red:          #ef4444;
    --blue:         #38bdf8;
    --orange:       #fb923c;
    --purple:       #a78bfa;
    --text-hi:      #f1f5f9;
    --text-lo:      #94a3b8;
    --border:       #2d3148;
}

html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
.main .block-container {
    background-color: var(--bg-main) !important;
    color: var(--text-hi) !important;
    font-family: 'Inter', 'SF Pro Display', system-ui, sans-serif;
}

[data-testid="stHeader"], footer, #MainMenu { display:none !important; }

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: var(--bg-sidebar) !important;
    border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] * { color: var(--text-hi) !important; }
[data-testid="stSidebar"] .stSelectbox > div > div {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
}
[data-testid="stSidebar"] label {
    color: var(--gold) !important;
    font-size: 0.7rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #7c5c00, #FFD700) !important;
    color: #16181c !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    font-size: 0.84rem !important;
    letter-spacing: 0.04em !important;
    padding: 10px 20px !important;
    transition: opacity 0.15s;
}
.stButton > button:hover { opacity: 0.85; }

/* Metric cards */
[data-testid="metric-container"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    padding: 18px 20px !important;
}
[data-testid="stMetricValue"] {
    color: var(--gold) !important;
    font-size: 1.6rem !important;
    font-weight: 700 !important;
}
[data-testid="stMetricLabel"] {
    color: var(--text-lo) !important;
    font-size: 0.68rem !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
}
[data-testid="stMetricDelta"] { font-size: 0.78rem !important; }

/* Tabs */
[data-testid="stTabs"] button {
    color: var(--text-lo) !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    border-radius: 6px 6px 0 0 !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: var(--gold) !important;
    border-bottom: 2px solid var(--gold) !important;
    background: var(--bg-card) !important;
}

/* Expanders */
[data-testid="stExpander"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
}
[data-testid="stExpander"] summary { color: var(--gold) !important; font-weight:600 !important; }

hr { border-color: var(--border) !important; margin: 1rem 0; }

/* Section heading */
.av-head {
    font-size: 0.66rem; font-weight: 800; letter-spacing: 0.12em;
    text-transform: uppercase; color: var(--gold);
    border-bottom: 1px solid var(--gold-muted);
    padding-bottom: 5px; margin: 20px 0 12px 0;
}

/* Cards */
.av-card {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 12px; padding: 16px 20px; margin-bottom: 10px;
}
.av-card-gold {
    background: var(--bg-card); border: 1px solid var(--gold-muted);
    border-radius: 12px; padding: 16px 20px; margin-bottom: 10px;
}
.av-bull { background:#0a1f0e; border:1px solid #166534; border-radius:12px; padding:14px 18px; margin-bottom:8px; }
.av-bear { background:#1f0a0a; border:1px solid #7f1d1d; border-radius:12px; padding:14px 18px; margin-bottom:8px; }
.av-warn { background:#1f150a; border:1px solid #854d0e; border-radius:12px; padding:14px 18px; margin-bottom:8px; }
.av-info { background:#0a0f1e; border:1px solid #1e40af; border-radius:12px; padding:14px 18px; margin-bottom:8px; }

/* Signal pills */
.pill {
    display:inline-block; padding:3px 11px; border-radius:20px;
    font-size:0.7rem; font-weight:700; letter-spacing:0.05em; text-transform:uppercase;
}
.pill-strong-buy  { background:#166534; color:#4ade80; }
.pill-buy         { background:#14532d; color:#86efac; }
.pill-neutral     { background:#2d3148; color:#94a3b8; }
.pill-sell        { background:#7f1d1d; color:#fca5a5; }
.pill-strong-sell { background:#991b1b; color:#fecaca; }

/* Grandpa Bear quote */
.gb-quote {
    font-style:italic; color:var(--gold); font-size:0.8rem; line-height:1.5;
    border-left:3px solid var(--gold-muted); padding-left:12px; margin:8px 0;
}

/* Planet row */
.prow {
    display:flex; justify-content:space-between; padding:5px 0;
    border-bottom:1px solid var(--border); font-size:0.78rem;
}

/* Gann row */
.grow {
    display:flex; justify-content:space-between; align-items:center;
    padding:6px 0; border-bottom:1px solid var(--border); font-size:0.84rem;
}

/* Screener grid (7 columns) */
.sc-grid {
    display:grid;
    grid-template-columns: 1.1fr 1fr 0.8fr 1.2fr 0.9fr 0.9fr 1.1fr;
    gap:6px; align-items:center;
}
.sc-head {
    font-size:0.66rem; font-weight:800; letter-spacing:0.08em;
    text-transform:uppercase; color:var(--gold);
    border-bottom:1px solid var(--gold-muted);
    padding:0 0 6px 0; margin-bottom:4px;
}
.sc-row {
    font-size:0.82rem; padding:7px 0;
    border-bottom:1px solid var(--border);
}
.sc-row:hover { background:var(--bg-alt); }

/* Sidebar chips */
.sb-chip {
    display:inline-block; background:var(--bg-card);
    border:1px solid var(--border); border-radius:6px;
    padding:2px 8px; font-size:0.7rem; color:var(--text-lo);
    margin:2px 3px; font-family:monospace;
}

/* Astro formula card */
.af-card {
    background:#1a1520; border:1px solid #3d2e5a;
    border-radius:10px; padding:12px 16px; margin-bottom:8px;
}
.af-card-active { border-color:var(--purple); background:#1a1028; }
.af-label {
    font-size:0.65rem; font-weight:800; letter-spacing:0.12em;
    text-transform:uppercase; color:var(--purple); margin-bottom:6px;
}
</style>
""",
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────

def render_sidebar() -> str:
    """Render the sidebar and return the selected asset class key."""
    with st.sidebar:
        st.markdown(
            """
            <div style="text-align:center;padding:16px 0 20px;">
              <div style="font-size:2rem;">🔭</div>
              <div style="font-size:1.15rem;font-weight:800;color:#FFD700;
                          letter-spacing:-0.01em;">AstroVantage</div>
              <div style="font-size:0.62rem;color:#5a6474;
                          letter-spacing:0.1em;margin-top:3px;">
                CANSLIM · URANIAN ASTROLOGY
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Asset class selector
        st.markdown(
            '<div style="font-size:0.66rem;font-weight:800;letter-spacing:0.1em;'
            'text-transform:uppercase;color:#FFD700;margin-bottom:6px;">'
            "Asset Class</div>",
            unsafe_allow_html=True,
        )
        class_keys = list(APP_UNIVERSE.keys())
        class_display = [
            f"{CLASS_META[k]['icon']}  {CLASS_META[k]['label']}"
            for k in class_keys
        ]
        idx: int = st.selectbox(
            label="ac_select",
            options=range(len(class_keys)),
            format_func=lambda i: class_display[i],
            index=0,
            label_visibility="collapsed",
        )
        sel: str = class_keys[idx]
        meta = CLASS_META[sel]

        st.markdown(
            f'<div style="font-size:0.76rem;color:{meta["accent"]};'
            f'margin:4px 0 10px;">{meta["description"]}</div>',
            unsafe_allow_html=True,
        )

        chips = "".join(
            f'<span class="sb-chip">{ticker_label(t)}</span>'
            for t in APP_UNIVERSE[sel]
        )
        st.markdown(
            f'<div style="line-height:2.2;margin-bottom:14px;">{chips}</div>',
            unsafe_allow_html=True,
        )

        # Manual Refresh button
        st.markdown("<div style='margin-top:6px;'></div>", unsafe_allow_html=True)
        if st.button("🔄  Manual Refresh", use_container_width=True):
            for key in ("screener_signals", "_last_class", "astro_report"):
                st.session_state.pop(key, None)
            st.cache_data.clear()
            st.rerun()

        # Astro status strip
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown(
            """
            <div style="font-size:0.76rem;line-height:2.1;color:#94a3b8;">
              ☀️ <span style="color:#FFD700;font-weight:700;">Aries Ingress</span>
                 — Mar 20 2026<br>
              ☿ <span style="color:#34d399;font-weight:700;">Mercury Direct</span>
                 — tech clarity<br>
              ⚡ <span style="color:#a78bfa;font-weight:700;">JU = SU/UR</span>
                 — formula live
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div style='margin-top:18px;font-size:0.6rem;color:#334155;"
            "text-align:center;'>Educational use only. Not financial advice.</div>",
            unsafe_allow_html=True,
        )

    return sel


# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────

def render_header(sel: str) -> None:
    meta = CLASS_META.get(sel, CLASS_META["MAG7"])
    col_l, col_r = st.columns([3, 1])
    with col_l:
        st.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:14px;padding:6px 0 4px;">
              <div style="font-size:2.4rem;">🔭</div>
              <div>
                <h1 style="margin:0;font-size:2rem;font-weight:800;
                            color:#FFD700;letter-spacing:-0.02em;">
                  AstroVantage
                </h1>
                <p style="margin:0;color:#5a6474;font-size:0.76rem;
                           letter-spacing:0.06em;">
                  {meta["icon"]} {meta["label"].upper()}
                  &nbsp;·&nbsp; CANSLIM + URANIAN ASTROLOGY
                </p>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_r:
        st.markdown(
            """
            <div style="text-align:right;padding-top:10px;
                        font-size:0.74rem;line-height:1.9;">
              <div style="color:#FFD700;font-weight:700;">☀️ ARIES INGRESS</div>
              <div style="color:#94a3b8;">March 20, 2026</div>
              <div style="color:#34d399;font-weight:600;">☿ Mercury Direct</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Metric Cards (4 columns)
# ─────────────────────────────────────────────────────────────────────────────

def render_metrics(sig: EntrySignal) -> None:
    st.markdown('<div class="av-head">Live Metrics</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("Price", f"${sig.price:,.2f}")

    with c2:
        rsi_note = (
            "Overbought ⚠️" if sig.rsi > 70
            else "Oversold 🟢" if sig.rsi < 30
            else "Healthy ✓"
        )
        st.metric("RSI (14)", f"{sig.rsi:.1f}", delta=rsi_note)

    with c3:
        vol_note = "Heavy 🔥" if sig.volume_ratio >= 1.5 else "Normal"
        st.metric("Volume Ratio", f"{sig.volume_ratio:.2f}x", delta=vol_note)

    with c4:
        pill_cls = "pill-" + sig.signal.replace("_", "-")
        sig_label = sig.signal.replace("_", " ").title()
        st.markdown(
            f"""
            <div style="background:#1e2028;border:1px solid #2d3148;
                        border-radius:12px;padding:18px 20px;">
              <div style="font-size:0.66rem;font-weight:700;letter-spacing:0.1em;
                          text-transform:uppercase;color:#94a3b8;margin-bottom:8px;">
                Signal
              </div>
              <span class="pill {pill_cls}" style="font-size:0.84rem;padding:5px 16px;">
                {sig_label}
              </span>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Candlestick Chart
# ─────────────────────────────────────────────────────────────────────────────

def render_chart(ticker: str, sig: EntrySignal, df: pd.DataFrame) -> None:
    """
    Plotly candlestick with EMA overlays, entry-zone shading, stop line,
    and Aries Ingress marker. All add_vline / add_hline / add_hrect calls
    are individually guarded with try/except to prevent cosmetic failures
    from crashing the chart.

    The x value for add_vline is always a tz-naive pd.Timestamp — never a
    bare string — to avoid the Plotly TypeError: int + str bug.
    """
    st.markdown(
        '<div class="av-head">Price Action · EMA Overlay</div>',
        unsafe_allow_html=True,
    )

    # Normalise index: strip tz-awareness so Plotly arithmetic works
    df = df.copy()
    if hasattr(df.index, "tz") and df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df.index = pd.to_datetime(df.index)

    # EMA stack
    ema_stack: dict = {}
    try:
        from core.indicators import get_ema_stack
        ema_stack = get_ema_stack(df)
    except Exception:
        pass

    fig = go.Figure()

    # Candlesticks
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name=ticker_label(ticker),
            increasing_line_color="#22c55e",
            decreasing_line_color="#ef4444",
            increasing_fillcolor="#166534",
            decreasing_fillcolor="#7f1d1d",
            line_width=1,
        )
    )

    # EMA lines
    ema_specs = [
        ("ema21",  "EMA 21",  "#34d399", "solid"),
        ("ema50",  "EMA 50",  "#FFD700", "dot"),
        ("ema200", "EMA 200", "#ef4444", "dash"),
    ]
    for key, lbl, colour, dash in ema_specs:
        series = ema_stack.get(key, pd.Series(dtype=float)).dropna()
        if series.empty:
            continue
        s = series.copy()
        if hasattr(s.index, "tz") and s.index.tz is not None:
            s.index = s.index.tz_localize(None)
        fig.add_trace(
            go.Scatter(
                x=s.index,
                y=s.values,
                name=lbl,
                line=dict(color=colour, width=1.4, dash=dash),
                opacity=0.85,
            )
        )

    # Entry zone band
    if sig.entry_low > 0 and sig.entry_high > 0:
        try:
            fig.add_hrect(
                y0=sig.entry_low,
                y1=sig.entry_high,
                fillcolor="rgba(255,215,0,0.07)",
                line_color="rgba(255,215,0,0.25)",
                line_width=1,
                annotation_text="Entry Zone",
                annotation_position="right",
                annotation_font_color="#FFD700",
                annotation_font_size=10,
            )
        except Exception:
            pass

    # Stop-loss line
    if sig.stop_loss > 0:
        try:
            fig.add_hline(
                y=sig.stop_loss,
                line_color="#ef4444",
                line_dash="dot",
                line_width=1.5,
                annotation_text=f"Stop  ${sig.stop_loss:,.2f}",
                annotation_position="right",
                annotation_font_color="#ef4444",
                annotation_font_size=10,
            )
        except Exception:
            pass

    # Aries Ingress vertical marker
    # x MUST be a tz-naive pd.Timestamp — not a string — to avoid the
    # TypeError: unsupported operand type(s) for +: 'int' and 'str'
    # that occurs when Plotly tries to compute annotation offsets.
    try:
        aries_ts = pd.Timestamp("2026-03-20")       # tz-naive Timestamp
        df_start = df.index.min()
        df_end = df.index.max()

        if df_start <= aries_ts <= df_end:
            marker_ts = aries_ts
            marker_lbl = "☀️ Aries Ingress"
        else:
            # Ingress date outside visible range — anchor to last bar
            marker_ts = df.index[-1]
            marker_lbl = "☀️ Aries Ingress (Mar 20)"

        fig.add_vline(
            x=marker_ts,
            line_color="#a78bfa",
            line_dash="dash",
            line_width=1.5,
            annotation_text=marker_lbl,
            annotation_position="top left",
            annotation_font_color="#a78bfa",
            annotation_font_size=10,
        )
    except Exception:
        pass

    fig.update_layout(
        paper_bgcolor="#16181c",
        plot_bgcolor="#16181c",
        font_color="#94a3b8",
        height=420,
        margin=dict(l=8, r=8, t=28, b=8),
        xaxis=dict(
            gridcolor="#1e2028",
            showgrid=True,
            rangeslider=dict(visible=False),
            color="#475569",
        ),
        yaxis=dict(
            gridcolor="#1e2028",
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


# ─────────────────────────────────────────────────────────────────────────────
# Gann Entry Zone Box  (below chart, left column)
# ─────────────────────────────────────────────────────────────────────────────

def render_gann_box(sig: EntrySignal) -> None:
    mid = (sig.entry_low + sig.entry_high) / 2
    risk = calculate_risk_parameters(
        entry_price=mid,
        stop_loss=sig.stop_loss,
        portfolio_value=100_000.0,
    )

    rows = [
        ("Entry Low",        f"${sig.entry_low:,.2f}",                       "#FFD700"),
        ("Entry High",       f"${sig.entry_high:,.2f}",                      "#FFD700"),
        ("Stop Loss",        f"${sig.stop_loss:,.2f}  (−{sig.stop_loss_pct*100:.1f}%)", "#ef4444"),
        ("Risk / Reward",    f"1 : {risk.risk_reward:.1f}",                  "#22c55e"),
        ("Shares (1% risk)", str(risk.position_size_shares),                 "#f1f5f9"),
        ("Position value",   f"${risk.position_size_usd:,.0f}",              "#f1f5f9"),
        ("Max loss",         f"${risk.max_loss_usd:,.0f}",                   "#ef4444"),
    ]

    rows_html = "".join(
        f'<div class="grow">'
        f'<span style="color:#94a3b8;">{lbl}</span>'
        f'<span style="color:{col};font-weight:600;">{val}</span>'
        f"</div>"
        for lbl, val, col in rows
    )

    st.markdown(
        f"""
        <div class="av-card-gold">
          <div style="font-size:0.66rem;font-weight:800;letter-spacing:0.12em;
                      text-transform:uppercase;color:#FFD700;margin-bottom:10px;">
            ⬡ Gann Entry Zone — {ticker_label(sig.ticker)}
          </div>
          {rows_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    for note in sig.notes:
        st.markdown(
            f'<div style="color:#94a3b8;font-size:0.8rem;padding:3px 0;">{note}</div>',
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Uranian / Financial Astrology Panel  (right column)
# ─────────────────────────────────────────────────────────────────────────────

def render_astro_panel(report: DailyAstroReport) -> None:
    st.markdown(
        '<div class="av-head">⚡ Uranian Insight Panel</div>',
        unsafe_allow_html=True,
    )

    # Aries Ingress banner
    if report.aries_ingress:
        st.markdown(
            """
            <div class="av-bull">
              <strong style="color:#4ade80;font-size:0.88rem;">
                ☀️ ARIES INGRESS — Astrological New Year
              </strong>
              <p style="color:#86efac;margin:6px 0 0;font-size:0.8rem;">
                Sun at 0° Aries — 2026 astrological cycle begins.
                Jupiter near Uranus in Taurus favours AI &amp; tech
                infrastructure expansion through year-end.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Mercury Direct banner
    if report.mercury_direct:
        st.markdown(
            """
            <div class="av-info">
              <strong style="color:#60a5fa;font-size:0.88rem;">
                ☿ Mercury Station Direct — ~22° Pisces
              </strong>
              <p style="color:#93c5fd;margin:6px 0 0;font-size:0.8rem;">
                Post-retrograde clarity returns to tech &amp; comms.
                Watch for gap-ups in MSFT, GOOGL, AAPL within 72 h.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Three formula cards: JU=SU/UR, VE=JU/UR, SA=SU/UR ──────────────────
    positions = report.planet_positions

    def lon(name: str) -> Optional[float]:
        p = positions.get(name)
        return p.longitude if p else None

    sun_l = lon("Sun")
    ju_l  = lon("Jupiter")
    ur_l  = lon("Uranus")
    ve_l  = lon("Venus")
    sa_l  = lon("Saturn")

    # Pull JU=SU/UR result from report
    ju_hit = next((h for h in report.active_hits if "JU" in h.formula), None)

    formulas = [
        {
            "code":    "JU = SU/UR",
            "name":    "Jupiter = Sun / Uranus",
            "planets": "☀️ Sun  +  ⚡ Uranus  →  🪐 Jupiter",
            "active":  bool(ju_hit and ju_hit.is_active),
            "orb":     f"{ju_hit.orb:.2f}°" if ju_hit else "—",
            "interp":  (
                "Sudden tech breakthroughs, euphoric rallies. "
                "Gap-up opens and momentum surges in AI names."
            ),
            "grandpa": (
                ju_hit.grandpa_bear_quote if ju_hit
                else "Boy, Jupiter on Uranus is the lottery ticket transit. "
                     "Wins big — loses bigger. Watch your stops."
            ),
        },
        {
            "code":    "VE = JU/UR",
            "name":    "Venus = Jupiter / Uranus",
            "planets": "🪐 Jupiter  +  ⚡ Uranus  →  ♀ Venus",
            "active":  False,
            "orb":     "—",
            "interp":  (
                "Sudden windfall energy. Favours financials, luxury goods, "
                "and speculative crypto rallies."
            ),
            "grandpa": (
                "Venus on Jupiter/Uranus? Son, that's the trade everyone "
                "wants. Which means half are already in. Be careful."
            ),
        },
        {
            "code":    "SA = SU/UR",
            "name":    "Saturn = Sun / Uranus",
            "planets": "☀️ Sun  +  ⚡ Uranus  →  ♄ Saturn",
            "active":  False,
            "orb":     "—",
            "interp":  (
                "Tech ambitions meet regulatory or economic resistance. "
                "Structural disruption slowed by reality."
            ),
            "grandpa": (
                "Saturn crashing the Sun/Uranus party means the bill "
                "arrives. Tighten those stops, son."
            ),
        },
    ]

    # Compute VE=JU/UR and SA=SU/UR live
    try:
        from core.astro_logic import calculate_midpoint, is_hard_aspect

        if ju_l is not None and ur_l is not None:
            ju_ur_mp = calculate_midpoint(ju_l, ur_l)
            if ve_l is not None:
                ve_hit, _, ve_orb = is_hard_aspect(ve_l, ju_ur_mp, orb=2.0)
                formulas[1]["active"] = ve_hit
                formulas[1]["orb"] = f"{ve_orb:.2f}°" if ve_hit else "—"

        if sun_l is not None and ur_l is not None:
            su_ur_mp = calculate_midpoint(sun_l, ur_l)
            if sa_l is not None:
                sa_hit, _, sa_orb = is_hard_aspect(sa_l, su_ur_mp, orb=2.0)
                formulas[2]["active"] = sa_hit
                formulas[2]["orb"] = f"{sa_orb:.2f}°" if sa_hit else "—"
    except Exception:
        pass

    for f in formulas:
        card_cls = "af-card af-card-active" if f["active"] else "af-card"
        sc = "#a78bfa" if f["active"] else "#475569"
        sl = f"✅ ACTIVE — Orb {f['orb']}" if f["active"] else "⬜ Inactive"

        st.markdown(
            f"""
            <div class="{card_cls}">
              <div class="af-label">{f["code"]}</div>
              <div style="display:flex;justify-content:space-between;
                          align-items:center;margin-bottom:5px;">
                <span style="color:#e2e8f0;font-size:0.8rem;font-weight:600;">
                  {f["name"]}
                </span>
                <span style="color:{sc};font-size:0.7rem;font-weight:700;">
                  {sl}
                </span>
              </div>
              <div style="color:#64748b;font-size:0.72rem;margin-bottom:7px;">
                {f["planets"]}
              </div>
              <div style="color:#c4b5fd;font-size:0.78rem;margin-bottom:7px;
                          line-height:1.4;">
                {f["interp"]}
              </div>
              <div class="gb-quote">🎩 "{f["grandpa"]}"</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Planet positions expander
    with st.expander("🪐 Planet Positions — Mar 20 2026", expanded=False):
        left_pl  = ["Sun", "Moon", "Mercury", "Venus", "Mars"]
        right_pl = ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
        pc1, pc2 = st.columns(2)
        for col, plist in [(pc1, left_pl), (pc2, right_pl)]:
            with col:
                for name in plist:
                    p = report.planet_positions.get(name)
                    if p:
                        col.markdown(
                            f'<div class="prow">'
                            f'<span style="color:#64748b;">{name}</span>'
                            f'<span style="color:#e2e8f0;font-weight:500;">'
                            f"{p.sign} {p.sign_degree:.1f}°</span>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )


# ─────────────────────────────────────────────────────────────────────────────
# Full-width Screener Table
# ─────────────────────────────────────────────────────────────────────────────

def render_screener(signals: list[EntrySignal], class_label: str) -> None:
    st.markdown(
        f'<div class="av-head">Screener — {class_label}</div>',
        unsafe_allow_html=True,
    )

    headers = ["Ticker", "Price", "RSI", "EMA Align", "Vol Ratio", "MACD", "Signal"]
    hcells = "".join(f"<span>{h}</span>" for h in headers)
    st.markdown(
        f'<div class="sc-grid sc-head">{hcells}</div>',
        unsafe_allow_html=True,
    )

    for sig in signals:
        pill_cls = "pill-" + sig.signal.replace("_", "-")
        sig_txt = sig.signal.replace("_", " ").title()

        rsi_c = "#fbbf24" if (sig.rsi > 70 or sig.rsi < 30) else "#f1f5f9"
        macd_c = (
            "#22c55e" if sig.macd_signal == "bullish"
            else "#ef4444" if sig.macd_signal == "bearish"
            else "#94a3b8"
        )
        vol_c = "#22c55e" if sig.volume_ratio >= 1.5 else "#f1f5f9"

        cells = [
            f'<span style="color:#FFD700;font-weight:700;">{ticker_label(sig.ticker)}</span>',
            f'<span style="color:#f1f5f9;">${sig.price:,.2f}</span>',
            f'<span style="color:{rsi_c};">{sig.rsi:.1f}</span>',
            f'<span style="color:#f1f5f9;font-size:0.76rem;">{sig.ema_align.title()}</span>',
            f'<span style="color:{vol_c};">{sig.volume_ratio:.2f}x</span>',
            f'<span style="color:{macd_c};">{sig.macd_signal.title()}</span>',
            f'<span class="pill {pill_cls}">{sig_txt}</span>',
        ]
        row_html = "".join(f"<span>{c}</span>" for c in cells)
        st.markdown(
            f'<div class="sc-grid sc-row">{row_html}</div>',
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Safe data helpers  (try/except to prevent black-screen crashes)
# ─────────────────────────────────────────────────────────────────────────────

def safe_fetch(ticker: str, period: str = "6mo") -> pd.DataFrame:
    """
    Fetch OHLCV for one ticker. Returns an empty DataFrame on any error.
    This is the primary guard against network / yfinance failures causing
    a blank white or black screen.
    """
    try:
        df = fetch_ohlcv(ticker, period=period, interval="1d")
        return df if (df is not None and not df.empty) else pd.DataFrame()
    except Exception as exc:
        st.warning(
            f"⚠️ **{ticker_label(ticker)}** — data fetch failed "
            f"(`{type(exc).__name__}`). Skipping.",
            icon="⚠️",
        )
        return pd.DataFrame()


def safe_analyze(ticker: str, df: pd.DataFrame) -> Optional[EntrySignal]:
    """Run analyze_ticker inside try/except — analysis errors are non-fatal."""
    try:
        return analyze_ticker(ticker, df)
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    # 1. Sidebar must be the very first widget call
    sel = render_sidebar()

    # 2. Header
    render_header(sel)
    st.markdown("<hr>", unsafe_allow_html=True)

    # 3. Astro report — computed once per session
    if "astro_report" not in st.session_state:
        with st.spinner("🪐 Calculating planetary positions…"):
            try:
                st.session_state["astro_report"] = generate_daily_report()
            except Exception as exc:
                st.error(f"Astro engine error: {exc}")
                st.session_state["astro_report"] = None

    report: Optional[DailyAstroReport] = st.session_state.get("astro_report")

    # 4. Resolve tickers; invalidate screener cache on class switch
    tickers = APP_UNIVERSE[sel]
    if st.session_state.get("_last_class") != sel:
        st.session_state.pop("screener_signals", None)
        st.session_state["_last_class"] = sel

    # 5. Dynamic ticker tabs
    tabs = st.tabs([ticker_label(t) for t in tickers])

    # 6. Per-ticker content
    for i, ticker in enumerate(tickers):
        with tabs[i]:
            with st.spinner(f"Fetching {ticker_label(ticker)}…"):
                df = safe_fetch(ticker)

            if df.empty:
                st.error(
                    f"**{ticker_label(ticker)}** — no market data returned. "
                    "Check your connection or yfinance rate limits. "
                    "Use **🔄 Manual Refresh** in the sidebar to retry."
                )
                continue

            sig = safe_analyze(ticker, df)
            if sig is None:
                st.warning(
                    f"**{ticker_label(ticker)}** — insufficient history "
                    "(need ≥ 50 bars). Try a longer period."
                )
                continue

            # 4-column metrics row
            render_metrics(sig)

            # Middle: chart (left) + astro panel (right)
            st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)
            col_l, col_r = st.columns([3, 2], gap="medium")

            with col_l:
                render_chart(ticker, sig, df)
                render_gann_box(sig)

            with col_r:
                if report is not None:
                    render_astro_panel(report)
                else:
                    st.info(
                        "Astro engine offline — install `ephem` to enable "
                        "Uranian formula calculations.",
                        icon="🪐",
                    )

            # Full-width screener table
            st.markdown("<hr>", unsafe_allow_html=True)
            if "screener_signals" not in st.session_state:
                with st.spinner(
                    f"Running screener across {CLASS_META[sel]['label']}…"
                ):
                    class_data: dict[str, pd.DataFrame] = {
                        t: safe_fetch(t) for t in tickers
                    }
                    st.session_state["screener_signals"] = screen_all(class_data)

            render_screener(
                st.session_state["screener_signals"],
                class_label=CLASS_META[sel]["label"],
            )

            # Deep analysis prompt builder
            st.markdown("<hr>", unsafe_allow_html=True)
            st.markdown(
                '<div class="av-head">🤖 AI Deep Analysis</div>',
                unsafe_allow_html=True,
            )
            btn_col, desc_col = st.columns([1, 3])
            with btn_col:
                do_analysis = st.button(
                    f"⚡ Analyze {ticker_label(ticker)}",
                    key=f"deep_{ticker}",
                )
            with desc_col:
                st.markdown(
                    '<p style="color:#64748b;font-size:0.82rem;padding-top:8px;">'
                    "Full trade plan: entry thesis, T1/T2/T3 targets, stop rules, "
                    "position sizing, and Grandpa Bear risk warnings."
                    "</p>",
                    unsafe_allow_html=True,
                )

            if do_analysis and report is not None:
                ju_hit = next(
                    (h for h in report.active_hits if "JU" in h.formula), None
                )
                ju_status = (
                    f"ACTIVE (orb {ju_hit.orb:.2f}°)"
                    if (ju_hit and ju_hit.is_active)
                    else "Inactive"
                )
                transits = []
                if report.aries_ingress:
                    transits.append("Aries Ingress — Sun 0° Aries")
                if report.mercury_direct:
                    transits.append("Mercury Station Direct ~22° Pisces")
                if ju_hit and ju_hit.is_active:
                    transits.append(f"JU = SU/UR active (orb {ju_hit.orb:.2f}°)")

                prompt = (
                    f"You are AstroVantage's Deep Analysis engine — "
                    f"CAN SLIM + Uranian Hamburg School astrology.\n\n"
                    f"**TECHNICALS — {ticker_label(ticker)}**\n"
                    f"- Price: ${sig.price:,.2f}\n"
                    f"- RSI: {sig.rsi:.1f}  |  MACD: {sig.macd_signal}\n"
                    f"- EMA 21/50/200: "
                    f"${sig.ema21:,.2f} / ${sig.ema50:,.2f} / ${sig.ema200:,.2f}\n"
                    f"- EMA Alignment: {sig.ema_align}\n"
                    f"- Volume Ratio: {sig.volume_ratio:.2f}x\n"
                    f"- Signal: {sig.signal}\n"
                    f"- Entry Zone: ${sig.entry_low:,.2f} – ${sig.entry_high:,.2f}\n"
                    f"- Stop Loss: ${sig.stop_loss:,.2f} "
                    f"(−{sig.stop_loss_pct*100:.1f}%)\n\n"
                    f"**ASTRO — March 20, 2026**\n"
                    f"- JU = SU/UR: {ju_status}\n"
                    f"- Active transits: "
                    f"{', '.join(transits) if transits else 'None'}\n\n"
                    f"**TASK — write a complete trade plan:**\n"
                    f"1. Entry thesis (technical + astro combined)\n"
                    f"2. Exact entry trigger and price\n"
                    f"3. Stop-loss rule (max 8% — CAN SLIM)\n"
                    f"4. Three targets: T1 (Pivot R1), T2 (measured move), "
                    f"T3 (stretch)\n"
                    f"5. Position sizing for $100k portfolio at 1% risk\n"
                    f"6. Grandpa Bear 'What could go wrong?' section\n"
                    f"7. 30-day astrological outlook for this sector"
                )

                with st.expander(
                    f"📋 Analysis Prompt — {ticker_label(ticker)}", expanded=True
                ):
                    st.markdown(
                        f'<div class="av-card">'
                        f'<pre style="color:#94a3b8;font-size:0.74rem;'
                        f'white-space:pre-wrap;font-family:monospace;">'
                        f"{prompt}</pre></div>",
                        unsafe_allow_html=True,
                    )
                    st.info(
                        "💡 Copy this prompt into Claude for a full trade plan, "
                        "or add `ANTHROPIC_API_KEY` to `.env` to auto-generate here.",
                        icon="ℹ️",
                    )


if __name__ == "__main__":
    main()
