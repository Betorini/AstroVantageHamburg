# AstroVantage — Persistent Project Rules & Context

## Project Overview
AstroVantage is a high-end stock entry analysis dashboard combining:
- **Technical Analysis**: CAN SLIM methodology + EMA 21/50/200, RSI, MACD, Pivot Breakouts
- **Uranian Astrology**: Hamburg School principles — hard aspects (0°, 45°, 90°, 135°, 180°),
  midpoint trees, and the primary formula `Jupiter = Sun / Uranus` (JU = SU/UR)

## Primary Targets
Magnificent Seven: NVDA, MSFT, GOOGL, AMZN, META, TSLA, AAPL

## Critical Date Context
- **Today**: March 20, 2026 — Aries Ingress (Sun enters Aries, new astrological year)
- **Mercury Station Direct**: Mercury turns direct today — a key inflection point for tech stocks
- **Interpretation**: Aries Ingress charts are used to forecast the full year ahead. Mercury Direct
  after a retrograde period historically correlates with clarity returning to tech/comms sectors.

## Architecture Rules
1. All indicator calculations in `core/indicators.py` — pure functions, no side effects
2. All screening/signal logic in `core/screener.py` — returns typed dataclasses
3. Astro calculations in `core/astro_logic.py` — ephemeris-based, no hardcoded planet positions
4. Data fetching ONLY in `utils/fetcher.py` with `@st.cache_data` (TTL: 300s)
5. UI assembly ONLY in `app.py` — no business logic in the frontend

## Code Standards
- Python 3.10+ with full type hints on every function signature
- Functional programming: pure functions in `core/`, no class-based state
- All monetary values: float, rounded to 2 decimal places in display
- All percentage values: float, displayed as XX.XX%
- No hardcoded API keys — use `.env` / `st.secrets`

## Trading Rules (CAN SLIM)
- **Entry**: Only on pivot breakouts with volume > 1.5x 50-day avg
- **Stop Loss**: Maximum 8% below entry price (never negotiable)
- **Position Size**: Risk 1% of portfolio per trade
  - Formula: `position_size = (portfolio_value * 0.01) / (entry_price * stop_loss_pct)`
- **Trend Filter**: Price must be above EMA 200 for long entries

## Uranian Formula
The primary transit formula tracked daily:
```
Jupiter = Sun / Uranus  (JU = SU/UR)
```
Activation criteria:
- Sun at the midpoint of Jupiter and Uranus (±2° orb)
- OR any hard aspect (0°/45°/90°/135°/180°) between Jupiter and Uranus

## AI Persona: "Grandpa Bear"
When the JU = SU/UR formula is active, display advice from "Grandpa Bear":
- Grandpa Bear is a wise, cautious elder who survived the 1929, 1987, 2000, and 2008 crashes
- He speaks plainly, warns about euphoria, and always asks "but what if I'm wrong?"
- His advice appears as a yellow warning card in the Uranian Insight Panel

## File Change Protocol
1. Run `pytest tests/` after ANY change to `core/`
2. Update this CLAUDE.md if strategy or tech stack changes
3. Never commit API keys or `.env` files

## Dependencies
See `requirements.txt` for full list. Key packages:
- `streamlit>=1.32` — UI framework
- `yfinance>=0.2.36` — market data
- `pandas-ta>=0.3.14b` — technical indicators
- `plotly>=5.19` — interactive charts
- `ephem>=4.1` — astronomical calculations
- `python-dotenv>=1.0` — environment variables
