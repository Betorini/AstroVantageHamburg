# Skill: astro_finance.md
## Specialist Knowledge: Uranian Astro-Finance for the Hamburg School

### Scope
This skill file provides Claude with specialist context for analyzing stocks using the
Uranian (Hamburg School) astrology system integrated with technical analysis.

---

## The Uranian System — Core Principles

The Hamburg School (founded by Alfred Witte, expanded by Friedrich Sieggrün) differs from
traditional astrology in several key ways:

1. **Hard Aspects Only**: Only 0°, 45°, 90°, 135°, 180° are used. Soft aspects (60°, 120°)
   are not considered significant in market analysis.

2. **Midpoint Trees**: The most powerful technique. A midpoint X/Y is the point equidistant
   between planet X and planet Y on the 360° wheel. Any planet on this midpoint (within 2°)
   "activates" both X and Y simultaneously.

3. **The 90° Dial**: Compresses the 360° wheel into a 90° space, making all hard aspect
   relationships visible at a glance.

4. **Transneptunian Planets (TNPs)**: Witte posited 8 hypothetical outer bodies:
   Cupido, Hades, Zeus, Kronos, Apollon, Admetos, Vulkanus, Poseidon.
   These are used by advanced practitioners but NOT implemented in v1.

---

## Primary Formula: Jupiter = Sun / Uranus (JU = SU/UR)

### Mathematical Definition
```
Midpoint(SU/UR) = (Sun_longitude + Uranus_longitude) / 2
Formula active when: |Jupiter_longitude - Midpoint(SU/UR)| ≤ 2° (on any hard aspect)
```

### Financial Interpretation
| Planet | Financial Symbolism |
|--------|-------------------|
| Sun    | The trend, the CEO, the leading index |
| Jupiter | Expansion, optimism, institutional buyers, excess |
| Uranus | Technology, disruption, sudden events, electricity |

**JU = SU/UR combined**: "Sudden, joyful breakthrough in technology/trend leadership."
In market terms: gap-up opens, unexpected positive catalysts, AI/tech announcements,
short squeezes, momentum surges.

**Caution**: This is a high-amplitude signal. It can also produce sell-the-news events
if the underlying fundamentals don't support the move.

---

## Aries Ingress Chart (March 20, 2026)

The Aries Ingress is the moment the Sun enters 0° Aries — the astrological New Year.
The chart cast for this moment is read as a "world forecast" for the following 12 months.

**Key features of the 2026 Aries Ingress:**
- Sun exactly at 0° Aries (the Ingress itself)
- Mercury stationing direct at ~22° Pisces (communications clarity returning)
- Jupiter in late Taurus / Gemini 0° (expansion entering the realm of information)
- Uranus in late Taurus (technology transformation in finance/material goods)
- Jupiter conjunct Uranus (orb ~2°): Major tech/disruption expansion cycle (last exact in 2024)

**Interpretation for Mag 7 stocks:**
- NVDA / MSFT / GOOGL / META: Favorable for AI infrastructure plays through 2026
- TSLA: Uranus in Taurus = transformation in vehicles/energy, but Saturn in Pisces
  warns of regulatory/liquidity headwinds
- AAPL / AMZN: Mercury Direct favors consumer electronics and commerce recovery

---

## Mercury Retrograde / Direct Cycles and Tech Stocks

Mercury governs: communication, data, software, contracts, short-term trading.

**Mercury Retrograde**: Historical pattern shows increased volatility and false breakouts
in tech (FAANG/Mag7) during Mercury retrograde periods.

**Mercury Direct Station**: The station direct is often more significant than the station
retrograde. Initial surge in tech names, followed by 3–5 day consolidation.

**2026 Mercury Retrograde periods** (approximate):
- Feb 12 – Mar 6: Aquarius/Pisces
- Jun 6 – Jun 30: Gemini  
- Oct 2 – Oct 26: Libra/Scorpio

---

## Grandpa Bear Persona — Prompt Engineering Notes

When generating "Grandpa Bear" advice, Claude should embody:
- An octogenarian trader who survived 1929, 1987, 2000, and 2008
- Speaks in plain, folksy language — never financial jargon
- Always asks the contrarian question: "What if I'm wrong?"
- Respects astro signals but demands technical confirmation
- Never says "this time is different"
- Key phrases: "boy," "son," "I've seen this before," "exits," "bag," "partial profits"

**Example tone:**
> "Son, Jupiter on the Sun/Uranus midpoint is real. But so was it in March 2000.
> You take your first tranche off the table when the stock's up 20%, you hear me?
> Let the house play with house money after that."

---

## Deep Analysis Prompt Template

When the user clicks "Deep Analysis" in the UI, Claude should receive this context
and produce a structured trade plan:

```
System: You are AstroVantage's Deep Analysis engine, combining CAN SLIM technical 
analysis with Uranian Hamburg School astrology.

Current Technical Data:
- Ticker: {ticker}
- Price: ${price}
- RSI: {rsi}
- EMA Alignment: {ema_align}
- MACD: {macd_signal}
- Volume Ratio: {volume_ratio}x
- Signal: {signal}
- Suggested Entry: ${entry_low} – ${entry_high}
- Stop Loss: ${stop_loss} ({stop_pct}% below entry)

Current Astro Context:
- Date: March 20, 2026 — Aries Ingress + Mercury Station Direct
- JU = SU/UR formula status: {ju_su_ur_active}
- Active transits: {active_transits}

Task: Write a complete trade plan including:
1. Entry thesis (technical + astro combined)
2. Exact entry price and trigger condition
3. Stop loss level and rule
4. Three price targets (T1 = pivot R1, T2 = measured move, T3 = stretch)
5. Position sizing recommendation (assume $100k portfolio)
6. "What could go wrong?" section (Grandpa Bear)
7. 30-day astrological outlook for this sector
```

---

## Key References
- *The Language of Uranian Astrology* — Roger Jacobson (1975)
- *Combination of Stellar Influences* — Alfred Witte / Friedrich Sieggrün
- *Astrology for Day Traders* — Grace Morris
- CAN SLIM: *How to Make Money in Stocks* — William J. O'Neil
