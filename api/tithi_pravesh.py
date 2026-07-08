"""
tithi_pravesh.py
Tithi Pravesh (lunar-based annual chart) calculation.

Method:
  Step 1 (month): find the window in target_year where transiting Sun is in
                  the SAME RASHI as natal Sun (rashi match, not exact-degree
                  Solar Return).
  Step 2 (day):   within that window, find the day where Tithi
                  (floor(Moon-Sun elongation / 12) + 1) matches natal Tithi.
  Step 3 (time):  binary search for the exact moment where the Moon-Sun
                  elongation equals the natal elongation.
  Step 4 (place): cast the resulting chart at BIRTHPLACE coordinates.
"""

import swisseph as swe

from ephemeris import (
    SIGNS, get_sidereal_longitude, get_all_positions_from_jd
)

# ── Small helpers ────────────────────────────────────────────────────────────

def _sun_sign_index(jd: float) -> int:
    sun_lon = get_sidereal_longitude(jd, swe.SUN)
    return int(sun_lon // 30) % 12


def _elongation(jd: float) -> float:
    sun_lon = get_sidereal_longitude(jd, swe.SUN)
    moon_lon = get_sidereal_longitude(jd, swe.MOON)
    return (moon_lon - sun_lon) % 360


def _tithi_number(jd: float) -> int:
    return int(_elongation(jd) // 12) + 1


def _wrapped_elong_diff(jd: float, target_elongation: float) -> float:
    """Signed difference (elongation(jd) - target), wrapped to (-180, 180]."""
    return ((_elongation(jd) - target_elongation + 180) % 360) - 180


def _jd_to_utc_str(jd: float) -> str:
    year, month, day, hour_frac = swe.revjul(jd, swe.GREG_CAL)
    hour = int(hour_frac)
    minute_frac = (hour_frac - hour) * 60
    minute = int(minute_frac)
    second = int(round((minute_frac - minute) * 60))
    if second == 60:
        second = 0
        minute += 1
    if minute == 60:
        minute = 0
        hour += 1
    return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d} UTC"


# ── Step 1: Sun rashi window ─────────────────────────────────────────────────

def _refine_sign_boundary(lo_jd: float, hi_jd: float, sign_index: int, entering: bool) -> float:
    """Binary-search the exact JD where Sun crosses into/out of sign_index.
    entering=True: lo is before the sign, hi is inside it -> returns crossing-in JD.
    entering=False: lo is inside the sign, hi is after it -> returns crossing-out JD.
    """
    for _ in range(25):
        mid = (lo_jd + hi_jd) / 2
        mid_match = _sun_sign_index(mid) == sign_index
        if entering:
            if mid_match:
                hi_jd = mid
            else:
                lo_jd = mid
        else:
            if mid_match:
                lo_jd = mid
            else:
                hi_jd = mid
    return hi_jd if entering else lo_jd


def find_sun_rashi_window(natal_sun_sign_index: int, target_year: int):
    """Scan (with 1-day coarse steps) for the window in target_year where the
    transiting Sun occupies the same sidereal rashi as the natal Sun. Returns
    (start_jd, end_jd) refined to a precise boundary."""
    step = 1.0
    scan_start = swe.julday(target_year - 1, 12, 1, 0.0)
    scan_end = swe.julday(target_year + 1, 2, 1, 0.0)

    windows = []
    jd = scan_start
    prev_match = _sun_sign_index(jd) == natal_sun_sign_index
    window_open_at = jd if prev_match else None
    jd += step

    while jd <= scan_end:
        cur_match = _sun_sign_index(jd) == natal_sun_sign_index
        if cur_match and not prev_match:
            window_open_at = jd
        elif not cur_match and prev_match and window_open_at is not None:
            windows.append((window_open_at, jd))
            window_open_at = None
        prev_match = cur_match
        jd += step

    if window_open_at is not None:
        windows.append((window_open_at, jd))

    if not windows:
        raise ValueError(
            f"Could not find a Sun-in-{SIGNS[natal_sun_sign_index]} window in {target_year}"
        )

    def _midpoint_year(window):
        y, _, _, _ = swe.revjul((window[0] + window[1]) / 2, swe.GREG_CAL)
        return y

    coarse_start, coarse_end = min(windows, key=lambda w: abs(_midpoint_year(w) - target_year))

    start_jd = _refine_sign_boundary(coarse_start - step, coarse_start, natal_sun_sign_index, entering=True)
    end_jd = _refine_sign_boundary(coarse_end - step, coarse_end, natal_sun_sign_index, entering=False)
    return start_jd, end_jd


# ── Step 2: Tithi day ────────────────────────────────────────────────────────

def find_tithi_day(window_start: float, window_end: float, natal_tithi: int):
    """Narrow the Sun-rashi window down to the day bracket spanning the full
    entry-to-exit span of natal Tithi (elongation is monotonically increasing,
    so the exact match is guaranteed to fall inside this bracket). Step is
    deliberately finer than a full day since a Tithi can be as short as
    ~19.5 hours."""
    step = 4.0 / 24.0  # 4 hours
    jd = window_start
    day_start = jd if _tithi_number(jd) == natal_tithi else None
    jd += step

    while jd <= window_end:
        cur_match = _tithi_number(jd) == natal_tithi
        if cur_match and day_start is None:
            day_start = jd - step
        elif not cur_match and day_start is not None:
            return max(window_start, day_start), min(window_end, jd)
        jd += step

    if day_start is not None:
        return max(window_start, day_start), min(window_end, jd)

    raise ValueError(f"Could not find matching Tithi #{natal_tithi} within the Sun-rashi window")


# ── Step 3: exact moment ─────────────────────────────────────────────────────

def find_exact_moment(day_start: float, day_end: float, natal_elongation: float) -> float:
    """Binary search for the precise JD where the Moon-Sun elongation equals
    natal_elongation, using ~20-30 min coarse steps to bracket the crossing."""
    step = 25.0 / 1440.0  # 25 minutes, in days

    jd = day_start
    prev_diff = _wrapped_elong_diff(jd, natal_elongation)
    next_jd = jd + step

    while next_jd <= day_end + step:
        cur_diff = _wrapped_elong_diff(next_jd, natal_elongation)
        crossed = (prev_diff <= 0 <= cur_diff) or (prev_diff >= 0 >= cur_diff)
        if crossed:
            lo_jd, hi_jd = jd, next_jd
            lo_diff = prev_diff
            for _ in range(30):
                mid_jd = (lo_jd + hi_jd) / 2
                mid_diff = _wrapped_elong_diff(mid_jd, natal_elongation)
                if (lo_diff <= 0 and mid_diff >= 0) or (lo_diff >= 0 and mid_diff <= 0):
                    hi_jd = mid_jd
                else:
                    lo_jd, lo_diff = mid_jd, mid_diff
            return (lo_jd + hi_jd) / 2
        jd = next_jd
        prev_diff = cur_diff
        next_jd = jd + step

    raise ValueError("Could not find the exact Tithi Pravesh moment within the Tithi day window")


# ── Orchestration ────────────────────────────────────────────────────────────

TITHI_ELONGATION_TOLERANCE_DEG = 0.05  # ~a few minutes of drift near a Tithi boundary

def calculate_tithi_pravesh(natal_jd: float, target_year: int, birth_lat: float, birth_lon: float) -> dict:
    natal_sun_lon = get_sidereal_longitude(natal_jd, swe.SUN)
    natal_moon_lon = get_sidereal_longitude(natal_jd, swe.MOON)
    natal_sun_sign_index = int(natal_sun_lon // 30) % 12
    natal_elongation = (natal_moon_lon - natal_sun_lon) % 360
    natal_tithi = int(natal_elongation // 12) + 1

    # Step 1
    window_start, window_end = find_sun_rashi_window(natal_sun_sign_index, target_year)

    # Steps 2-3: the Sun-rashi window (~30-31 days) can be slightly longer
    # than a synodic month (~29.5 days), so a Tithi occurrence right at the
    # window's edge may be a truncated leftover whose true elongation
    # crossing falls just outside the window. If a bracket doesn't actually
    # contain the crossing, keep scanning the remainder of the window for
    # the next (complete) occurrence.
    scan_from = window_start
    tp_jd = None
    while scan_from < window_end:
        day_start, day_end = find_tithi_day(scan_from, window_end, natal_tithi)
        try:
            tp_jd = find_exact_moment(day_start, day_end, natal_elongation)
            break
        except ValueError:
            scan_from = day_end

    if tp_jd is None:
        raise ValueError(
            f"Could not find the exact Tithi Pravesh moment for Tithi #{natal_tithi} "
            f"within the Sun-rashi window"
        )

    # ── Validation guards ────────────────────────────────────────────────────
    tp_sun_sign_index = _sun_sign_index(tp_jd)
    if tp_sun_sign_index != natal_sun_sign_index:
        raise ValueError(
            f"Tithi Pravesh validation failed: Sun rashi at TP moment "
            f"({SIGNS[tp_sun_sign_index]}) != natal Sun rashi ({SIGNS[natal_sun_sign_index]})"
        )

    tp_elongation = _elongation(tp_jd)
    tp_tithi = int(tp_elongation // 12) + 1
    if tp_tithi != natal_tithi:
        elong_diff = abs(_wrapped_elong_diff(tp_jd, natal_elongation))
        if elong_diff > TITHI_ELONGATION_TOLERANCE_DEG:
            raise ValueError(
                f"Tithi Pravesh validation failed: Tithi at TP moment ({tp_tithi}) "
                f"!= natal Tithi ({natal_tithi})"
            )

    # Step 4: cast at birthplace
    chart = get_all_positions_from_jd(tp_jd, birth_lat, birth_lon)

    return {
        "target_year": target_year,
        "tithi_pravesh_moment_utc": _jd_to_utc_str(tp_jd),
        "jd": tp_jd,
        "natal_sun_sign_index": natal_sun_sign_index,
        "natal_tithi": natal_tithi,
        "cast_at": {
            "latitude": birth_lat,
            "longitude": birth_lon,
            "note": "Cast at birthplace coordinates, not current residence"
        },
        "chart": chart
    }
