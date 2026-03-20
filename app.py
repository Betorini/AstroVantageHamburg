"""
app.py  —  AstroVantage  (fully responsive edition)
----------------------------------------------------
Gold / Charcoal theme · CAN SLIM · Uranian Hamburg-School astrology

Responsive strategy
-------------------
Streamlit's st.columns() is purely server-side and cannot react to the
browser's viewport width at paint time.  The reliable cross-device solution
is to render the "two-column" sections as a *single* Streamlit column that
contains a self-stacking CSS Grid / Flexbox layout injected via
st.markdown(unsafe_allow_html=True).

Key techniques used:
  • clamp() on all font sizes      — scales smoothly between viewport widths
  • CSS Grid with auto-fit         — chart+astro stack automatically ≤ 820 px
  • overflow-x: auto on table      — screener scrolls horizontally on mobile
  • JS ResizeObserver              — adds a '.mobile' class to the root so
                                     pure-CSS mobile overrides also work
  • @media (max-width: 820px)      — belt-and-suspenders for devices where JS
                                     is delayed

Run:  streamlit run app.py
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
from utils.fetcher import fetch_ohlcv

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# Asset universe
# ─────────────────────────────────────────────────────────────────────────────

# ─── ASSET_UNIVERSE is the single source of truth for all category menus. ───
# The sidebar selectbox reads list(ASSET_UNIVERSE.keys()) directly so adding
# a new category here is all that is needed to expose it in the UI.

ASSET_UNIVERSE: dict[str, list[str]] = {
    "MAG7 & BIG TECH": [
        "AAPL",   # Apple
        "MSFT",   # Microsoft
        "GOOGL",  # Alphabet
        "AMZN",   # Amazon
        "META",   # Meta
        "TSLA",   # Tesla
        "NVDA",   # NVIDIA
        "NFLX",   # Netflix
        "AVGO",   # Broadcom
        "ORCL",   # Oracle
        "ADBE",   # Adobe
        "AMD",    # AMD
    ],
    "CRYPTO CURRENCY": [
        "BTC-USD",   # Bitcoin
        "ETH-USD",   # Ethereum
        "SOL-USD",   # Solana  ← bare "SOL" = wrong stock; -USD suffix is mandatory
        "BNB-USD",   # BNB
        "XRP-USD",   # XRP
        "DOGE-USD",  # Dogecoin
    ],
    "COMMODITIES (GANN)": [
        "GC=F",   # Gold       — COMEX front-month
        "SI=F",   # Silver     — COMEX front-month
        "CL=F",   # Crude Oil  — WTI front-month
        "HG=F",   # Copper     — COMEX front-month
        "NG=F",   # Natural Gas — NYMEX front-month
    ],
}

# Keep APP_UNIVERSE as an alias so the rest of the file, which references
# APP_UNIVERSE throughout, needs zero further changes.
APP_UNIVERSE: dict[str, list[str]] = ASSET_UNIVERSE

CLASS_META: dict[str, dict] = {
    "MAG7 & BIG TECH": {
        "label":       "MAG7 & Big Tech",
        "icon":        "🏆",
        "accent":      "#FFD700",
        "description": "AAPL · MSFT · GOOGL · AMZN · META · TSLA · NVDA + more",
    },
    "CRYPTO CURRENCY": {
        "label":       "Crypto Currency",
        "icon":        "₿",
        "accent":      "#34d399",
        "description": "BTC · ETH · SOL · BNB · XRP · DOGE",
    },
    "COMMODITIES (GANN)": {
        "label":       "Commodities (Gann)",
        "icon":        "🪙",
        "accent":      "#fb923c",
        "description": "Gold · Silver · Crude Oil · Copper · Natural Gas",
    },
}

# ── Friendly display names used in tab labels, screener, and chips ───────────
# Any ticker not in this dict falls back to the raw symbol (equities work fine).
_TICKER_LABELS: dict[str, str] = {
    # Commodities — raw yfinance symbols are cryptic; map to plain English
    "GC=F":    "Gold",
    "SI=F":    "Silver",
    "CL=F":    "Crude Oil",
    "HG=F":    "Copper",
    "NG=F":    "Nat Gas",
    # Crypto — strip the "-USD" suffix for brevity in the UI
    "BTC-USD":  "Bitcoin",
    "ETH-USD":  "Ethereum",
    "SOL-USD":  "Solana",
    "BNB-USD":  "BNB",
    "XRP-USD":  "XRP",
    "DOGE-USD": "Dogecoin",
}


def tlabel(t: str) -> str:
    """Return a human-friendly display name for a raw yfinance ticker symbol."""
    return _TICKER_LABELS.get(t, t)

# ─────────────────────────────────────────────────────────────────────────────
# Page config  (must precede all st.* calls)
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AstroVantage",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Global CSS  — Gold / Charcoal, clamp() typography, responsive grid
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* ── 1. Design tokens ────────────────────────────────────────────────────── */
:root {
    --bg:         #16181c;
    --bg-card:    #1e2028;
    --bg-sidebar: #12141a;
    --bg-alt:     #1a1c22;
    --gold:       #FFD700;
    --gold-dim:   #b8a000;
    --gold-muted: #5a4e00;
    --green:      #22c55e;
    --red:        #ef4444;
    --blue:       #38bdf8;
    --orange:     #fb923c;
    --purple:     #a78bfa;
    --hi:         #f1f5f9;
    --lo:         #94a3b8;
    --border:     #2d3148;
    --radius:     12px;
}

/* ── 2. Global dark background ───────────────────────────────────────────── */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
.main .block-container {
    background: var(--bg) !important;
    color: var(--hi) !important;
    font-family: 'Inter', system-ui, sans-serif;
    /* Remove default side padding on very small viewports */
    padding-left: max(0.5rem, 1vw) !important;
    padding-right: max(0.5rem, 1vw) !important;
}
[data-testid="stHeader"], footer, #MainMenu { display: none !important; }

/* ── 3. Sidebar ──────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: var(--bg-sidebar) !important;
    border-right: 1px solid var(--border);
    padding: 0 0.5rem;
}
[data-testid="stSidebar"] * { color: var(--hi) !important; }
[data-testid="stSidebar"] .stSelectbox > div > div {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    color: var(--hi) !important;
}
[data-testid="stSidebar"] label {
    color: var(--gold) !important;
    font-size: 0.68rem !important;
    font-weight: 800 !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
}

/* ── 4. Buttons ──────────────────────────────────────────────────────────── */
.stButton > button {
    background: linear-gradient(135deg, #7c5c00, #FFD700) !important;
    color: #16181c !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 800 !important;
    /* clamp: shrinks on small screens */
    font-size: clamp(0.72rem, 2vw, 0.88rem) !important;
    padding: 0.6rem 1.2rem !important;
    transition: opacity 0.15s;
    width: 100%;
}
.stButton > button:hover { opacity: 0.82; }

/* ── 5. Metric cards ─────────────────────────────────────────────────────── */
[data-testid="metric-container"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    padding: clamp(10px, 2vw, 18px) clamp(12px, 2.5vw, 20px) !important;
    min-width: 0 !important;       /* critical: prevents overflow in tight grids */
    word-break: break-word;
}
[data-testid="stMetricValue"] {
    color: var(--gold) !important;
    /* clamp: 1.1rem on phone → 1.7rem on desktop */
    font-size: clamp(1.1rem, 3.5vw, 1.7rem) !important;
    font-weight: 700 !important;
    white-space: nowrap;
}
[data-testid="stMetricLabel"] {
    color: var(--lo) !important;
    font-size: clamp(0.58rem, 1.5vw, 0.72rem) !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
}
[data-testid="stMetricDelta"] {
    font-size: clamp(0.62rem, 1.5vw, 0.78rem) !important;
}

/* ── 6. Tabs ─────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] button {
    color: var(--lo) !important;
    font-size: clamp(0.7rem, 1.8vw, 0.84rem) !important;
    font-weight: 500 !important;
    border-radius: 6px 6px 0 0 !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: var(--gold) !important;
    border-bottom: 2px solid var(--gold) !important;
    background: var(--bg-card) !important;
}

/* ── 7. Expanders ────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
}
[data-testid="stExpander"] summary {
    color: var(--gold) !important;
    font-weight: 600 !important;
    font-size: clamp(0.78rem, 2vw, 0.9rem) !important;
}

/* ── 8. Dividers ─────────────────────────────────────────────────────────── */
hr { border-color: var(--border) !important; margin: 1rem 0; }

/* ── 9. Section headings ─────────────────────────────────────────────────── */
.av-head {
    font-size: clamp(0.6rem, 1.5vw, 0.7rem);
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--gold);
    border-bottom: 1px solid var(--gold-muted);
    padding-bottom: 5px;
    margin: 18px 0 10px;
}

/* ── 10. Generic cards ───────────────────────────────────────────────────── */
.av-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: clamp(12px, 2vw, 18px) clamp(14px, 2.5vw, 22px);
    margin-bottom: 10px;
    overflow: hidden;
}
.av-card-gold {
    background: var(--bg-card);
    border: 1px solid var(--gold-muted);
    border-radius: var(--radius);
    padding: clamp(12px, 2vw, 18px) clamp(14px, 2.5vw, 22px);
    margin-bottom: 10px;
}
.av-bull { background:#0a1f0e; border:1px solid #166534; border-radius:var(--radius); padding:12px 16px; margin-bottom:8px; }
.av-info { background:#0a0f1e; border:1px solid #1e40af; border-radius:var(--radius); padding:12px 16px; margin-bottom:8px; }

/* ── 11. Signal pills ────────────────────────────────────────────────────── */
.pill {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: clamp(0.62rem, 1.4vw, 0.72rem);
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    white-space: nowrap;
}
.pill-strong-buy  { background:#166534; color:#4ade80; }
.pill-buy         { background:#14532d; color:#86efac; }
.pill-neutral     { background:#2d3148; color:#94a3b8; }
.pill-sell        { background:#7f1d1d; color:#fca5a5; }
.pill-strong-sell { background:#991b1b; color:#fecaca; }

/* ── 12. Grandpa Bear quote ──────────────────────────────────────────────── */
.gb-quote {
    font-style: italic;
    color: var(--gold);
    font-size: clamp(0.72rem, 1.8vw, 0.82rem);
    line-height: 1.5;
    border-left: 3px solid var(--gold-muted);
    padding-left: 12px;
    margin: 8px 0 0;
}

/* ── 13. Planet position rows ────────────────────────────────────────────── */
.prow {
    display: flex;
    justify-content: space-between;
    padding: 5px 0;
    border-bottom: 1px solid var(--border);
    font-size: clamp(0.7rem, 1.6vw, 0.8rem);
}

/* ── 14. Gann entry rows ─────────────────────────────────────────────────── */
.grow {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 0;
    border-bottom: 1px solid var(--border);
    font-size: clamp(0.75rem, 1.8vw, 0.86rem);
    gap: 8px;
}
.grow span:last-child { text-align: right; }

/* ── 15. Astro formula cards ─────────────────────────────────────────────── */
.af-card {
    background: #1a1520;
    border: 1px solid #3d2e5a;
    border-radius: 10px;
    padding: clamp(10px, 2vw, 14px) clamp(12px, 2.5vw, 18px);
    margin-bottom: 8px;
    break-inside: avoid;
}
.af-card-active { border-color: var(--purple); background: #1a1028; }
.af-label {
    font-size: clamp(0.58rem, 1.4vw, 0.66rem);
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--purple);
    margin-bottom: 5px;
}
.af-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 4px;
    margin-bottom: 5px;
}
.af-name  { color: #e2e8f0; font-size: clamp(0.72rem, 1.8vw, 0.82rem); font-weight: 600; }
.af-status { font-size: clamp(0.62rem, 1.5vw, 0.72rem); font-weight: 700; }
.af-planets { color: #64748b; font-size: clamp(0.64rem, 1.5vw, 0.74rem); margin-bottom: 6px; }
.af-interp  { color: #c4b5fd; font-size: clamp(0.7rem, 1.7vw, 0.8rem); line-height: 1.4; margin-bottom: 6px; }

/* ── 16. Responsive two-column grid (chart | astro) ─────────────────────── */
/*
   auto-fit with a 480px minimum means:
     ≥ 820 px viewport  →  two columns side by side
     < 820 px viewport  →  single column, stacked vertically
   No JavaScript required for this core behaviour.
*/
.av-mid-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 480px), 1fr));
    gap: 1rem;
    align-items: start;
    width: 100%;
}
.av-mid-left  { min-width: 0; }
.av-mid-right { min-width: 0; }

/* ── 17. Responsive metric row ───────────────────────────────────────────── */
/*
   Four metric cards wrap to 2×2 on mobile, stay 4-across on desktop.
   Streamlit's own st.columns() is used for desktop; this rule only matters
   when the viewport shrinks far enough to overflow st.columns().
*/
@media (max-width: 640px) {
    [data-testid="stHorizontalBlock"] > div {
        min-width: 46% !important;
        flex-wrap: wrap !important;
    }
}

/* ── 18. Screener table — scrollable on small screens ────────────────────── */
.sc-wrap {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    border-radius: var(--radius);
    border: 1px solid var(--border);
    margin-top: 6px;
}
.sc-table {
    width: 100%;
    min-width: 560px;          /* triggers horizontal scroll below 560px */
    border-collapse: collapse;
}
.sc-table th {
    background: var(--bg-alt);
    color: var(--gold);
    font-size: clamp(0.58rem, 1.3vw, 0.68rem);
    font-weight: 800;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    padding: 9px 12px;
    text-align: left;
    white-space: nowrap;
    border-bottom: 1px solid var(--gold-muted);
}
.sc-table td {
    padding: 8px 12px;
    font-size: clamp(0.72rem, 1.6vw, 0.82rem);
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
    vertical-align: middle;
}
.sc-table tr:hover td { background: var(--bg-alt); }

/* ── 19. Sidebar ticker chips ────────────────────────────────────────────── */
.sb-chip {
    display: inline-block;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 2px 8px;
    font-size: clamp(0.64rem, 1.5vw, 0.72rem);
    color: var(--lo);
    margin: 2px 3px;
    font-family: monospace;
}

/* ── 20. Signal card in metrics (4th column) ─────────────────────────────── */
.sig-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: clamp(10px, 2vw, 18px) clamp(12px, 2.5vw, 20px);
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: center;
}
.sig-card-label {
    font-size: clamp(0.58rem, 1.4vw, 0.68rem);
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--lo);
    margin-bottom: 8px;
}
</style>
""", unsafe_allow_html=True)

