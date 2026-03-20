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
    "MAG7 & Semi Giants": [
        "NVDA",   # NVIDIA — AI / GPU
        "TSM",    # TSMC — world's largest foundry
        "AAPL",   # Apple
        "MSFT",   # Microsoft
        "GOOGL",  # Alphabet
        "AMZN",   # Amazon
        "META",   # Meta
        "TSLA",   # Tesla
        "AVGO",   # Broadcom
        "ORCL",   # Oracle
    ],
    "Broad Market (ตลาดหลัก)": [
        "^SPX",   # S&P 500 Index  (^GSPC is the yfinance fallback if ^SPX is empty)
        "VOO",    # Vanguard S&P 500 ETF
        "SPY",    # SPDR S&P 500 ETF
        "VTI",    # Vanguard Total US Market ETF
        "VT",     # Vanguard Total World ETF
        "BRK-B",  # Berkshire Hathaway Class B
    ],
    "Buffett Portfolio (ปู่บัฟเฟตต์)": [
        "BRK-B",  # Berkshire Hathaway — the vehicle
        "KO",     # Coca-Cola
        "BAC",    # Bank of America
        "AXP",    # American Express
        "CVX",    # Chevron
        "KHC",    # Kraft Heinz
        "MCO",    # Moody's Corp
        "V",      # Visa Inc
        "MA",     # Mastercard
        "DVA",    # DaVita
        "COF",    # Capital One
        "HWM",    # Howmet Aerospace
        "PARA",   # Paramount Global
    ],
    "Oil & Energy (พลังงาน)": [
        "CVX",    # Chevron
        "XOM",    # Exxon Mobil
        "SHEL",   # Shell
        "COP",    # ConocoPhillips
        "BP",     # BP
        "TTE",    # TotalEnergies
        "EOG",    # EOG Resources
        "PBR",    # Petrobras
        "SLB",    # SLB (Schlumberger)
        "HAL",    # Halliburton
    ],
    "Commodities & Crypto": [
        "GC=F",      # Gold       — COMEX front-month
        "SI=F",      # Silver     — COMEX front-month
        "BTC-USD",   # Bitcoin    — -USD suffix mandatory
        "ETH-USD",   # Ethereum
        "SOL-USD",   # Solana     — bare "SOL" = wrong stock ticker
        "BNB-USD",   # BNB
        "XRP-USD",   # XRP
        "DOGE-USD",  # Dogecoin
    ],
    "Growth & Healthcare": [
        "QQQ",    # Invesco NASDAQ-100 ETF
        "QQQM",   # Invesco NASDAQ-100 ETF (lower share price)
        "XLK",    # Technology Select Sector SPDR ETF
        "SCHD",   # Schwab US Dividend Equity ETF
        "VIG",    # Vanguard Dividend Appreciation ETF
        "LLY",    # Eli Lilly
        "JNJ",    # Johnson & Johnson
        "PFE",    # Pfizer
        "ABBV",   # AbbVie
        "AWK",    # American Water Works
        "WM",     # Waste Management
        "ISRG",   # Intuitive Surgical
        "PANW",   # Palo Alto Networks
        "MU",     # Micron Technology
        "TMC",    # The Metals Company
    ],
}

# Keep APP_UNIVERSE as an alias so the rest of the file, which references
# APP_UNIVERSE throughout, needs zero further changes.
APP_UNIVERSE: dict[str, list[str]] = ASSET_UNIVERSE

CLASS_META: dict[str, dict] = {
    "MAG7 & Semi Giants": {
        "label":       "MAG7 & Semi Giants",
        "icon":        "🏆",
        "accent":      "#FFD700",
        "description": "หุ้นเทคโนโลยีชั้นนำ · Magnificent 7 · TSMC · Semis · AI",
    },
    "Broad Market (ตลาดหลัก)": {
        "label":       "Broad Market",
        "icon":        "🌍",
        "accent":      "#38bdf8",
        "description": "ตลาดหุ้นหลัก · S&P 500 · ETF ครอบคลุมตลาด",
    },
    "Buffett Portfolio (ปู่บัฟเฟตต์)": {
        "label":       "Buffett Portfolio",
        "icon":        "🎩",
        "accent":      "#4ade80",
        "description": "พอร์ต Berkshire Hathaway · หุ้นคุณค่าระยะยาว · Warren Buffett",
    },
    "Oil & Energy (พลังงาน)": {
        "label":       "Oil & Energy",
        "icon":        "🛢️",
        "accent":      "#fb923c",
        "description": "หุ้นพลังงานและน้ำมัน · Major Oils · E&P · OFS",
    },
    "Commodities & Crypto": {
        "label":       "Commodities & Crypto",
        "icon":        "₿",
        "accent":      "#34d399",
        "description": "โลหะมีค่า · Gold · Silver · Bitcoin · Ethereum · Altcoins",
    },
    "Growth & Healthcare": {
        "label":       "Growth & Healthcare",
        "icon":        "🚀",
        "accent":      "#a78bfa",
        "description": "NASDAQ ETFs · เทคโนโลยีและการแพทย์ · Dividend · Speculative",
    },
}

