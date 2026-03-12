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
    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    utc_dt = dt - timedelta(hours=tz_offset)
    return swe.julday(utc_dt.year, utc_dt.month, utc_dt.day,
                      utc_dt.hour + utc_dt.minute / 60.0)


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


def get_d10_sign_index(natal_longitude: float) -> int:
    """
    D10 Dashamsha calculation (Parashari method)
    Odd signs: count from same sign
    Even signs: count from 9th sign
    """
    sign_index = int(natal_longitude / 30) % 12
    degree_in_sign = natal_longitude % 30
    part = int(degree_in_sign / 3)  # 0-9

    # In Jyotish, signs are odd/even by rashi number (Aries=1=odd, Taurus=2=even...)
    rashi_num = sign_index + 1  # 1-based
    if rashi_num % 2 == 1:  # Odd rashi
        d10_sign = (sign_index * 10 + part) % 12
    else:  # Even rashi
        d10_sign = (sign_index * 10 + part + 8) % 12
    return d10_sign


def calculate_vimshottari(moon_lon: float, birth_date: str, birth_time: str) -> dict:
    nak_size = 360 / 27
    nak_index = int(moon_lon / nak_size) % 27
    lord_index = nak_index % 9
    degree_in_nak = moon_lon % nak_size
    fraction_remaining = 1 - (degree_in_nak / nak_size)

    starting_lord = NAKSHATRA_LORDS[lord_index]
    starting_years = DASHA_YEARS[starting_lord] * fraction_remaining

    birth_dt = datetime.strptime(f"{birth_date} {birth_time}", "%Y-%m-%d %H:%M")
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

    # Find current antardasha
    current_ad = None
    if current_md:
        md_start = datetime.strptime(current_md["start"], "%Y-%m-%d")
        md_lord_idx = DASHA_ORDER.index(current_md["lord"])
        ad_dt = md_start
        for i in range(9):
            ad_lord = DASHA_ORDER[(md_lord_idx + i) % 9]
            ad_years = (DASHA_YEARS[ad_lord] / 120) * current_md["years"]
            ad_end = ad_dt + timedelta(days=ad_years * 365.25)
            if ad_dt <= now <= ad_end:
                current_ad = {
                    "lord": ad_lord,
                    "start": ad_dt.strftime("%Y-%m-%d"),
                    "end": ad_end.strftime("%Y-%m-%d")
                }
                break
            ad_dt = ad_end

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