# Inject a JS ResizeObserver so an additional `.mobile` class is toggled on
# the document root — this enables any CSS `.mobile` overrides to fire
# the instant the viewport changes (e.g. rotating an iPad).
st.markdown("""
<script>
(function () {
    function applyMobile() {
        if (window.innerWidth < 820) {
            document.documentElement.classList.add('mobile');
        } else {
            document.documentElement.classList.remove('mobile');
        }
    }
    applyMobile();
    window.addEventListener('resize', applyMobile);
})();
</script>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Safe data helpers  —  try/except guards prevent the "Black Screen of Death"
# ─────────────────────────────────────────────────────────────────────────────

def safe_fetch(ticker: str, period: str = "6mo") -> pd.DataFrame:
    """
    Fetch OHLCV via yfinance.  Returns an empty DataFrame on ANY error so the
    rest of the dashboard continues rendering even if one ticker is broken.
    """
    try:
        df = fetch_ohlcv(ticker, period=period, interval="1d")
        if df is None or df.empty:
            return pd.DataFrame()
        # Normalise index: strip tz-awareness so Plotly arithmetic works
        if hasattr(df.index, "tz") and df.index.tz is not None:
            df = df.copy()
            df.index = df.index.tz_localize(None)
        df.index = pd.to_datetime(df.index)
        return df
    except Exception as exc:
        st.warning(
            f"⚠️ **{tlabel(ticker)}** — data unavailable (`{type(exc).__name__}`). "
            "Skipping.",
            icon="⚠️",
        )
        return pd.DataFrame()


def safe_analyze(ticker: str, df: pd.DataFrame) -> Optional[EntrySignal]:
    """Run the screener pipeline; return None on any exception."""
    try:
        return analyze_ticker(ticker, df)
    except Exception:
        return None


def safe_astro_report() -> Optional[DailyAstroReport]:
    """Compute the daily astrological report; return None on failure."""
    try:
        return generate_daily_report()
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────

def render_sidebar() -> str:
    """
    Render the sidebar and return the selected asset-class key.

    The selectbox options are always derived from list(ASSET_UNIVERSE.keys())
    so adding a new category to ASSET_UNIVERSE automatically exposes it here.
    """
    with st.sidebar:
        st.markdown(
            '<div style="text-align:center;padding:16px 0 20px;">'
            '<div style="font-size:clamp(1.6rem,4vw,2rem);">🔭</div>'
            '<div style="font-size:clamp(1rem,3vw,1.2rem);font-weight:800;color:#FFD700;">'
            "AstroVantage</div>"
            '<div style="font-size:clamp(0.56rem,1.3vw,0.65rem);color:#5a6474;'
            'letter-spacing:0.1em;margin-top:3px;">CANSLIM · URANIAN ASTROLOGY</div>'
            "</div>",
            unsafe_allow_html=True,
        )

        # ── Asset class selectbox ────────────────────────────────────────────
        # Options are read directly from ASSET_UNIVERSE so the menu always
        # reflects the full current universe without any manual sync needed.
        st.markdown(
            '<div style="font-size:0.66rem;font-weight:800;letter-spacing:0.1em;'
            'text-transform:uppercase;color:#FFD700;margin-bottom:6px;">Asset Class</div>',
            unsafe_allow_html=True,
        )
        keys: list[str] = list(ASSET_UNIVERSE.keys())
        labels: list[str] = [
            f"{CLASS_META[k]['icon']}  {CLASS_META[k]['label']}" for k in keys
        ]
        idx: int = st.selectbox(
            "ac",
            options=range(len(keys)),
            format_func=lambda i: labels[i],
            index=0,
            label_visibility="collapsed",
        )
        sel: str = keys[idx]
        meta = CLASS_META[sel]

        st.markdown(
            f'<div style="font-size:0.72rem;color:{meta["accent"]};'
            f'margin:4px 0 10px;line-height:1.5;">{meta["description"]}</div>',
            unsafe_allow_html=True,
        )

        # Ticker chips — flex-wrap handles 12-ticker lists cleanly
        chips = "".join(
            f'<span class="sb-chip">{tlabel(t)}</span>'
            for t in ASSET_UNIVERSE[sel]
        )
        st.markdown(
            f'<div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:14px;">'
            f"{chips}</div>",
            unsafe_allow_html=True,
        )

        # ── Manual Refresh ───────────────────────────────────────────────────
        if st.button("🔄  Manual Refresh", use_container_width=True):
            for k in ("screener_signals", "_last_class", "astro_report"):
                st.session_state.pop(k, None)
            st.cache_data.clear()
            st.rerun()

        # ── Astro status strip ───────────────────────────────────────────────
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown(
            '<div style="font-size:clamp(0.68rem,1.6vw,0.78rem);line-height:2.1;'
            'color:#94a3b8;">'
            '☀️ <span style="color:#FFD700;font-weight:700;">Aries Ingress</span>'
            " — Mar 20 2026<br>"
            '☿ <span style="color:#34d399;font-weight:700;">Mercury Direct</span>'
            " — tech clarity<br>"
            '⚡ <span style="color:#a78bfa;font-weight:700;">JU = SU/UR</span>'
            " — formula live"
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="margin-top:18px;font-size:0.6rem;color:#334155;'
            'text-align:center;">Educational use only. Not financial advice.</div>',
            unsafe_allow_html=True,
        )

    return sel


# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────

def render_header(sel: str) -> None:
    # Use the first key of ASSET_UNIVERSE as the fallback so this line never
    # goes stale when category names change.
    _default_key = next(iter(ASSET_UNIVERSE))
    meta = CLASS_META.get(sel, CLASS_META[_default_key])
    col_l, col_r = st.columns([3, 1])

    with col_l:
        st.markdown(
            '<div style="display:flex;align-items:center;gap:14px;padding:6px 0 4px;">'
            '<div style="font-size:clamp(1.8rem,4vw,2.4rem);">🔭</div>'
            "<div>"
            '<h1 style="margin:0;font-size:clamp(1.4rem,4vw,2rem);font-weight:800;'
            'color:#FFD700;letter-spacing:-0.02em;">AstroVantage</h1>'
            f'<p style="margin:0;color:#5a6474;'
            f'font-size:clamp(0.62rem,1.5vw,0.78rem);letter-spacing:0.06em;">'
            f'{meta["icon"]} {meta["label"].upper()}'
            " &nbsp;·&nbsp; CANSLIM + URANIAN ASTROLOGY</p>"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    with col_r:
        st.markdown(
            '<div style="text-align:right;padding-top:10px;'
            'font-size:clamp(0.62rem,1.5vw,0.76rem);line-height:1.9;">'
            '<div style="color:#FFD700;font-weight:700;">☀️ ARIES INGRESS</div>'
            '<div style="color:#94a3b8;">March 20, 2026</div>'
            '<div style="color:#34d399;font-weight:600;">☿ Mercury Direct</div>'
            "</div>",
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Metric cards  (4 columns; wrap to 2 × 2 on ≤ 640 px via Streamlit columns)
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
        st.metric("Vol Ratio", f"{sig.volume_ratio:.2f}x", delta=vol_note)

    with c4:
        pill_cls = "pill-" + sig.signal.replace("_", "-")
        sig_label = sig.signal.replace("_", " ").title()
        st.markdown(
            f'<div class="sig-card">'
            f'<div class="sig-card-label">Signal</div>'
            f'<span class="pill {pill_cls}" '
            f'style="font-size:clamp(0.72rem,1.8vw,0.84rem);padding:5px 14px;">'
            f"{sig_label}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Candlestick Chart
# ─────────────────────────────────────────────────────────────────────────────

def render_chart(ticker: str, sig: EntrySignal, df: pd.DataFrame) -> None:
    """
    Interactive Plotly candlestick with EMA overlays, entry-zone shading,
    stop-loss line, and Aries Ingress marker.

    All add_vline / add_hline / add_hrect calls are individually guarded with
    try/except — a cosmetic annotation failure never crashes the chart.

    The Aries Ingress x value is always a tz-naive pd.Timestamp (never a bare
    string) to prevent the Plotly "TypeError: int + str" bug.
    """
    st.markdown(
        '<div class="av-head">Price Action · EMA Overlay</div>',
        unsafe_allow_html=True,
    )

    # EMA stack
    ema_stack: dict = {}
    try:
        from core.indicators import get_ema_stack
        ema_stack = get_ema_stack(df)
    except Exception:
        pass

    fig = go.Figure()

    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"], high=df["High"],
            low=df["Low"],   close=df["Close"],
            name=tlabel(ticker),
            increasing_line_color="#22c55e", decreasing_line_color="#ef4444",
            increasing_fillcolor="#166534",  decreasing_fillcolor="#7f1d1d",
            line_width=1,
        )
    )

    for key, lbl, colour, dash in [
        ("ema21",  "EMA 21",  "#34d399", "solid"),
        ("ema50",  "EMA 50",  "#FFD700", "dot"),
        ("ema200", "EMA 200", "#ef4444", "dash"),
    ]:
        s = ema_stack.get(key, pd.Series(dtype=float)).dropna()
        if s.empty:
            continue
        s = s.copy()
        if hasattr(s.index, "tz") and s.index.tz is not None:
            s.index = s.index.tz_localize(None)
        fig.add_trace(
            go.Scatter(x=s.index, y=s.values, name=lbl,
                       line=dict(color=colour, width=1.4, dash=dash), opacity=0.85)
        )

    # Entry zone band
    if sig.entry_low > 0 and sig.entry_high > 0:
        try:
            fig.add_hrect(
                y0=sig.entry_low, y1=sig.entry_high,
                fillcolor="rgba(255,215,0,0.06)",
                line_color="rgba(255,215,0,0.22)", line_width=1,
                annotation_text="Entry Zone", annotation_position="right",
                annotation_font_color="#FFD700", annotation_font_size=10,
            )
        except Exception:
            pass

    # Stop-loss line
    if sig.stop_loss > 0:
        try:
            fig.add_hline(
                y=sig.stop_loss,
                line_color="#ef4444", line_dash="dot", line_width=1.5,
                annotation_text=f"Stop  ${sig.stop_loss:,.2f}",
                annotation_position="right",
                annotation_font_color="#ef4444", annotation_font_size=10,
            )
        except Exception:
            pass

    # Aries Ingress marker — use pd.Timestamp, NOT a plain string
    try:
        aries_ts = pd.Timestamp("2026-03-20")   # tz-naive Timestamp
        df_start, df_end = df.index.min(), df.index.max()
        marker_ts  = aries_ts if df_start <= aries_ts <= df_end else df.index[-1]
        marker_txt = "☀️ Aries Ingress" if df_start <= aries_ts <= df_end \
                     else "☀️ Aries Ingress (Mar 20)"
        fig.add_vline(
            x=marker_ts,
            line_color="#a78bfa", line_dash="dash", line_width=1.5,
            annotation_text=marker_txt, annotation_position="top left",
            annotation_font_color="#a78bfa", annotation_font_size=10,
        )
    except Exception:
        pass

    fig.update_layout(
        paper_bgcolor="#16181c", plot_bgcolor="#16181c", font_color="#94a3b8",
        height=400,
        margin=dict(l=6, r=6, t=24, b=6),
        xaxis=dict(gridcolor="#1e2028", showgrid=True,
                   rangeslider=dict(visible=False), color="#475569"),
        yaxis=dict(gridcolor="#1e2028", showgrid=True,
                   color="#475569", tickprefix="$"),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10, color="#64748b"),
                    orientation="h", yanchor="bottom", y=1.01, x=0),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ─────────────────────────────────────────────────────────────────────────────
# Gann Entry Zone box  (below chart in left column)
# ─────────────────────────────────────────────────────────────────────────────

def render_gann_box(sig: EntrySignal) -> None:
    mid = (sig.entry_low + sig.entry_high) / 2
    try:
        risk = calculate_risk_parameters(
            entry_price=mid, stop_loss=sig.stop_loss, portfolio_value=100_000.0
        )
    except Exception:
        risk = None

    rows = [
        ("Entry Low",        f"${sig.entry_low:,.2f}",                              "#FFD700"),
        ("Entry High",       f"${sig.entry_high:,.2f}",                             "#FFD700"),
        ("Stop Loss",        f"${sig.stop_loss:,.2f}  (−{sig.stop_loss_pct*100:.1f}%)", "#ef4444"),
    ]
    if risk:
        rows += [
            ("Risk / Reward",    f"1 : {risk.risk_reward:.1f}",                     "#22c55e"),
            ("Shares (1% risk)", str(risk.position_size_shares),                    "#f1f5f9"),
            ("Position value",   f"${risk.position_size_usd:,.0f}",                 "#f1f5f9"),
            ("Max loss",         f"${risk.max_loss_usd:,.0f}",                      "#ef4444"),
        ]

    rows_html = "".join(
        f'<div class="grow">'
        f'<span style="color:#94a3b8;flex:1;">{lbl}</span>'
        f'<span style="color:{col};font-weight:600;">{val}</span>'
        f"</div>"
        for lbl, val, col in rows
    )

    st.markdown(
        f'<div class="av-card-gold">'
        f'<div style="font-size:clamp(0.6rem,1.4vw,0.68rem);font-weight:800;'
        f'letter-spacing:0.12em;text-transform:uppercase;color:#FFD700;'
        f'margin-bottom:10px;">⬡ Gann Entry Zone — {tlabel(sig.ticker)}</div>'
        f"{rows_html}"
        f"</div>",
        unsafe_allow_html=True,
    )

    for note in sig.notes:
        st.markdown(
            f'<div style="color:#94a3b8;font-size:clamp(0.7rem,1.6vw,0.8rem);'
            f'padding:3px 0;">{note}</div>',
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Astro Panel  (right column)  — four formula cards
# ─────────────────────────────────────────────────────────────────────────────

def _formula_card(code: str, name: str, planets: str,
                  active: bool, orb: str, interp: str, grandpa: str) -> str:
    """Return the HTML string for a single formula card."""
    cls    = "af-card af-card-active" if active else "af-card"
    sc     = "#a78bfa" if active else "#475569"
    sl     = f"✅ ACTIVE — Orb {orb}" if active else "⬜ Inactive"
    return (
        f'<div class="{cls}">'
        f'<div class="af-label">{code}</div>'
        f'<div class="af-header">'
        f'<span class="af-name">{name}</span>'
        f'<span class="af-status" style="color:{sc};">{sl}</span>'
        f"</div>"
        f'<div class="af-planets">{planets}</div>'
        f'<div class="af-interp">{interp}</div>'
        f'<div class="gb-quote">🎩 "{grandpa}"</div>'
        f"</div>"
    )


def render_astro_panel(report: DailyAstroReport) -> None:
    st.markdown(
        '<div class="av-head">⚡ Uranian Insight Panel</div>',
        unsafe_allow_html=True,
    )

    # Aries Ingress banner
    if report.aries_ingress:
        st.markdown(
            '<div class="av-bull">'
            '<strong style="color:#4ade80;font-size:clamp(0.78rem,2vw,0.9rem);">'
            "☀️ ARIES INGRESS — Astrological New Year</strong>"
            '<p style="color:#86efac;margin:6px 0 0;'
            'font-size:clamp(0.7rem,1.7vw,0.82rem);">'
            "Sun at 0° Aries — 2026 astrological cycle begins. "
            "Jupiter near Uranus in Taurus favours AI &amp; tech "
            "infrastructure expansion through year-end.</p>"
            "</div>",
            unsafe_allow_html=True,
        )

    # Mercury Direct banner
    if report.mercury_direct:
        st.markdown(
            '<div class="av-info">'
            '<strong style="color:#60a5fa;font-size:clamp(0.78rem,2vw,0.9rem);">'
            "☿ Mercury Station Direct — ~22° Pisces</strong>"
            '<p style="color:#93c5fd;margin:6px 0 0;'
            'font-size:clamp(0.7rem,1.7vw,0.82rem);">'
            "Post-retrograde clarity returns to tech &amp; comms. "
            "Watch for gap-ups in MSFT, GOOGL, AAPL within 72 h.</p>"
            "</div>",
            unsafe_allow_html=True,
        )

    # ── Gather planet longitudes ─────────────────────────────────────────────
    positions = report.planet_positions

    def lon(name: str) -> Optional[float]:
        p = positions.get(name)
        return p.longitude if p else None

    sun_l = lon("Sun");    ju_l  = lon("Jupiter"); ur_l = lon("Uranus")
    ve_l  = lon("Venus");  sa_l  = lon("Saturn");  ne_l = lon("Neptune")
    pl_l  = lon("Pluto")

    # JU = SU/UR from the report's pre-computed active_hits
    ju_hit = next((h for h in report.active_hits if "JU" in h.formula), None)

    # Default states for the four formulas
    formulas: list[dict] = [
        {
            "code": "JU = SU/UR", "name": "Jupiter = Sun / Uranus",
            "planets": "☀️ Sun  +  ⚡ Uranus  →  🪐 Jupiter",
            "active": bool(ju_hit and ju_hit.is_active),
            "orb": f"{ju_hit.orb:.2f}°" if ju_hit else "—",
            "interp": (
                "Sudden tech breakthroughs and euphoric rallies. "
                "Historically correlates with gap-up opens in AI names."
            ),
            "grandpa": (
                ju_hit.grandpa_bear_quote if ju_hit
                else "Boy, Jupiter on Uranus is the lottery transit. "
                     "Wins big — loses bigger. Watch your stops."
            ),
        },
        {
            "code": "VE = JU/UR", "name": "Venus = Jupiter / Uranus",
            "planets": "🪐 Jupiter  +  ⚡ Uranus  →  ♀ Venus",
            "active": False, "orb": "—",
            "interp": "Sudden windfall energy. Favours financials, luxury goods, and crypto rallies.",
            "grandpa": (
                "Venus on Jupiter/Uranus? Son, that's the trade "
                "everyone wants. Half of 'em are already in. Be careful."
            ),
        },
        {
            "code": "SA = SU/UR", "name": "Saturn = Sun / Uranus",
            "planets": "☀️ Sun  +  ⚡ Uranus  →  ♄ Saturn",
            "active": False, "orb": "—",
            "interp": "Tech ambitions meet regulatory resistance. Structure disrupted by reality.",
            "grandpa": (
                "Saturn crashing the Sun/Uranus party means the bill "
                "arrives. Tighten those stops, son."
            ),
        },
        {
            "code": "NE = PL/UR", "name": "Neptune = Pluto / Uranus",
            "planets": "♇ Pluto  +  ⚡ Uranus  →  ♆ Neptune",
            "active": False, "orb": "—",
            "interp": (
                "Generational dissolution of old power structures. "
                "Crypto and AI narrative cycles at peak confusion or peak clarity."
            ),
            "grandpa": (
                "Neptune on Pluto/Uranus? Son, that's the kind of transit "
                "that makes people believe they've invented something new. "
                "They haven't. It's still tulips."
            ),
        },
    ]

    # Compute VE=JU/UR, SA=SU/UR, NE=PL/UR live
    try:
        from core.astro_logic import calculate_midpoint, is_hard_aspect

        if ju_l is not None and ur_l is not None:
            ju_ur_mp = calculate_midpoint(ju_l, ur_l)
            if ve_l is not None:
                hit, _, orb_v = is_hard_aspect(ve_l, ju_ur_mp, orb=2.0)
                formulas[1]["active"] = hit
                formulas[1]["orb"]    = f"{orb_v:.2f}°" if hit else "—"

        if sun_l is not None and ur_l is not None:
            su_ur_mp = calculate_midpoint(sun_l, ur_l)
            if sa_l is not None:
                hit, _, orb_v = is_hard_aspect(sa_l, su_ur_mp, orb=2.0)
                formulas[2]["active"] = hit
                formulas[2]["orb"]    = f"{orb_v:.2f}°" if hit else "—"

        if pl_l is not None and ur_l is not None:
            pl_ur_mp = calculate_midpoint(pl_l, ur_l)
            if ne_l is not None:
                hit, _, orb_v = is_hard_aspect(ne_l, pl_ur_mp, orb=2.0)
                formulas[3]["active"] = hit
                formulas[3]["orb"]    = f"{orb_v:.2f}°" if hit else "—"
    except Exception:
        pass  # Non-fatal: formula cards still render with default state

    # Render formula cards
    for f in formulas:
        st.markdown(
            _formula_card(
                f["code"], f["name"], f["planets"],
                f["active"], f["orb"], f["interp"], f["grandpa"],
            ),
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
# Screener table  — overflow-x: auto makes it scroll on small screens
# ─────────────────────────────────────────────────────────────────────────────

def render_screener(signals: list[EntrySignal], class_label: str) -> None:
    st.markdown(
        f'<div class="av-head">Screener — {class_label}</div>',
        unsafe_allow_html=True,
    )

    # Table header
    thead = (
        "<thead><tr>"
        "<th>Ticker</th><th>Price</th><th>RSI</th>"
        "<th>EMA Align</th><th>Vol Ratio</th><th>MACD</th><th>Signal</th>"
        "</tr></thead>"
    )

    # Table rows
    rows_html = ""
    for sig in signals:
        pill_cls = "pill-" + sig.signal.replace("_", "-")
        sig_txt  = sig.signal.replace("_", " ").title()

        rsi_c  = "#fbbf24" if (sig.rsi > 70 or sig.rsi < 30) else "#f1f5f9"
        macd_c = (
            "#22c55e" if sig.macd_signal == "bullish"
            else "#ef4444" if sig.macd_signal == "bearish"
            else "#94a3b8"
        )
        vol_c = "#22c55e" if sig.volume_ratio >= 1.5 else "#f1f5f9"

        rows_html += (
            "<tr>"
            f'<td style="color:#FFD700;font-weight:700;">{tlabel(sig.ticker)}</td>'
            f'<td style="color:#f1f5f9;">${sig.price:,.2f}</td>'
            f'<td style="color:{rsi_c};">{sig.rsi:.1f}</td>'
            f'<td style="color:#f1f5f9;font-size:0.76rem;">{sig.ema_align.title()}</td>'
            f'<td style="color:{vol_c};">{sig.volume_ratio:.2f}x</td>'
            f'<td style="color:{macd_c};">{sig.macd_signal.title()}</td>'
            f'<td><span class="pill {pill_cls}">{sig_txt}</span></td>'
            "</tr>"
        )

    st.markdown(
        f'<div class="sc-wrap">'
        f'<table class="sc-table">{thead}<tbody>{rows_html}</tbody></table>'
        f"</div>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    # 1. Sidebar (first widget call — required by Streamlit)
    sel = render_sidebar()

    # 2. Header
    render_header(sel)
    st.markdown("<hr>", unsafe_allow_html=True)

    # 3. Astro report — cached for the session
    if "astro_report" not in st.session_state:
        with st.spinner("🪐 Calculating planetary positions…"):
            st.session_state["astro_report"] = safe_astro_report()
    report: Optional[DailyAstroReport] = st.session_state.get("astro_report")

    # 4. Tickers for the selected class; clear screener cache on class switch
    tickers = APP_UNIVERSE[sel]
    if st.session_state.get("_last_class") != sel:
        st.session_state.pop("screener_signals", None)
        st.session_state["_last_class"] = sel

    # 5. Dynamic tabs — friendly display names as tab labels
    tabs = st.tabs([tlabel(t) for t in tickers])

    # 6. Per-ticker content
    for i, ticker in enumerate(tickers):
        with tabs[i]:
            # Data fetch
            with st.spinner(f"Fetching {tlabel(ticker)}…"):
                df = safe_fetch(ticker)

            if df.empty:
                st.error(
                    f"**{tlabel(ticker)}** — no market data returned. "
                    "Check connection or yfinance rate limits. "
                    "Use **🔄 Manual Refresh** in the sidebar to retry."
                )
                continue

            sig = safe_analyze(ticker, df)
            if sig is None:
                st.warning(
                    f"**{tlabel(ticker)}** — insufficient history "
                    "(need ≥ 50 bars). Try a longer lookback period."
                )
                continue

            # ── Metric cards ─────────────────────────────────────────────────
            render_metrics(sig)

            # ── Middle section: responsive two-column grid ───────────────────
            # We use a CSS Grid div rather than st.columns() so that the layout
            # truly responds to the viewport width.  The `auto-fit` column rule
            # ensures the chart and astro panel each take a minimum of 480px;
            # when the viewport cannot fit two such columns they stack vertically.
            st.markdown(
                "<div class='av-mid-grid'>",
                unsafe_allow_html=True,
            )

            # Left cell — chart + Gann box
            st.markdown(
                "<div class='av-mid-left'>",
                unsafe_allow_html=True,
            )
            render_chart(ticker, sig, df)
            render_gann_box(sig)
            st.markdown("</div>", unsafe_allow_html=True)

            # Right cell — astro panel
            st.markdown(
                "<div class='av-mid-right'>",
                unsafe_allow_html=True,
            )
            if report is not None:
                render_astro_panel(report)
            else:
                st.info(
                    "Astro engine offline — install `ephem` to enable "
                    "Uranian formula calculations.",
                    icon="🪐",
                )
            st.markdown("</div>", unsafe_allow_html=True)

            # Close the grid wrapper
            st.markdown("</div>", unsafe_allow_html=True)

            # ── Full-width screener table ─────────────────────────────────────
            st.markdown("<hr>", unsafe_allow_html=True)
            if "screener_signals" not in st.session_state:
                with st.spinner(
                    f"Running screener across {CLASS_META[sel]['label']}…"
                ):
                    class_data = {t: safe_fetch(t) for t in tickers}
                    st.session_state["screener_signals"] = screen_all(class_data)

            render_screener(
                st.session_state["screener_signals"],
                class_label=CLASS_META[sel]["label"],
            )

            # ── Deep analysis prompt ──────────────────────────────────────────
            st.markdown("<hr>", unsafe_allow_html=True)
            st.markdown(
                '<div class="av-head">🤖 AI Deep Analysis</div>',
                unsafe_allow_html=True,
            )
            btn_col, desc_col = st.columns([1, 3])
            with btn_col:
                do_analysis = st.button(
                    f"⚡ Analyze {tlabel(ticker)}", key=f"deep_{ticker}"
                )
            with desc_col:
                st.markdown(
                    '<p style="color:#64748b;font-size:clamp(0.7rem,1.7vw,0.82rem);'
                    'padding-top:8px;">'
                    "Full trade plan: entry thesis, T1/T2/T3 targets, stop rules, "
                    "position sizing, and Grandpa Bear risk warnings.</p>",
                    unsafe_allow_html=True,
                )

            if do_analysis:
                ju_hit = (
                    next(
                        (h for h in report.active_hits if "JU" in h.formula), None
                    ) if report else None
                )
                ju_status = (
                    f"ACTIVE (orb {ju_hit.orb:.2f}°)"
                    if (ju_hit and ju_hit.is_active) else "Inactive"
                )
                transits: list[str] = []
                if report and report.aries_ingress:
                    transits.append("Aries Ingress — Sun 0° Aries")
                if report and report.mercury_direct:
                    transits.append("Mercury Station Direct ~22° Pisces")
                if ju_hit and ju_hit.is_active:
                    transits.append(f"JU = SU/UR active (orb {ju_hit.orb:.2f}°)")

                prompt = (
                    f"You are AstroVantage's Deep Analysis engine — "
                    f"CAN SLIM + Uranian Hamburg School astrology.\n\n"
                    f"**TECHNICALS — {tlabel(ticker)}**\n"
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
                    f"4. Three targets: T1 (Pivot R1), T2 (measured move), T3 (stretch)\n"
                    f"5. Position sizing for $100k portfolio at 1% risk\n"
                    f"6. Grandpa Bear 'What could go wrong?' section\n"
                    f"7. 30-day astrological outlook for this sector"
                )

                with st.expander(
                    f"📋 Analysis Prompt — {tlabel(ticker)}", expanded=True
                ):
                    st.markdown(
                        f'<div class="av-card">'
                        f'<pre style="color:#94a3b8;font-size:clamp(0.66rem,1.5vw,0.76rem);'
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
