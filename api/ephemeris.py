"""
ephemeris.py
Pure Swiss Ephemeris calculations — no interpretation, just math.
Lahiri Ayanamsa | Whole Sign Houses
"""

import swisseph as swe
from datetime import datetime, timedelta

# ── Constants ──────────────────────────────────────────────────────────────────

PLANET_IDS = {
    "Sun":     swe.SUN,
    "Moon":    swe.MOON,
    "Mars":    swe.MARS,
    "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER,
    "Venus":   swe.VENUS,
    "Saturn":  swe.SATURN,
    "Rahu":    swe.MEAN_NODE,
}

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishtha", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"
]

NAKSHATRA_LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]

DASHA_YEARS = {
    "Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10,
    "Mars": 7, "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17
}

DASHA_ORDER = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]


def get_julian_day(date_str: str, time_str: str, tz_offset: float) -> float:
    fmt = "%Y-%m-%d %H:%M:%S" if time_str.count(":") == 2 else "%Y-%m-%d %H:%M"
    dt = datetime.strptime(f"{date_str} {time_str}", fmt)
    utc_dt = dt - timedelta(hours=tz_offset)
    return swe.julday(utc_dt.year, utc_dt.month, utc_dt.day,
                      utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0)


def get_sidereal_longitude(jd: float, planet_id: int) -> float:
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL
    result, _ = swe.calc_ut(jd, planet_id, flags)
    return result[0]


def get_ascendant(jd: float, lat: float, lon: float) -> float:
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    ayanamsa = swe.get_ayanamsa(jd)
    _, ascmc = swe.houses(jd, lat, lon, b'P')
    return (ascmc[0] - ayanamsa) % 360


def parse_longitude(lon: float) -> dict:
    sign_index = int(lon / 30) % 12
    deg_in_sign = lon % 30
    return {
        "longitude": round(lon, 4),
        "sign": SIGNS[sign_index],
        "sign_index": sign_index,       # 0-based (Aries=0)
        "sign_num": sign_index + 1,     # 1-based
        "degree": int(deg_in_sign),
        "minute": int((deg_in_sign % 1) * 60),
    }


def get_nakshatra_info(lon: float) -> dict:
    nak_size = 360 / 27
    nak_index = int(lon / nak_size) % 27
    pada = int((lon % nak_size) / (nak_size / 4)) + 1
    lord_index = nak_index % 9
    return {
        "nakshatra": NAKSHATRAS[nak_index],
        "nakshatra_index": nak_index,
        "pada": pada,
        "nakshatra_lord": NAKSHATRA_LORDS[lord_index]
    }


def whole_sign_house(planet_sign_index: int, asc_sign_index: int) -> int:
    """Whole sign house number (1-based)"""
    return ((planet_sign_index - asc_sign_index) % 12) + 1


def _parse_birth_dt(birth_date: str, birth_time: str) -> datetime:
    fmt = "%Y-%m-%d %H:%M:%S" if birth_time.count(":") == 2 else "%Y-%m-%d %H:%M"
    return datetime.strptime(f"{birth_date} {birth_time}", fmt)


def _md_periods(moon_lon: float, birth_dt: datetime) -> list:
    """9 Mahadashas (one full cycle) anchored at the first MD's true start."""
    nak_size = 360 / 27
    first_lord = NAKSHATRA_LORDS[(int(moon_lon / nak_size) % 27) % 9]
    fraction_elapsed = (moon_lon % nak_size) / nak_size
    start = birth_dt - timedelta(days=DASHA_YEARS[first_lord] * fraction_elapsed * 365.25)
    idx = DASHA_ORDER.index(first_lord)
    out = []
    for i in range(9):
        lord = DASHA_ORDER[(idx + i) % 9]
        years = DASHA_YEARS[lord]
        end = start + timedelta(days=years * 365.25)
        out.append({"level": "MD", "lord": lord, "start": start, "end": end,
                    "years": years, "md_lord": lord, "ad_lord": None})
        start = end
    return out


def _subdivide(parent: dict, level: str) -> list:
    """Split a period into 9 full-length children starting from the parent lord."""
    idx = DASHA_ORDER.index(parent["lord"])
    start = parent["start"]
    out = []
    for i in range(9):
        lord = DASHA_ORDER[(idx + i) % 9]
        years = parent["years"] * DASHA_YEARS[lord] / 120
        end = start + timedelta(days=years * 365.25)
        out.append({
            "level": level, "lord": lord, "start": start, "end": end, "years": years,
            "md_lord": parent["md_lord"],
            "ad_lord": lord if level == "AD" else parent["ad_lord"],
        })
        start = end
    return out


def vimshottari_tree(moon_lon: float, birth_date: str, birth_time: str,
                     range_start: datetime, range_end: datetime) -> list:
    """Return every MD/AD/PD period overlapping [range_start, range_end).
    Each item: {"level": "MD"|"AD"|"PD", "lord", "start", "end",
                "md_lord", "ad_lord"}  (start/end as datetime).
    Uses full-length subdivision anchored at each period's true start.
    Sub-period lengths: child_years = parent_years * DASHA_YEARS[child] / 120,
    children start from the parent lord and follow DASHA_ORDER."""
    birth_dt = _parse_birth_dt(birth_date, birth_time)

    def overlaps(p):
        return p["start"] < range_end and p["end"] > range_start

    def strip(p):
        return {k: p[k] for k in ("level", "lord", "start", "end", "md_lord", "ad_lord")}

    out = []
    for md in _md_periods(moon_lon, birth_dt):
        if not overlaps(md):
            continue
        out.append(strip(md))
        for ad in _subdivide(md, "AD"):
            if not overlaps(ad):
                continue
            out.append(strip(ad))
            for pd in _subdivide(ad, "PD"):
                if overlaps(pd):
                    out.append(strip(pd))
    return out


