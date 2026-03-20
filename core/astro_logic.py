"""
core/astro_logic.py
-------------------
Uranian Hamburg School astrology calculations.
Primary formula: Jupiter = Sun / Uranus  (JU = SU/UR)

The midpoint SU/UR is the arithmetic mean of the Sun and Uranus longitudes.
A "hit" occurs when Jupiter (or any planet) is within ±2° of that midpoint,
or forms a hard aspect (0°, 45°, 90°, 135°, 180°) to it.

All angles are in tropical zodiacal degrees [0, 360).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

try:
    import ephem
    EPHEM_AVAILABLE = True
except ImportError:
    EPHEM_AVAILABLE = False


# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

HARD_ASPECTS: list[float] = [0.0, 45.0, 90.0, 135.0, 180.0]
ORB: float = 2.0  # degrees

PLANET_MEANINGS: dict[str, str] = {
    "Sun":     "Vitality, leadership, the CEO / founder energy",
    "Jupiter": "Expansion, optimism, excess, institutional money",
    "Uranus":  "Disruption, tech breakthroughs, sudden reversals",
    "Saturn":  "Restriction, consolidation, reality checks",
    "Mars":    "Aggression, momentum, volume surges",
    "Neptune": "Confusion, illusion, crypto/speculative bubbles",
    "Pluto":   "Transformation, power, generational shifts",
}

FORMULA_INTERPRETATION: dict[str, str] = {
    "JU=SU/UR": (
        "Jupiter activates the Sun/Uranus midpoint — a signature of sudden breakthroughs, "
        "euphoric rallies, and unexpected tech moves. This is the 'lottery energy' of astro-finance. "
        "Historically correlates with gap-up opens and momentum surges in tech stocks."
    ),
}

GRANDPA_BEAR_ADVICE: list[str] = [
    "Son, when everyone's celebratin', that's when I start countin' my exits.",
    "The Jupiter/Uranus midpoint fired in 1999 too. I remember what happened next.",
    "Euphoria is the market's way of handing you the bag. Take partial profits here.",
    "A breakout on astro energy alone ain't a breakout. Show me the volume.",
    "I've seen this transit five times. Three ended badly. Two were magnificent. Know your stops.",
    "The stars don't lie, but they don't tell the whole truth either. Check your fundamentals.",
]


# ─────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────

@dataclass
class PlanetPosition:
    name: str
    longitude: float       # tropical degrees [0, 360)
    sign: str
    sign_degree: float     # degrees within the sign [0, 30)


@dataclass
class MidpointResult:
    planet_a: str
    planet_b: str
    midpoint_longitude: float
    midpoint_sign: str
    midpoint_sign_degree: float


@dataclass
class TransitHit:
    formula: str                   # e.g. "JU = SU/UR"
    activating_planet: str
    midpoint: MidpointResult
    orb: float                     # actual orb in degrees
    aspect: float                  # aspect angle (0, 45, 90, 135, 180)
    is_active: bool
    interpretation: str
    grandpa_bear_quote: str


@dataclass
class DailyAstroReport:
    date: date
    planet_positions: dict[str, PlanetPosition]
    active_hits: list[TransitHit]
    aries_ingress: bool            # Is today the Aries Ingress?
    mercury_direct: bool           # Is Mercury stationing direct today?
    summary: str


# ─────────────────────────────────────────────
# Core Calculations (pure functions)
# ─────────────────────────────────────────────

def normalize_degrees(deg: float) -> float:
    """Normalize angle to [0, 360)."""
    return deg % 360.0


def angular_distance(a: float, b: float) -> float:
    """
    Shortest arc between two ecliptic longitudes.

    Returns value in [0, 180].
    """
    diff = abs(normalize_degrees(a) - normalize_degrees(b))
    return min(diff, 360.0 - diff)


def calculate_midpoint(long_a: float, long_b: float) -> float:
    """
    Calculate the near midpoint of two ecliptic longitudes.

    Uranian method uses the shorter arc midpoint:
        MP = (A + B) / 2 if |A-B| <= 180 else (A + B + 180) / 2

    Returns:
        Midpoint longitude in [0, 360).
    """
    diff = abs(long_a - long_b)
    if diff <= 180.0:
        mp = (long_a + long_b) / 2.0
    else:
        mp = (long_a + long_b) / 2.0 + 180.0
    return normalize_degrees(mp)


def longitude_to_sign(longitude: float) -> tuple[str, float]:
    """
    Convert ecliptic longitude to zodiac sign and degree within sign.

    Returns:
        Tuple of (sign_name, degrees_in_sign).
    """
    signs = [
        "Aries", "Taurus", "Gemini", "Cancer",
        "Leo", "Virgo", "Libra", "Scorpio",
        "Sagittarius", "Capricorn", "Aquarius", "Pisces",
    ]
    lon = normalize_degrees(longitude)
    sign_index = int(lon // 30)
    degree_in_sign = lon % 30
    return (signs[sign_index], round(degree_in_sign, 2))


def is_hard_aspect(planet_long: float, midpoint_long: float, orb: float = ORB) -> tuple[bool, float, float]:
    """
    Check if a planet forms a hard aspect to a midpoint.

    Hard aspects: 0°, 45°, 90°, 135°, 180° (and their mirrors).

    Args:
        planet_long:    Planet's ecliptic longitude.
        midpoint_long:  Target midpoint longitude.
        orb:            Allowed orb in degrees (default 2°).

    Returns:
        Tuple of (is_hit: bool, closest_aspect: float, actual_orb: float).
    """
    dist = angular_distance(planet_long, midpoint_long)
    for aspect in HARD_ASPECTS:
        diff = abs(dist - aspect)
        if diff <= orb:
            return (True, aspect, round(diff, 3))
        # Check the mirror axis (e.g. 315° = 360-45°)
        mirror_dist = angular_distance(planet_long, normalize_degrees(midpoint_long + 180))
        diff_mirror = abs(angular_distance(mirror_dist, aspect))
        if diff_mirror <= orb:
            return (True, aspect, round(diff_mirror, 3))
    return (False, 0.0, 0.0)


def build_midpoint(
    planet_a: str,
    long_a: float,
    planet_b: str,
    long_b: float,
) -> MidpointResult:
    """Construct a MidpointResult from two planet longitudes."""
    mp_long = calculate_midpoint(long_a, long_b)
    sign, deg = longitude_to_sign(mp_long)
    return MidpointResult(
        planet_a=planet_a,
        planet_b=planet_b,
        midpoint_longitude=round(mp_long, 4),
        midpoint_sign=sign,
        midpoint_sign_degree=deg,
    )


# ─────────────────────────────────────────────
# Ephemeris Integration (ephem library)
# ─────────────────────────────────────────────

def _ephem_longitude(body: ephem.Body, dt: datetime) -> float:
    """Compute tropical longitude for a body using pyephem."""
    observer = ephem.Observer()
    observer.date = ephem.Date(dt)
    observer.epoch = ephem.J2000
    body.compute(observer)
    # ephem gives ecliptic longitude in radians via astrological epoch
    # Use the RA/Dec → ecliptic conversion
    ecl = ephem.Ecliptic(body, epoch=ephem.J2000)
    lon_rad = float(ecl.lon)
    return normalize_degrees(math.degrees(lon_rad))


def get_planet_positions(dt: datetime | None = None) -> dict[str, PlanetPosition]:
    """
    Fetch tropical ecliptic longitudes for key planets using ephem.

    Falls back to approximate positions for March 20, 2026 (Aries Ingress)
    if ephem is not available.

    Args:
        dt: Target datetime (UTC). Defaults to now.

    Returns:
        Dict of planet_name → PlanetPosition.
    """
    if dt is None:
        dt = datetime.utcnow()

    # Fallback approximate positions for 2026-03-20 (Aries Ingress)
    FALLBACK_2026_03_20: dict[str, float] = {
        "Sun":     0.0,      # Aries 0° — exact ingress
        "Moon":    142.3,    # Leo ~22°
        "Mercury": 352.8,    # Pisces ~22° (stationing direct)
        "Venus":   28.5,     # Taurus ~28°
        "Mars":    96.4,     # Cancer ~6°
        "Jupiter": 58.7,     # Taurus ~28° / Gemini 0°
        "Saturn":  342.1,    # Pisces ~12°
        "Uranus":  56.3,     # Taurus ~26°
        "Neptune": 4.2,      # Aries ~4°
        "Pluto":   303.8,    # Capricorn ~3° (Aquarius ingress)
    }

    if not EPHEM_AVAILABLE:
        positions: dict[str, PlanetPosition] = {}
        for name, lon in FALLBACK_2026_03_20.items():
            sign, deg = longitude_to_sign(lon)
            positions[name] = PlanetPosition(
                name=name,
                longitude=round(lon, 4),
                sign=sign,
                sign_degree=deg,
            )
        return positions

    bodies: dict[str, ephem.Body] = {
        "Sun":     ephem.Sun(),
        "Moon":    ephem.Moon(),
        "Mercury": ephem.Mercury(),
        "Venus":   ephem.Venus(),
        "Mars":    ephem.Mars(),
        "Jupiter": ephem.Jupiter(),
        "Saturn":  ephem.Saturn(),
        "Uranus":  ephem.Uranus(),
        "Neptune": ephem.Neptune(),
        "Pluto":   ephem.Pluto(),
    }

    positions = {}
    for name, body in bodies.items():
        try:
            lon = _ephem_longitude(body, dt)
        except Exception:
            lon = FALLBACK_2026_03_20.get(name, 0.0)
        sign, deg = longitude_to_sign(lon)
        positions[name] = PlanetPosition(
            name=name, longitude=lon, sign=sign, sign_degree=deg
        )
    return positions


# ─────────────────────────────────────────────
# Formula Evaluation
# ─────────────────────────────────────────────

def evaluate_ju_su_ur(positions: dict[str, PlanetPosition]) -> TransitHit | None:
    """
    Evaluate the primary formula: Jupiter = Sun / Uranus

    Checks if Jupiter is conjunct or in hard aspect to the Sun/Uranus midpoint.

    Returns:
        TransitHit if formula is active within orb, else None.
    """
    import random

    if "Sun" not in positions or "Uranus" not in positions or "Jupiter" not in positions:
        return None

    sun_long = positions["Sun"].longitude
    ur_long = positions["Uranus"].longitude
    ju_long = positions["Jupiter"].longitude

    mp = build_midpoint("Sun", sun_long, "Uranus", ur_long)
    is_hit, aspect_angle, actual_orb = is_hard_aspect(ju_long, mp.midpoint_longitude)

    quote = random.choice(GRANDPA_BEAR_ADVICE)
    interp = FORMULA_INTERPRETATION.get("JU=SU/UR", "")

    return TransitHit(
        formula="JU = SU/UR",
        activating_planet="Jupiter",
        midpoint=mp,
        orb=actual_orb,
        aspect=aspect_angle,
        is_active=is_hit,
        interpretation=interp,
        grandpa_bear_quote=quote,
    )


def check_aries_ingress(dt: datetime | None = None) -> bool:
    """
    Return True if today is the Aries Ingress (Sun at 0° Aries).

    For 2026, this occurs on March 20.
    """
    if dt is None:
        dt = datetime.utcnow()
    return dt.month == 3 and dt.day == 20


def check_mercury_direct(positions: dict[str, PlanetPosition]) -> bool:
    """
    Heuristic: Mercury is stationing direct when it's in late Pisces / early Aries
    in early-to-mid March–April.

    For a full implementation, compare ephemeris positions over 3 days.
    Returns True based on the known 2026-03-20 station.
    """
    mercury = positions.get("Mercury")
    if mercury is None:
        return False
    # Mercury stationing direct at ~22° Pisces on 2026-03-20
    return mercury.sign == "Pisces" and 18 <= mercury.sign_degree <= 26


# ─────────────────────────────────────────────
# Daily Report
# ─────────────────────────────────────────────

def generate_daily_report(dt: datetime | None = None) -> DailyAstroReport:
    """
    Generate the full daily astrological report.

    Calculates all planet positions, evaluates the JU=SU/UR formula,
    and checks for special dates (Aries Ingress, Mercury Direct).

    Args:
        dt: Target datetime (UTC). Defaults to now.

    Returns:
        DailyAstroReport dataclass.
    """
    if dt is None:
        dt = datetime.utcnow()

    positions = get_planet_positions(dt)
    active_hits: list[TransitHit] = []

    ju_hit = evaluate_ju_su_ur(positions)
    if ju_hit:
        active_hits.append(ju_hit)

    aries = check_aries_ingress(dt)
    merc_direct = check_mercury_direct(positions)

    # Build summary
    summaries: list[str] = []
    if aries:
        summaries.append(
            "☀️ **Aries Ingress** (Sun 0° Aries): The astrological new year begins. "
            "This chart is read as the forecast template for the next 12 months."
        )
    if merc_direct:
        summaries.append(
            "☿ **Mercury Station Direct** (~22° Pisces): Communications, contracts, and "
            "tech sector clarity returns. Watch for gap-ups in MSFT, GOOGL, AAPL."
        )
    if ju_hit and ju_hit.is_active:
        summaries.append(
            f"⚡ **JU = SU/UR Active** (orb {ju_hit.orb:.1f}°): "
            f"Sudden expansive moves possible in tech. {ju_hit.grandpa_bear_quote}"
        )

    if not summaries:
        summaries.append("No major Uranian hits active today. Clean chart — follow the technicals.")

    return DailyAstroReport(
        date=dt.date(),
        planet_positions=positions,
        active_hits=active_hits,
        aries_ingress=aries,
        mercury_direct=merc_direct,
        summary="\n\n".join(summaries),
    )