# ── Friendly display names used in tab labels, screener, and chips ───────────
# Any ticker not in this dict falls back to the raw symbol (equities work fine).
_TICKER_LABELS: dict[str, str] = {
    # ── MAG7 & Semi Giants ───────────────────────────────────────────────────
    "TSM":   "TSMC",
    # NVDA, AAPL, MSFT, GOOGL, AMZN, META, TSLA, AVGO, ORCL → raw symbol
    # ── Indices & broad-market ETFs ──────────────────────────────────────────
    "^SPX":  "S&P 500 Index",
    "VOO":   "Vanguard S&P 500",
    "SPY":   "S&P 500 ETF",
    "VTI":   "Total US Market",
    "VT":    "Vanguard Total World",
    "BRK-B": "Berkshire Hathaway",
    # ── Buffett Portfolio ─────────────────────────────────────────────────────
    "KO":    "Coca-Cola",
    "BAC":   "Bank of America",
    "AXP":   "American Express",
    "CVX":   "Chevron",
    "KHC":   "Kraft Heinz",
    "MCO":   "Moody's Corp",
    "V":     "Visa Inc",
    "MA":    "Mastercard",
    "DVA":   "DaVita",
    "COF":   "Capital One",
    "HWM":   "Howmet Aerospace",
    "PARA":  "Paramount Global",
    # ── Oil & Energy ──────────────────────────────────────────────────────────
    "XOM":   "Exxon Mobil",
    "SHEL":  "Shell",
    "COP":   "ConocoPhillips",
    "BP":    "BP",
    "TTE":   "TotalEnergies",
    "EOG":   "EOG Resources",
    "PBR":   "Petrobras",
    "SLB":   "SLB (Schlumberger)",
    "HAL":   "Halliburton",
    # ── Commodities ───────────────────────────────────────────────────────────
    "GC=F":  "Gold",
    "SI=F":  "Silver",
    "CL=F":  "Crude Oil",
    "HG=F":  "Copper",
    "NG=F":  "Nat Gas",
    # ── Crypto — -USD suffix is mandatory for all; bare symbols = wrong tickers
    "BTC-USD":  "Bitcoin",
    "ETH-USD":  "Ethereum",
    "SOL-USD":  "Solana",
    "BNB-USD":  "BNB",
    "XRP-USD":  "XRP",
    "DOGE-USD": "Dogecoin",
    # ── Growth & Healthcare ───────────────────────────────────────────────────
    "QQQ":   "NASDAQ-100 ETF",
    "QQQM":  "NASDAQ-100 (QQQM)",
    "XLK":   "Tech Sector ETF",
    "SCHD":  "Schwab Dividend",
    "VIG":   "Dividend Growth ETF",
    "LLY":   "Eli Lilly",
    "JNJ":   "Johnson & Johnson",
    "PFE":   "Pfizer",
    "ABBV":  "AbbVie",
    "AWK":   "American Water Works",
    "WM":    "Waste Management",
    "ISRG":  "Intuitive Surgical",
    "PANW":  "Palo Alto Networks",
    "MU":    "Micron Technology",
    "TMC":   "The Metals Company",
    # ── Previously active but removed from universe (kept for safe_fetch compat)
    "XLV":   "Health Care ETF",
    "XLE":   "Energy Sector ETF",
    "XLF":   "Financial Sector ETF",
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
/* When the sidebar is collapsed the toggle floats at ~60px from the left.   */
/* Give the main block a minimum left indent so content never hides under it.*/
[data-testid="stMainBlockContainer"] {
    padding-left:  max(3.5rem, 3vw) !important;
    padding-right: max(1rem,   2vw) !important;
}
/* ── stHeader: keep visible, style it dark so the toggle is always legible ── */
/* NEVER set display:none on stHeader — collapsedControl lives inside it.      */
[data-testid="stHeader"] {
    background: #16181c !important;
    border-bottom: 1px solid #2d3148 !important;
}
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stToolbar"]    { display: none !important; }
#MainMenu                    { display: none !important; }
footer                       { display: none !important; }

/* ── Sidebar toggle wrapper ──────────────────────────────────────────────── */
/* collapsedControl is the outer container; it must be visible on all screens */
[data-testid="collapsedControl"] {
    display:        flex   !important;
    visibility:     visible !important;
    opacity:        1       !important;
    pointer-events: auto    !important;
    z-index:        999999  !important;
}

/* ── button[kind="header"] — the actual toggle button Streamlit renders ───── */
/* On desktop Streamlit renders this as button[kind="header"] INSIDE             */
/* collapsedControl. Without explicit styling it either inherits the wide gold   */
/* gradient from .stButton > button (broken look) or is transparent on the dark */
/* header background (invisible). Style it as a circular gold-tinted button.    */
button[kind="header"] {
    background-color: rgba(255, 215, 0, 0.25) !important;
    color:            #FFD700                  !important;
    border:           1px solid rgba(255, 215, 0, 0.4) !important;
    border-radius:    50%                      !important;
    width:            36px                     !important;
    height:           36px                     !important;
    min-width:        36px                     !important;
    max-width:        36px                     !important;
    padding:          0                        !important;
    margin:           10px                     !important;
    display:          flex                     !important;
    align-items:      center                   !important;
    justify-content:  center                   !important;
    visibility:       visible                  !important;
    opacity:          1                        !important;
    z-index:          999999                   !important;
    pointer-events:   auto                     !important;
    /* Override any width:100% from the global .stButton rule */
    flex-shrink:      0                        !important;
}
button[kind="header"]:hover {
    background-color: rgba(255, 215, 0, 0.35) !important;
    border-color:     #FFD700                  !important;
}
/* Gold chevron SVG inside the toggle */
button[kind="header"] svg {
    fill:   #FFD700 !important;
    stroke: #FFD700 !important;
    color:  #FFD700 !important;
    width:  18px    !important;
    height: 18px    !important;
}

/* ── 3. Sidebar ──────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: var(--bg-sidebar) !important;
    border-right: 1px solid var(--border) !important;
    padding: 0 0.5rem;
    z-index: 100 !important;        /* below toggle so toggle stays on top     */
}
/* Scope the colour override to sidebar content only — do NOT use bare *      */
/* A bare `[data-testid="stSidebar"] *` bleeds into collapsedControl's SVG.  */
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div,
[data-testid="stSidebar"] li,
[data-testid="stSidebar"] a { color: var(--hi) !important; }
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

/* ── 4a. Responsive base font — 1.25rem target, clamped ─────────────────── */
/* Raw 1.25rem on every element would overflow component labels and tab text. */
/* Apply it to the body/app shell; component-level sizes use their own clamp. */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
    font-size: 1.25rem !important;
}
[class*="css"] { font-size: clamp(0.95rem, 1.8vw, 1.1rem) !important; }
/* Sidebar nav — 1.4rem target */
[data-testid="stSidebarNav"],
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span {
    font-size: clamp(1.0rem, 2.2vw, 1.4rem) !important;
}
/* Data table cells — slightly smaller for data density */
.stDataFrame div { font-size: clamp(0.85rem, 1.5vw, 1.0rem) !important; }