def calculate_vimshottari(moon_lon: float, birth_date: str, birth_time: str) -> dict:
    nak_size = 360 / 27
    nak_index = int(moon_lon / nak_size) % 27
    lord_index = nak_index % 9
    degree_in_nak = moon_lon % nak_size
    fraction_remaining = 1 - (degree_in_nak / nak_size)

    starting_lord = NAKSHATRA_LORDS[lord_index]
    starting_years = DASHA_YEARS[starting_lord] * fraction_remaining

    fmt = "%Y-%m-%d %H:%M:%S" if birth_time.count(":") == 2 else "%Y-%m-%d %H:%M"
    birth_dt = datetime.strptime(f"{birth_date} {birth_time}", fmt)
    now = datetime.now()

    dashas = []
    current_dt = birth_dt

    # First partial dasha
    end_dt = current_dt + timedelta(days=starting_years * 365.25)
    dashas.append({
        "lord": starting_lord,
        "start": current_dt.strftime("%Y-%m-%d"),
        "end": end_dt.strftime("%Y-%m-%d"),
        "years": round(starting_years, 2)
    })
    current_dt = end_dt

    # Remaining 8 dashas
    seq_start = (DASHA_ORDER.index(starting_lord) + 1) % 9
    for i in range(8):
        lord = DASHA_ORDER[(seq_start + i) % 9]
        years = DASHA_YEARS[lord]
        end_dt = current_dt + timedelta(days=years * 365.25)
        dashas.append({
            "lord": lord,
            "start": current_dt.strftime("%Y-%m-%d"),
            "end": end_dt.strftime("%Y-%m-%d"),
            "years": years
        })
        current_dt = end_dt

    # Find current mahadasha
    current_md = next((d for d in dashas
                       if datetime.strptime(d["start"], "%Y-%m-%d") <= now
                       <= datetime.strptime(d["end"], "%Y-%m-%d")), None)

    # Find current antardasha (full-length subdivision from the MD's true start)
    current_ad = None
    if current_md:
        for md in _md_periods(moon_lon, birth_dt):
            if md["lord"] != current_md["lord"] or not (md["start"] <= now <= md["end"]):
                continue
            for ad in _subdivide(md, "AD"):
                if ad["start"] <= now <= ad["end"]:
                    current_ad = {
                        "lord": ad["lord"],
                        "start": ad["start"].strftime("%Y-%m-%d"),
                        "end": ad["end"].strftime("%Y-%m-%d")
                    }
                    break
            break

    return {
        "sequence": dashas,
        "current_mahadasha": current_md,
        "current_antardasha": current_ad
    }


def get_all_positions(date_str: str, time_str: str, tz_offset: float,
                      lat: float, lon: float) -> dict:
    """Master function: returns raw positions for all planets + ascendant"""
    jd = get_julian_day(date_str, time_str, tz_offset)
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    positions = {}

    # Ascendant
    asc_lon = get_ascendant(jd, lat, lon)
    positions["Ascendant"] = {
        **parse_longitude(asc_lon),
        **get_nakshatra_info(asc_lon)
    }

    # Planets
    for name, pid in PLANET_IDS.items():
        p_lon = get_sidereal_longitude(jd, pid)
        positions[name] = {
            **parse_longitude(p_lon),
            **get_nakshatra_info(p_lon)
        }

    # Ketu = Rahu + 180
    ketu_lon = (positions["Rahu"]["longitude"] + 180) % 360
    positions["Ketu"] = {
        **parse_longitude(ketu_lon),
        **get_nakshatra_info(ketu_lon)
    }

    return {
        "jd": jd,
        "ayanamsa_lahiri": round(swe.get_ayanamsa(jd), 4),
        "positions": positions
    }


def get_all_positions_from_jd(jd: float, lat: float, lon: float) -> dict:
    """Same as get_all_positions() but takes a Julian Day directly, and
    includes whole-sign house number for each planet/Ascendant."""
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    positions = {}

    # Ascendant
    asc_lon = get_ascendant(jd, lat, lon)
    asc_info = parse_longitude(asc_lon)
    asc_sign_index = asc_info["sign_index"]
    positions["Ascendant"] = {
        **asc_info,
        **get_nakshatra_info(asc_lon),
        "house": whole_sign_house(asc_sign_index, asc_sign_index)
    }

    # Planets
    for name, pid in PLANET_IDS.items():
        p_lon = get_sidereal_longitude(jd, pid)
        p_info = parse_longitude(p_lon)
        positions[name] = {
            **p_info,
            **get_nakshatra_info(p_lon),
            "house": whole_sign_house(p_info["sign_index"], asc_sign_index)
        }

    # Ketu = Rahu + 180
    ketu_lon = (positions["Rahu"]["longitude"] + 180) % 360
    ketu_info = parse_longitude(ketu_lon)
    positions["Ketu"] = {
        **ketu_info,
        **get_nakshatra_info(ketu_lon),
        "house": whole_sign_house(ketu_info["sign_index"], asc_sign_index)
    }

    return {
        "jd": jd,
        "ayanamsa_lahiri": round(swe.get_ayanamsa(jd), 4),
        "positions": positions
    }
