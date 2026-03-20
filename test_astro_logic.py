"""
tests/test_astro_logic.py
-------------------------
Unit tests for core/astro_logic.py
Focuses on the mathematical purity of midpoint and aspect calculations.
"""

from __future__ import annotations

import pytest
from core.astro_logic import (
    angular_distance,
    build_midpoint,
    calculate_midpoint,
    check_aries_ingress,
    is_hard_aspect,
    longitude_to_sign,
    normalize_degrees,
)
from datetime import datetime


class TestNormalize:
    def test_positive_wraps(self):
        assert normalize_degrees(370.0) == pytest.approx(10.0)

    def test_negative_wraps(self):
        assert normalize_degrees(-10.0) == pytest.approx(350.0)

    def test_zero_stays(self):
        assert normalize_degrees(0.0) == pytest.approx(0.0)

    def test_360_becomes_0(self):
        assert normalize_degrees(360.0) == pytest.approx(0.0)


class TestAngularDistance:
    def test_same_point(self):
        assert angular_distance(45.0, 45.0) == pytest.approx(0.0)

    def test_opposite(self):
        assert angular_distance(0.0, 180.0) == pytest.approx(180.0)

    def test_short_arc(self):
        # 10° apart
        assert angular_distance(5.0, 355.0) == pytest.approx(10.0)

    def test_result_max_180(self):
        for a in [0, 45, 90, 180, 270, 355]:
            for b in [0, 45, 90, 180, 270, 355]:
                assert angular_distance(float(a), float(b)) <= 180.0


class TestMidpoint:
    def test_simple_midpoint(self):
        # 0° and 90° → midpoint at 45°
        mp = calculate_midpoint(0.0, 90.0)
        assert mp == pytest.approx(45.0)

    def test_wrap_around_midpoint(self):
        # 350° and 10° → midpoint at 0° (or 180° for far arc)
        mp = calculate_midpoint(350.0, 10.0)
        # Near arc midpoint = 0°
        assert mp == pytest.approx(0.0) or mp == pytest.approx(180.0)

    def test_identical_points(self):
        mp = calculate_midpoint(120.0, 120.0)
        assert mp == pytest.approx(120.0)

    def test_midpoint_in_range(self):
        for a in [0, 45, 90, 180, 270]:
            for b in [45, 135, 225, 315]:
                mp = calculate_midpoint(float(a), float(b))
                assert 0.0 <= mp < 360.0


class TestLongitudeToSign:
    def test_aries(self):
        sign, deg = longitude_to_sign(0.0)
        assert sign == "Aries"
        assert deg == pytest.approx(0.0)

    def test_taurus(self):
        sign, deg = longitude_to_sign(35.0)
        assert sign == "Taurus"
        assert deg == pytest.approx(5.0)

    def test_pisces_end(self):
        sign, deg = longitude_to_sign(359.9)
        assert sign == "Pisces"

    def test_all_twelve_signs(self):
        signs = [
            "Aries", "Taurus", "Gemini", "Cancer",
            "Leo", "Virgo", "Libra", "Scorpio",
            "Sagittarius", "Capricorn", "Aquarius", "Pisces",
        ]
        for i, expected_sign in enumerate(signs):
            sign, _ = longitude_to_sign(float(i * 30 + 1))
            assert sign == expected_sign


class TestHardAspects:
    def test_conjunction_0(self):
        hit, aspect, orb = is_hard_aspect(90.0, 90.0)
        assert hit is True
        assert aspect == pytest.approx(0.0)

    def test_square_90(self):
        hit, aspect, orb = is_hard_aspect(180.0, 90.0)
        assert hit is True
        assert aspect == pytest.approx(90.0)

    def test_semisquare_45(self):
        hit, aspect, orb = is_hard_aspect(135.0, 90.0)
        assert hit is True
        assert aspect == pytest.approx(45.0)

    def test_opposition_180(self):
        hit, aspect, orb = is_hard_aspect(270.0, 90.0)
        assert hit is True
        assert aspect == pytest.approx(180.0)

    def test_trine_120_not_hard(self):
        """120° is a soft aspect — should NOT trigger."""
        hit, _, _ = is_hard_aspect(210.0, 90.0)
        assert hit is False

    def test_within_orb(self):
        """1° off a conjunction should still trigger with default 2° orb."""
        hit, aspect, orb = is_hard_aspect(91.0, 90.0)
        assert hit is True
        assert orb <= 2.0

    def test_outside_orb(self):
        """3° off should not trigger with default 2° orb."""
        hit, _, _ = is_hard_aspect(93.0, 90.0, orb=2.0)
        assert hit is False


class TestAriesIngress:
    def test_march_20_is_ingress(self):
        dt = datetime(2026, 3, 20, 12, 0)
        assert check_aries_ingress(dt) is True

    def test_march_21_is_not(self):
        dt = datetime(2026, 3, 21, 12, 0)
        assert check_aries_ingress(dt) is False

    def test_april_20_is_not(self):
        dt = datetime(2026, 4, 20, 12, 0)
        assert check_aries_ingress(dt) is False