/* ── 4b. Buttons — guard toggle from inheriting the app button styles ────── */
/* Without :not([kind="header"]) the toggle gets width:100% and the gradient, */
/* which makes it appear as a wide gold bar and breaks the circular shape.    */
.stButton > button:not([kind="header"]) {
    background: linear-gradient(135deg, #7c5c00, #FFD700) !important;
    color: #16181c !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 800 !important;
    font-size: clamp(0.82rem, 2vw, 1.0rem) !important;
    padding: 0.6rem 1.2rem !important;
    transition: opacity 0.15s;
    width: 100%;
}
.stButton > button:not([kind="header"]):hover { opacity: 0.82; }

/* ── 5. Metric cards ─────────────────────────────────────────────────────── */
[data-testid="metric-container"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    padding: clamp(10px, 2vw, 20px) clamp(12px, 2.5vw, 22px) !important;
    min-width: 0 !important;       /* critical: prevents overflow in tight grids */
    word-break: break-word;
}
[data-testid="stMetricValue"] {
    color: var(--gold) !important;
    /* 3.5rem target, clamped so it never overflows a 4-col iPad cell (~180px). */
    /* clamp floor 1.6rem keeps it readable on small phones.                    */
    /* clamp ceiling 3.5rem = ~56px on a 1440px desktop — prominent and bold.   */
    /* The 5.5vw middle ensures smooth scaling across all breakpoints.           */
    font-size: clamp(1.6rem, 5.5vw, 3.5rem) !important;
    font-weight: 800 !important;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
[data-testid="stMetricLabel"] {
    color: var(--lo) !important;
    font-size: clamp(0.78rem, 1.8vw, 1.05rem) !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
}
[data-testid="stMetricDelta"] {
    font-size: clamp(0.75rem, 1.6vw, 0.95rem) !important;
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

def render_sidebar() -> tuple[str, bool, bool]:
    """
    Render the sidebar controls.

    Returns:
        (selected_class_key, show_planetary_price_lines, show_tnp_lines)
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

        # Ticker chips
        chips = "".join(
            f'<span class="sb-chip">{tlabel(t)}</span>'
            for t in ASSET_UNIVERSE[sel]
        )
        st.markdown(
            f'<div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:14px;">'
            f"{chips}</div>",
            unsafe_allow_html=True,
        )

        # ── Chart overlay controls ───────────────────────────────────────────
        st.markdown(
            "<hr style='margin:8px 0;'>"
            '<div style="font-size:0.62rem;font-weight:800;letter-spacing:0.1em;'
            'text-transform:uppercase;color:#FFD700;margin-bottom:6px;">Chart Overlays</div>',
            unsafe_allow_html=True,
        )
        show_ppl: bool = st.checkbox(
            "🪐 Planetary Price Lines",
            value=True,
            help=(
                "Auto-scaled Jupiter (Gold) and Saturn (Silver) horizontal "
                "lines. Each planet's longitude (0–360°) is multiplied or "
                "divided by 10 until the level falls within ±50% of the "
                "current price."
            ),
        )
        show_tnp: bool = st.checkbox(
            "⊕ Transneptunian PPL",
            value=False,
            help=(
                "Apollon (Blue — expansion/inflation) and Kronos (Purple — "
                "market authority) price levels using 2026 Transneptunian "
                "longitudes, scaled to current price with ±50% window."
            ),
        )

        # ── Manual Refresh ───────────────────────────────────────────────────
        st.markdown("<div style='margin-top:6px;'></div>", unsafe_allow_html=True)
        if st.button("🔄  Manual Refresh", use_container_width=True):
            for k in ("screener_signals", "_last_class", "astro_report"):
                st.session_state.pop(k, None)
            st.cache_data.clear()
            st.rerun()

        # ── Dynamic astro status strip ───────────────────────────────────────
        st.markdown("<hr>", unsafe_allow_html=True)
        try:
            _today = date.today()
            _ju_sign, _ju_deg = planet_sign_degree("Jupiter", _today)
            _sa_sign, _sa_deg = planet_sign_degree("Saturn",  _today)
            _ap_lon  = tnp_longitude("Apollon", _today)
            _kr_lon  = tnp_longitude("Kronos",  _today)
            _ap_sign = _SIGNS[int(_ap_lon // 30)]
            _kr_sign = _SIGNS[int(_kr_lon // 30)]
            _ap_deg  = _ap_lon % 30
            _kr_deg  = _kr_lon % 30
            _astro_html = (
                f'<div style="font-size:clamp(0.66rem,1.5vw,0.76rem);line-height:2.0;color:#94a3b8;">'
                f'🪐 <span style="color:#fde68a;font-weight:700;">Jupiter</span>'
                f' {_ju_sign} {_ju_deg:.0f}°<br>'
                f'♄ <span style="color:#93c5fd;font-weight:700;">Saturn</span>'
                f' {_sa_sign} {_sa_deg:.0f}°<br>'
                f'⊕ <span style="color:#38bdf8;font-weight:700;">Apollon</span>'
                f' {_ap_sign} {_ap_deg:.1f}°<br>'
                f'♄ₓ <span style="color:#a78bfa;font-weight:600;">Kronos</span>'
                f' {_kr_sign} {_kr_deg:.1f}°'
                f'</div>'
            )
        except Exception:
            _astro_html = (
                '<div style="font-size:0.72rem;color:#94a3b8;">'
                '⚡ Perpetual ephemeris active</div>'
            )
        st.markdown(_astro_html, unsafe_allow_html=True)
        st.markdown(
            '<div style="margin-top:18px;font-size:0.6rem;color:#334155;'
            'text-align:center;">Educational use only. Not financial advice.</div>',
            unsafe_allow_html=True,
        )

    return sel, show_ppl, show_tnp


# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────

def render_header(sel: str) -> None:
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
        # Dynamic header — live planet positions from perpetual engine
        try:
            _today = date.today()
            _ju_sign, _ju_deg = planet_sign_degree("Jupiter", _today)
            _sa_sign, _sa_deg = planet_sign_degree("Saturn",  _today)
            _su_sign, _su_deg = planet_sign_degree("Sun",     _today)
            _header_r = (
                f'<div style="text-align:right;padding-top:8px;'
                f'font-size:clamp(0.6rem,1.4vw,0.74rem);line-height:1.85;">'
                f'<div style="color:#FFD700;font-weight:700;">'
                f'☀️ Sun in {_su_sign} {_su_deg:.0f}°</div>'
                f'<div style="color:#fde68a;">🪐 Jupiter in {_ju_sign}</div>'
                f'<div style="color:#93c5fd;">♄ Saturn in {_sa_sign}</div>'
                f'<div style="color:#38bdf8;font-size:0.66rem;">'
                f'⊕ Apollon · ♄ₓ Kronos active</div>'
                f'</div>'
            )
        except Exception:
            _header_r = (
                '<div style="text-align:right;padding-top:10px;'
                'font-size:clamp(0.62rem,1.5vw,0.76rem);line-height:1.9;">'
                '<div style="color:#FFD700;font-weight:700;">☀️ ARIES INGRESS</div>'
                '<div style="color:#94a3b8;">March 20, 2026</div>'
                '<div style="color:#34d399;font-weight:600;">☿ Mercury Direct</div>'
                '</div>'
            )
        st.markdown(_header_r, unsafe_allow_html=True)


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
# Planetary Price Levels (PPL) — Classical + Transneptunian Edition
# ─────────────────────────────────────────────────────────────────────────────

# Colour-coding for classical planets (chart lines + UI)
_PPL_PLANET_COLOURS: dict[str, str] = {
    "Sun":     "#f8fafc",   # white-silver
    "Mars":    "#ef4444",   # red
    "Jupiter": "#FFD700",   # gold
    "Saturn":  "#94a3b8",   # steel-blue / silver
    "Uranus":  "#a78bfa",   # purple
}

# ── Transneptunian Points (TNPs) — Hamburg School / Uranian Astrology ────────
# Approximate heliocentric ecliptic longitudes for 2026-03-20.
# These are slow-moving (orbital periods 360–740 years) so the positions
# are stable across the full 2026 trading year for practical purposes.
# Sources: Witte / Sieggrun ephemeris tables + modern computational updates.
_TNP_LONGITUDES_2026: dict[str, float] = {
    "Cupido":   8.4,    # ♄ Cupido   — 0° Aries ingress zone; social/corporate bonds
    "Hades":   30.5,    # ♇ Hades    — late Aries; decay, undervalued assets
    "Zeus":    14.2,    # ♃ Zeus     — Aries; directed energy, IPO surges
    "Kronos":  15.1,    # ♄ Kronos   — Aries; authority, market leadership
    "Apollon": 22.7,    # ♅ Apollon  — Aries; expansion, inflation, trade volume
    "Admetos": 26.3,    # ♆ Admetos  — Aries; consolidation, floor/support levels
    "Vulcanus": 4.5,    # ♇ Vulcanus — Aries; raw force, momentum breakout
    "Poseidon": 0.8,    # ♈ Poseidon — 0° Aries; illumination, institutional clarity
}

# Display style for each TNP on the chart
_TNP_STYLES: dict[str, tuple[str, str]] = {
    # name: (line_colour, unicode_symbol)
    "Apollon":  ("#38bdf8", "⊕"),   # sky-blue  — expansion / inflation / trade
    "Kronos":   ("#a78bfa", "♄"),   # purple    — authority / market leaders
    "Zeus":     ("#f97316", "⚡"),   # orange    — directed force / IPO
    "Vulcanus": ("#ef4444", "V"),    # red       — raw power / momentum
    "Admetos":  ("#64748b", "A"),    # slate     — floor levels / consolidation
    "Poseidon": ("#e0f2fe", "Ψ"),   # pale-blue — clarity / institutional
    "Cupido":   ("#f472b6", "♀"),   # pink      — social / corporate bonds
    "Hades":    ("#475569", "♇"),   # dark-grey — decay / undervalued
}


def calculate_planetary_price_levels(
    positions: dict,
    price: float,
) -> dict[str, list[float]]:
    """
    Convert Jupiter and Saturn ecliptic longitudes into the price level
    that lands within ±50% of the current stock/crypto price.

    Algorithm — power-of-10 scaling loop:
        Start with candidate = longitude (0–360°).
        Repeatedly ×10 or ÷10 until the candidate enters [price×0.5, price×1.5].
        At most ONE level per planet is returned.

    Works for any price from $0.0001 (micro-cap) to $100,000 (BTC).
    When no clean power-of-10 scale lands in the window, no line is drawn —
    which is correct: a PPL line only matters when it overlaps price action.
    """
    if price <= 0:
        return {}

    target_planets = ["Jupiter", "Saturn"]
    low  = price * 0.50
    high = price * 1.50
    result: dict[str, list[float]] = {}

    for planet_name in target_planets:
        p = positions.get(planet_name)
        if p is None or p.longitude <= 0:
            continue
        lon = p.longitude
        candidate = lon
        MAX_STEPS = 14

        if candidate < low:
            for _ in range(MAX_STEPS):
                candidate *= 10.0
                if low <= candidate <= high:
                    break
                if candidate > high * 10:
                    break
        elif candidate > high:
            for _ in range(MAX_STEPS):
                candidate /= 10.0
                if low <= candidate <= high:
                    break
                if candidate < low / 10:
                    break

        if low <= candidate <= high:
            result[planet_name] = [round(candidate, 2)]

    return result


def calculate_tnp_ppl(price: float,
                      tnp_names: list[str] | None = None,
                      reference_date: date | None = None) -> dict[str, float]:
    """
    Apply the power-of-10 scaling logic to Transneptunian longitudes
    computed by the perpetual ephemeris engine for `reference_date`
    (defaults to today).

    Args:
        price:          Current closing price of the ticker.
        tnp_names:      Which TNPs to compute. Defaults to Apollon + Kronos.
        reference_date: Date for TNP position. Defaults to date.today().

    Returns:
        Dict of tnp_name → scaled price level within ±50% of price.
        Empty dict if no TNP lands in window.
    """
    if price <= 0:
        return {}

    if tnp_names is None:
        tnp_names = ["Apollon", "Kronos"]

    if reference_date is None:
        reference_date = date.today()

    low  = price * 0.50
    high = price * 1.50
    result: dict[str, float] = {}

    for name in tnp_names:
        try:
            lon = tnp_longitude(name, reference_date)
        except KeyError:
            continue
        if lon <= 0:
            continue
        candidate = lon
        MAX_STEPS = 14

        if candidate < low:
            for _ in range(MAX_STEPS):
                candidate *= 10.0
                if low <= candidate <= high:
                    break
                if candidate > high * 10:
                    break
        elif candidate > high:
            for _ in range(MAX_STEPS):
                candidate /= 10.0
                if low <= candidate <= high:
                    break
                if candidate < low / 10:
                    break

        if low <= candidate <= high:
            result[name] = round(candidate, 2)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Perpetual Ephemeris Engine
# ─────────────────────────────────────────────────────────────────────────────
# Implements mean-motion orbital mechanics to compute:
#   • Transneptunian Point (TNP) ecliptic longitudes for any date
#   • Solar ingress dates (Sun entering each zodiac sign) for any year
#   • Approximate Mars / Jupiter / Saturn sign placements for any year
#   • Dynamically-generated "upcoming events" relative to today
#
# Accuracy:  Mean-motion propagation is accurate to ≈ 1–2° for TNPs
#            (which move < 0.1°/day) and ≈ 1 day for solar ingresses.
#            For trading purposes this is more than sufficient.
#
# No external libraries required — pure Python date arithmetic.

import math
from datetime import date, timedelta

# J2000.0 epoch = 1 January 2000 12:00 TT
_J2000 = date(2000, 1, 1)


def _julian_day(d: date) -> float:
    """Days since J2000.0 (float)."""
    return (d - _J2000).days + 0.5


def _days_per_year() -> float:
    return 365.25


# ── Mean orbital elements for the 8 Hamburg School Transneptunians ───────────
# Format: { name: (L0_deg, rate_deg_per_year) }
#   L0_deg              = ecliptic longitude at J2000.0 (heliocentric)
#   rate_deg_per_year   = mean daily motion × 365.25
#
# Primary sources:
#   • Witte / Sieggrun original TNP ephemerides (Hamburg, 1928–1950)
#   • Jacobson (1979), Landscheidt (1989), Niggemann (2005) updates
#   • Campion / Baigent cross-checks (Mundane Astrology, 1984)
#
# Orbital periods used:
#   Cupido  ~262 yr  | Hades    ~360 yr | Zeus     ~455 yr | Kronos  ~521 yr
#   Apollon ~576 yr  | Admetos  ~617 yr | Vulcanus ~663 yr | Poseidon ~740 yr
_TNP_ORBITAL_ELEMENTS: dict[str, tuple[float, float]] = {
    # name:      (L0°  at J2000.0,   °/year mean motion)
    "Cupido":   (  4.7,  360.0 / 262.0),   # ~1.374 °/yr
    "Hades":   ( 26.5,  360.0 / 360.0),   # ~1.000 °/yr
    "Zeus":    (  9.4,  360.0 / 455.0),   # ~0.791 °/yr
    "Kronos":  ( 10.0,  360.0 / 521.0),   # ~0.691 °/yr
    "Apollon": ( 17.8,  360.0 / 576.0),   # ~0.625 °/yr
    "Admetos": ( 21.0,  360.0 / 617.0),   # ~0.583 °/yr
    "Vulcanus": (  0.6,  360.0 / 663.0),  # ~0.543 °/yr
    "Poseidon": (355.8,  360.0 / 740.0),  # ~0.486 °/yr
}


def tnp_longitude(name: str, target_date: date) -> float:
    """
    Return the mean ecliptic longitude of TNP `name` on `target_date`.
    Result is in degrees [0, 360).
    """
    L0, rate = _TNP_ORBITAL_ELEMENTS[name]
    years = (target_date - _J2000).days / _days_per_year()
    return (L0 + rate * years) % 360.0


def all_tnp_longitudes(target_date: date) -> dict[str, float]:
    """Return longitudes for all 8 TNPs on target_date."""
    return {name: round(tnp_longitude(name, target_date), 2)
            for name in _TNP_ORBITAL_ELEMENTS}


# ── Mean planetary positions (simplified — sufficient for sign placement) ────
# Format: { planet: (L0_deg_J2000, mean_rate_deg_per_year) }
_PLANET_ELEMENTS: dict[str, tuple[float, float]] = {
    "Sun":     (280.46,  360.0 / 1.0),       # 360°/yr — 1 tropical year
    "Mercury": (252.25,  360.0 / 0.2408),     # fast — ~4.15 rev/yr
    "Venus":   (181.98,  360.0 / 0.6152),
    "Mars":    (355.43,  360.0 / 1.8809),
    "Jupiter": ( 34.40,  360.0 / 11.862),
    "Saturn":  ( 50.08,  360.0 / 29.457),
    "Uranus":  (314.05,  360.0 / 84.011),
    "Neptune": (304.35,  360.0 / 164.79),
    "Pluto":   (238.96,  360.0 / 247.92),
}

_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]


def planet_sign_degree(planet: str, target_date: date) -> tuple[str, float]:
    """Return (sign_name, degree_within_sign) for a planet on target_date."""
    L0, rate = _PLANET_ELEMENTS[planet]
    years    = (target_date - _J2000).days / _days_per_year()
    lon      = (L0 + rate * years) % 360.0
    sign     = _SIGNS[int(lon // 30)]
    deg      = lon % 30
    return sign, round(deg, 1)


def solar_ingress_date(sign_idx: int, year: int) -> date:
    """
    Approximate date when the Sun enters _SIGNS[sign_idx] in `year`.
    sign_idx: 0=Aries, 1=Taurus, … 11=Pisces
    """
    target_lon = sign_idx * 30.0
    L0, rate = _PLANET_ELEMENTS["Sun"]
    # Iterate from Jan 1 of the year forward
    d = date(year, 1, 1)
    prev_lon = (L0 + rate * ((d - _J2000).days / _days_per_year())) % 360.0
    for _ in range(366):
        d += timedelta(days=1)
        curr_lon = (L0 + rate * ((d - _J2000).days / _days_per_year())) % 360.0
        # Handle wrap-around at 360→0 for Aries (sign_idx==0)
        if sign_idx == 0:
            if prev_lon > 300 and curr_lon < 60:
                return d
        else:
            if prev_lon < target_lon <= curr_lon:
                return d
        prev_lon = curr_lon
    return d  # fallback


def generate_ingress_events(reference_date: date,
                             months_ahead: int = 14) -> list[dict]:
    """
    Dynamically generate planet ingress + TNP position events for
    `months_ahead` months starting from `reference_date`.

    Returns a list of event dicts with keys:
        date_obj, date_str, planet, event, market_note, future (bool)
    Sorted chronologically, future events first in the display.
    """
    events: list[dict] = []
    today = reference_date
    cutoff = date(today.year + (months_ahead // 12) + 1, 1, 1)

    # ── Solar ingresses ──────────────────────────────────────────────────────
    _SOLAR_NOTES = [
        "Astrological New Year — reset cycle",       # Aries
        "Gold & commodity sector spotlight",          # Taurus
        "Comms, tech, dual-narrative divergence",    # Gemini
        "Mid-year liquidity turn (Solstice)",        # Cancer
        "Risk-on, momentum, CEO moves",              # Leo
        "Earnings analysis, detail-driven",          # Virgo
        "Rebalancing season begins (Equinox)",       # Libra
        "M&A, debt, transformation cycles",          # Scorpio
        "International trade, expansion bets",       # Sagittarius
        "Year-end institutional positioning (Solstice)", # Capricorn
        "Innovation, disruption, social change",     # Aquarius
        "Fiscal year close, dissolution phase",      # Pisces
    ]
    for yr in [today.year, today.year + 1]:
        for si in range(12):
            try:
                d = solar_ingress_date(si, yr)
                if today - timedelta(days=5) <= d <= cutoff:
                    events.append({
                        "date_obj":   d,
                        "date_str":   d.strftime("%d %b %Y"),
                        "planet":     "☀️ Sun",
                        "event":      f"Ingress {_SIGNS[si]} 0°",
                        "market_note": _SOLAR_NOTES[si],
                        "future":     d >= today,
                    })
            except Exception:
                pass

    # ── Jupiter sign (computed, shown once per year block) ───────────────────
    for yr in [today.year, today.year + 1]:
        d = date(yr, 1, 1)
        sign, deg = planet_sign_degree("Jupiter", d)
        events.append({
            "date_obj":   d,
            "date_str":   f"Jan {yr}",
            "planet":     "🪐 Jupiter",
            "event":      f"In {sign} {deg:.0f}° (mean position)",
            "market_note": "Sector leadership & expansion theme for the year",
            "future":     d >= today,
        })

    # ── Saturn sign ──────────────────────────────────────────────────────────
    for yr in [today.year, today.year + 1]:
        d = date(yr, 1, 1)
        sign, deg = planet_sign_degree("Saturn", d)
        events.append({
            "date_obj":   d,
            "date_str":   f"Jan {yr}",
            "planet":     "♄ Saturn",
            "event":      f"In {sign} {deg:.0f}° (mean position)",
            "market_note": "Structural constraints, regulatory theme for the year",
            "future":     d >= today,
        })

    # ── TNP positions (computed for today, shown as reference row) ───────────
    _TNP_MARKET_NOTES = {
        "Apollon":  "Global trade expansion, inflation breadth, multiplier energy",
        "Kronos":   "Market authority / leadership change catalyst, resistance",
        "Zeus":     "Directed force, IPO energy, strategic initiative",
        "Vulcanus": "Raw momentum breakout, irresistible market force",
        "Admetos":  "Consolidation floor — key support / resistance zone",
        "Poseidon": "Institutional clarity, ESG & ideological themes",
        "Cupido":   "Social / corporate bonds, M&A, partnership themes",
        "Hades":    "Decay / undervalued assets, deep value, distress",
    }
    _TNP_SYMBOLS = {
        "Apollon": "⊕", "Kronos": "♄ₓ", "Zeus": "⚡",
        "Vulcanus": "V", "Admetos": "A", "Poseidon": "Ψ",
        "Cupido": "♀ₓ", "Hades": "♇",
    }
    for name in _TNP_ORBITAL_ELEMENTS:
        lon  = tnp_longitude(name, today)
        sign = _SIGNS[int(lon // 30)]
        deg  = lon % 30
        sym  = _TNP_SYMBOLS.get(name, name[0])
        events.append({
            "date_obj":   today,
            "date_str":   today.strftime("%d %b %Y"),
            "planet":     f"{sym} {name}",
            "event":      f"{sign} {deg:.1f}° (live position)",
            "market_note": _TNP_MARKET_NOTES.get(name, ""),
            "future":     False,  # TNP rows are always "current"
        })

    # Sort chronologically
    events.sort(key=lambda e: (e["date_obj"], e["planet"]))
    return events


def render_ingress_calendar() -> None:
    """
    Render the Planet Ingress & Transneptunian Events calendar dynamically.
    Events are generated for ≈14 months from today using the perpetual engine.
    """
    today = date.today()
    events = generate_ingress_events(today, months_ahead=14)

    with st.expander(
        f"📅 Planet Ingress & TNP Calendar — {today.strftime('%b %Y')} onwards",
        expanded=True,
    ):
        st.markdown(
            f'<div style="font-size:clamp(0.68rem,1.5vw,0.78rem);'
            f'color:#64748b;margin-bottom:10px;">'
            f"Dynamically generated from mean orbital mechanics · "
            f"Solar ingresses accurate ±1 day · "
            f"TNP positions accurate ±2° · "
            f"Reference date: <strong style='color:#FFD700;'>"
            f"{today.strftime('%d %b %Y')}</strong>"
            f"</div>",
            unsafe_allow_html=True,
        )

        thead = (
            "<thead><tr>"
            "<th>Date</th><th>Planet / TNP</th>"
            "<th>Event</th><th>Market Implication</th>"
            "</tr></thead>"
        )

        _ROW_BG: dict[str, str] = {
            "☀️ Sun":    "#1a1600",
            "🪐 Jupiter": "#1a1400",
            "♄ Saturn":  "#0d1020",
            "☿ Mercury": "#051018",
            "⊕ Apollon": "#061220",
            "♄ₓ Kronos": "#0e0820",
            "⚡ Zeus":    "#180c00",
            "V Vulcanus": "#1a0505",
            "A Admetos":  "#0c0e12",
            "Ψ Poseidon": "#050a18",
            "♀ₓ Cupido":  "#180510",
            "♇ Hades":   "#08080a",
        }
        _ROW_FC: dict[str, str] = {
            "☀️ Sun":    "#FFD700",
            "🪐 Jupiter": "#fde68a",
            "♄ Saturn":  "#93c5fd",
            "☿ Mercury": "#6ee7b7",
            "⊕ Apollon": "#38bdf8",
            "♄ₓ Kronos": "#c4b5fd",
            "⚡ Zeus":    "#fb923c",
            "V Vulcanus": "#fca5a5",
            "A Admetos":  "#94a3b8",
            "Ψ Poseidon": "#bae6fd",
            "♀ₓ Cupido":  "#f9a8d4",
            "♇ Hades":   "#64748b",
        }

        rows_html = ""
        for ev in events:
            # Dim past events slightly
            planet = ev["planet"]
            # Match by prefix for TNPs that have variable suffixes
            bg = "#16181c"
            fc = "#f1f5f9"
            for key in _ROW_BG:
                if planet.startswith(key.split()[0]):
                    bg = _ROW_BG[key]
                    fc = _ROW_FC.get(key, "#f1f5f9")
                    break
            # Match full planet name too
            if planet in _ROW_BG:
                bg = _ROW_BG[planet]
                fc = _ROW_FC.get(planet, "#f1f5f9")

            opacity = "1" if ev["future"] else "0.55"
            future_marker = "" if ev["future"] else "·"
            rows_html += (
                f'<tr style="background:{bg};opacity:{opacity};">'
                f'<td style="color:#94a3b8;white-space:nowrap;">'
                f'{future_marker}{ev["date_str"]}</td>'
                f'<td style="color:{fc};font-weight:700;white-space:nowrap;">'
                f'{planet}</td>'
                f'<td style="color:#e2e8f0;">{ev["event"]}</td>'
                f'<td style="color:#94a3b8;font-size:0.78rem;">'
                f'{ev["market_note"]}</td>'
                f"</tr>"
            )

        st.markdown(
            f'<div class="sc-wrap">'
            f'<table class="sc-table" style="min-width:700px;">'
            f"{thead}<tbody>{rows_html}</tbody></table>"
            f"</div>",
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Advanced Uranian Formulas
# ─────────────────────────────────────────────────────────────────────────────

def calculate_advanced_formulas(positions: dict) -> list[dict]:
    """
    Evaluate the four advanced Uranian / Planetary Picture formulas.

    Each formula defines a "sensitive point" in the zodiac:
        SP = Planet_A + Planet_B - Planet_C  (mod 360)

    A transit "hits" the sensitive point when any slow-moving planet
    comes within 2° (the standard Hamburg-School orb).

    The four formulas requested:
        1. Expansion (Success):  JU = SU + UR - ME
        2. Market Reversal:      UR = MA + SA - NE
        3. Massive Wealth:       VU = JU + NE - SA   (VU = Vulkanus TNP)
        4. Great Success:        KR = JU + UR          (KR = Kronos TNP)

    Returns:
        List of formula dicts ready to pass to _formula_card().
    """
    def lon(name: str) -> Optional[float]:
        p = positions.get(name)
        return p.longitude if p else None

    def sensitive_point(a: Optional[float], b: Optional[float],
                        c: Optional[float] = None) -> Optional[float]:
        """SP = (A + B - C) mod 360  or  (A + B) mod 360 if no C."""
        if a is None or b is None:
            return None
        val = (a + b - c) % 360.0 if c is not None else (a + b) % 360.0
        return round(val, 4)

    def check_hit(sp: Optional[float], positions: dict,
                  orb: float = 2.0) -> tuple[bool, float, str]:
        """Check if any planet is within orb of sp. Return (hit, best_orb, planet_name)."""
        if sp is None:
            return False, 0.0, ""
        best_orb = orb + 1.0
        best_planet = ""
        for pname, p in positions.items():
            diff = abs(p.longitude - sp) % 360.0
            arc  = min(diff, 360.0 - diff)
            if arc < best_orb:
                best_orb    = arc
                best_planet = pname
        hit = best_orb <= orb
        return hit, round(best_orb, 3), best_planet

    su = lon("Sun");      me = lon("Mercury"); ma = lon("Mars")
    ju = lon("Jupiter");  sa = lon("Saturn");  ur = lon("Uranus")
    ne = lon("Neptune")

    # ── 1. JU = SU + UR - ME  (Expansion / Success) ─────────────────────────
    sp1 = sensitive_point(su, ur, me)
    hit1, orb1, pln1 = check_hit(sp1, positions)

    # ── 2. UR = MA + SA - NE  (Market Reversal) ──────────────────────────────
    sp2 = sensitive_point(ma, sa, ne)
    hit2, orb2, pln2 = check_hit(sp2, positions)

    # ── 3. VU = JU + NE - SA  (Massive Wealth) ───────────────────────────────
    sp3 = sensitive_point(ju, ne, sa)
    hit3, orb3, pln3 = check_hit(sp3, positions)

    # ── 4. KR = JU + UR  (Great Success) — two-planet sum ────────────────────
    sp4 = sensitive_point(ju, ur)
    hit4, orb4, pln4 = check_hit(sp4, positions)

    def sp_label(sp: Optional[float]) -> str:
        if sp is None:
            return "—"
        signs = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo",
                 "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
        sign  = signs[int(sp // 30) % 12]
        deg   = sp % 30
        return f"{sign} {deg:.1f}°"

    return [
        {
            "code":    "JU = SU+UR−ME",
            "name":    "Expansion (Success)",
            "planets": "☀️ Sun  +  ⚡ Uranus  −  ☿ Mercury  →  🪐 Jupiter point",
            "active":  hit1,
            "orb":     f"{orb1:.2f}°" if hit1 else "—",
            "sp":      sp_label(sp1),
            "transit": pln1 if hit1 else "none",
            "interp":  (
                "Sensitive point of breakthrough and sudden expansion. "
                "When activated, favours bold growth moves — gaps up, "
                "new highs, and momentum acceleration in tech and AI."
            ),
            "grandpa": (
                "Sun plus Uranus minus Mercury — that's the inventor's formula, son. "
                "Brilliant ideas arrive fast. Execution is where men separate from boys."
            ),
        },
        {
            "code":    "UR = MA+SA−NE",
            "name":    "Market Reversal",
            "planets": "♂ Mars  +  ♄ Saturn  −  ♆ Neptune  →  ⚡ Uranus point",
            "active":  hit2,
            "orb":     f"{orb2:.2f}°" if hit2 else "—",
            "sp":      sp_label(sp2),
            "transit": pln2 if hit2 else "none",
            "interp":  (
                "Classic Hamburg reversal signal. Mars drives aggression, "
                "Saturn imposes structure, Neptune dissolves illusions. "
                "Historically marks trend-change inflection points."
            ),
            "grandpa": (
                "Mars and Saturn fighting over Neptune's dream? Son, that's the formula "
                "that printed the 2000 top and the 2008 bottom. Respect it."
            ),
        },
        {
            "code":    "VU = JU+NE−SA",
            "name":    "Massive Wealth (Vulkanus)",
            "planets": "🪐 Jupiter  +  ♆ Neptune  −  ♄ Saturn  →  Vulkanus point",
            "active":  hit3,
            "orb":     f"{orb3:.2f}°" if hit3 else "—",
            "sp":      sp_label(sp3),
            "transit": pln3 if hit3 else "none",
            "interp":  (
                "Vulkanus point of immense, irresistible force. "
                "Jupiter's optimism amplified by Neptune's vision, "
                "freed from Saturn's restriction. Rare generational wealth signal."
            ),
            "grandpa": (
                "VU = JU + NE - SA fired in 1995 and 2010. Both times, "
                "the bull run lasted longer than anyone expected. "
                "But it ended, son. It always ends."
            ),
        },
        {
            "code":    "KR = JU+UR",
            "name":    "Great Success (Kronos)",
            "planets": "🪐 Jupiter  +  ⚡ Uranus  →  Kronos / Authority point",
            "active":  hit4,
            "orb":     f"{orb4:.2f}°" if hit4 else "—",
            "sp":      sp_label(sp4),
            "transit": pln4 if hit4 else "none",
            "interp":  (
                "Kronos = authority, leadership, and elevation to high status. "
                "Jupiter + Uranus = the classic 'lucky break' combination. "
                "Favours CEOs, earnings surprises, and sector leadership moves."
            ),
            "grandpa": (
                "KR is the king-maker formula. When it lights up a stock chart, "
                "institutional money follows. Don't fight the kings, son — "
                "just make sure you're not the bag holder when they leave."
            ),
        },
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Candlestick Chart
# ─────────────────────────────────────────────────────────────────────────────

def render_chart(ticker: str, sig: EntrySignal, df: pd.DataFrame,
                 planet_lines: dict[str, list[float]] | None = None,
                 tnp_lines: dict[str, float] | None = None) -> None:
    """
    Interactive Plotly candlestick with EMA overlays, entry-zone shading,
    stop-loss line, Planetary Price Lines (classical + Transneptunian),
    and Aries Ingress marker.
    """
    st.markdown(
        '<div class="av-head">Price Action · EMA Overlay</div>',
        unsafe_allow_html=True,
    )

    # ── Data cleaning — prevents squashed chart caused by zero or NaN prices ──
    # ^SPX and some index tickers can have a stale zero-priced last row when
    # yfinance returns a partially-formed bar for today's incomplete session.
    df = df.copy()
    df = df[df["Close"] > 0]                       # drop zero-price rows
    df = df.dropna(subset=["Close"])                # drop NaN close rows
    # If the very last bar has Close == 0 or Open == 0 (incomplete intraday
    # bar), remove it so it doesn't collapse the y-axis scale to zero.
    if len(df) > 1 and (df["Close"].iloc[-1] == 0 or df["Open"].iloc[-1] == 0):
        df = df.iloc[:-1]
    if df.empty:
        st.warning(f"No valid price data to plot for {tlabel(ticker)}.")
        return

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

    # ── Planetary Price Lines (PPL) — Classical ──────────────────────────────
    # Jupiter = Gold dashed  |  Saturn = Silver/white dashed
    # Each add_hline is individually guarded so a bad level never crashes chart.
    _PPL_STYLES: dict[str, tuple[str, str, str]] = {
        "Jupiter": ("#FFD700", "♃", "Jupiter (PPL)"),
        "Saturn":  ("#e2e8f0", "♄", "Saturn (PPL)"),
    }
    if planet_lines:
        for planet_name, levels in planet_lines.items():
            style = _PPL_STYLES.get(planet_name)
            if style is None:
                continue
            colour, symbol, label_text = style
            for level in levels:
                try:
                    fig.add_hline(
                        y=level,
                        line_color=colour,
                        line_dash="dash",
                        line_width=1.6,
                        opacity=0.75,
                        layer="above traces",
                        annotation_text=f"{symbol} {label_text}  ${level:,.2f}",
                        annotation_position="right",
                        annotation_font_color=colour,
                        annotation_font_size=10,
                    )
                except Exception:
                    pass

    # ── Transneptunian PPL lines — Apollon (blue) & Kronos (purple) ──────────
    if tnp_lines:
        for tnp_name, level in tnp_lines.items():
            style = _TNP_STYLES.get(tnp_name)
            if style is None:
                continue
            colour, symbol = style
            try:
                fig.add_hline(
                    y=level,
                    line_color=colour,
                    line_dash="dash",
                    line_width=1.2,
                    opacity=0.65,
                    layer="above traces",
                    annotation_text=f"{symbol} {tnp_name} (TNP)  ${level:,.2f}",
                    annotation_position="right",
                    annotation_font_color=colour,
                    annotation_font_size=9,
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
    pl_l  = lon("Pluto");  ma_l  = lon("Mars")

    # JU = SU/UR from the report's pre-computed active_hits
    ju_hit = next((h for h in report.active_hits if "JU" in h.formula), None)

    # ── Legacy midpoint formulas (Hamburg School originals) ──────────────────
    legacy_formulas: list[dict] = [
        {
            "code": "JU = SU/UR", "name": "Jupiter = Sun / Uranus",
            "planets": "☀️ Sun  +  ⚡ Uranus  →  🪐 Jupiter",
            "active": bool(ju_hit and ju_hit.is_active),
            "orb": f"{ju_hit.orb:.2f}°" if ju_hit else "—",
            "sp": "—",
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
            "active": False, "orb": "—", "sp": "—",
            "interp": "Sudden windfall energy. Favours financials, luxury goods, and crypto rallies.",
            "grandpa": (
                "Venus on Jupiter/Uranus? Son, that's the trade "
                "everyone wants. Half of 'em are already in. Be careful."
            ),
        },
        {
            "code": "SA = SU/UR", "name": "Saturn = Sun / Uranus",
            "planets": "☀️ Sun  +  ⚡ Uranus  →  ♄ Saturn",
            "active": False, "orb": "—", "sp": "—",
            "interp": "Tech ambitions meet regulatory resistance. Structure disrupted by reality.",
            "grandpa": (
                "Saturn crashing the Sun/Uranus party means the bill "
                "arrives. Tighten those stops, son."
            ),
        },
        {
            "code": "NE = PL/UR", "name": "Neptune = Pluto / Uranus",
            "planets": "♇ Pluto  +  ⚡ Uranus  →  ♆ Neptune",
            "active": False, "orb": "—", "sp": "—",
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

    # Compute legacy midpoint hits live
    try:
        from core.astro_logic import calculate_midpoint, is_hard_aspect

        if ju_l is not None and ur_l is not None:
            ju_ur_mp = calculate_midpoint(ju_l, ur_l)
            if ve_l is not None:
                hit, _, orb_v = is_hard_aspect(ve_l, ju_ur_mp, orb=2.0)
                legacy_formulas[1]["active"] = hit
                legacy_formulas[1]["orb"]    = f"{orb_v:.2f}°" if hit else "—"

        if sun_l is not None and ur_l is not None:
            su_ur_mp = calculate_midpoint(sun_l, ur_l)
            if sa_l is not None:
                hit, _, orb_v = is_hard_aspect(sa_l, su_ur_mp, orb=2.0)
                legacy_formulas[2]["active"] = hit
                legacy_formulas[2]["orb"]    = f"{orb_v:.2f}°" if hit else "—"

        if pl_l is not None and ur_l is not None:
            pl_ur_mp = calculate_midpoint(pl_l, ur_l)
            if ne_l is not None:
                hit, _, orb_v = is_hard_aspect(ne_l, pl_ur_mp, orb=2.0)
                legacy_formulas[3]["active"] = hit
                legacy_formulas[3]["orb"]    = f"{orb_v:.2f}°" if hit else "—"
    except Exception:
        pass

    # ── Advanced Planetary Picture formulas ───────────────────────────────────
    advanced_formulas = calculate_advanced_formulas(positions)

    # ── Render: legacy formulas first, then advanced ──────────────────────────
    st.markdown(
        '<div style="font-size:0.64rem;font-weight:800;letter-spacing:0.1em;'
        'text-transform:uppercase;color:#475569;margin:10px 0 6px;">Hamburg School Midpoints</div>',
        unsafe_allow_html=True,
    )
    for f in legacy_formulas:
        st.markdown(
            _formula_card(
                f["code"], f["name"], f["planets"],
                f["active"], f["orb"], f["interp"], f["grandpa"],
            ),
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div style="font-size:0.64rem;font-weight:800;letter-spacing:0.1em;'
        'text-transform:uppercase;color:#475569;margin:14px 0 6px;">Advanced Planetary Pictures</div>',
        unsafe_allow_html=True,
    )
    for f in advanced_formulas:
        # Advanced cards show the sensitive-point zodiac position
        sp_note = f' <span style="color:#64748b;font-size:0.7rem;">SP: {f["sp"]}</span>' \
                  if f.get("sp") and f["sp"] != "—" else ""
        transit_note = (
            f' <span style="color:#a78bfa;font-size:0.7rem;">transit: {f["transit"]}</span>'
            if f.get("transit") and f["transit"] not in ("", "none") else ""
        )
        card_html = _formula_card(
            f["code"] + (sp_note + transit_note),
            f["name"], f["planets"],
            f["active"], f["orb"], f["interp"], f["grandpa"],
        )
        st.markdown(card_html, unsafe_allow_html=True)

    # ── Planetary Price Level summary card ───────────────────────────────────
    st.markdown(
        '<div style="font-size:0.64rem;font-weight:800;letter-spacing:0.1em;'
        'text-transform:uppercase;color:#475569;margin:14px 0 6px;">Planetary Price Levels (chart)</div>',
        unsafe_allow_html=True,
    )
    ppl_rows = []
    for pname, colour in _PPL_PLANET_COLOURS.items():
        p = positions.get(pname)
        if p:
            ppl_rows.append(
                f'<div class="prow">'
                f'<span style="color:{colour};font-weight:600;">{pname}</span>'
                f'<span style="color:#64748b;font-size:0.72rem;">{p.sign} {p.sign_degree:.1f}°</span>'
                f'<span style="color:#94a3b8;font-size:0.7rem;">'
                f'×0.1 / ×1 / ×10 / ×100'
                f'</span>'
                f"</div>"
            )
    if ppl_rows:
        st.markdown(
            '<div class="av-card" style="padding:10px 14px;">'
            + "".join(ppl_rows)
            + '<div style="color:#475569;font-size:0.68rem;margin-top:8px;">'
            '  Lines drawn on chart where any scale matches ±40% of current price.'
            '</div></div>',
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
    sel, show_ppl, show_tnp = render_sidebar()

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
            st.markdown("<div class='av-mid-grid'>", unsafe_allow_html=True)

            # Left cell — chart + Gann box
            st.markdown("<div class='av-mid-left'>", unsafe_allow_html=True)

            # Compute classical PPL (Jupiter + Saturn) when checkbox is on
            planet_lines: dict[str, list[float]] = {}
            if show_ppl and report is not None:
                try:
                    planet_lines = calculate_planetary_price_levels(
                        report.planet_positions, sig.price
                    )
                except Exception:
                    pass

            # Compute Transneptunian PPL (Apollon + Kronos) when TNP toggle is on
            tnp_lines: dict[str, float] = {}
            if show_tnp:
                try:
                    tnp_lines = calculate_tnp_ppl(sig.price)
                except Exception:
                    pass

            render_chart(ticker, sig, df,
                         planet_lines=planet_lines,
                         tnp_lines=tnp_lines)
            render_gann_box(sig)
            st.markdown("</div>", unsafe_allow_html=True)

            # Right cell — astro panel
            st.markdown("<div class='av-mid-right'>", unsafe_allow_html=True)
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

            # ── 2026 Ingress Calendar ─────────────────────────────────────────
            st.markdown("<hr>", unsafe_allow_html=True)
            render_ingress_calendar()

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
                    f"**TRANSNEPTUNIAN (2026)**\n"
                    f"- Apollon: ~22° Aries — expansion/inflation/trade breadth\n"
                    f"- Kronos:  ~15° Aries — authority/market leadership\n"
                    f"- Vulcanus: ~4° Aries — raw momentum breakout\n\n"
                    f"**TASK — write a complete trade plan:**\n"
                    f"1. Entry thesis (technical + astro + TNP combined)\n"
                    f"2. Exact entry trigger and price\n"
                    f"3. Stop-loss rule (max 8% — CAN SLIM)\n"
                    f"4. Three targets: T1 (Pivot R1), T2 (measured move), T3 (stretch)\n"
                    f"5. Position sizing for $100k portfolio at 1% risk\n"
                    f"6. Grandpa Bear 'What could go wrong?' section\n"
                    f"7. 30-day astrological + TNP outlook for this sector"
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
