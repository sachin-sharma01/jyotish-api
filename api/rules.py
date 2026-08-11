"""
rules.py
Deterministic Jyotish rule engine.
Takes raw ephemeris positions → derives verified astrological facts.
NO language generation here — only facts that go into Claude's prompt.
"""

from ephemeris import (
    SIGNS, DASHA_ORDER, DASHA_YEARS,
    whole_sign_house, calculate_vimshottari
)
from jyotish_fundamentals import (
    SIGN_LORDS, EXALTATION, DEBILITATION, OWN_SIGNS, MOOLATRIKONA,
    NATURAL_BENEFICS, NATURAL_MALEFICS, PLANET_ASPECTS,
    KENDRA, TRIKONA, DUSTHANA, UPACHAYA,
    get_dignity, get_house_nature, houses_aspected_by, sign_lord,
)

# Jupiter's aspects (house numbers it aspects from its position)
JUPITER_ASPECTS = [1, 5, 7, 9]  # 1st (itself), 5th, 7th, 9th

# ── Main Rule Engine ───────────────────────────────────────────────────────────

def derive_facts(positions: dict, birth_date: str, birth_time: str,
                 married: bool) -> dict:
    """
    Takes raw ephemeris positions and derives all astrological facts.
    Returns a structured fact sheet — no language, only verified data.
    """

    asc = positions["Ascendant"]
    asc_sign_index = asc["sign_index"]
    asc_lord = sign_lord(asc_sign_index)

    # ── D1 House Placements ────────────────────────────────────────────────────
    d1_planets = {}
    for planet, data in positions.items():
        if planet == "Ascendant":
            continue
        sign_idx = data["sign_index"]
        house = whole_sign_house(sign_idx, asc_sign_index)
        dignity = get_dignity(planet, sign_idx)
        house_nature = get_house_nature(house)
        aspected_houses = houses_aspected_by(planet, house)

        d1_planets[planet] = {
            "sign": data["sign"],
            "sign_index": sign_idx,
            "sign_lord": sign_lord(sign_idx),
            "house": house,
            "house_nature": house_nature,
            "degree": data["degree"],
            "minute": data["minute"],
            "nakshatra": data["nakshatra"],
            "nakshatra_lord": data["nakshatra_lord"],
            "dignity": dignity,
            "aspected_houses": aspected_houses,
        }

    # ── Dasha ──────────────────────────────────────────────────────────────────
    moon_lon = positions["Moon"]["longitude"]
    dasha = calculate_vimshottari(moon_lon, birth_date, birth_time)

    current_md_lord = dasha["current_mahadasha"]["lord"] if dasha["current_mahadasha"] else None
    current_ad_lord = dasha["current_antardasha"]["lord"] if dasha["current_antardasha"] else None

    # Dasha lord placements in D1
    md_d1 = d1_planets.get(current_md_lord, {})
    ad_d1 = d1_planets.get(current_ad_lord, {})

    # ── Jupiter Transit into Cancer ────────────────────────────────────────────
    # Cancer = sign_index 3
    cancer_sign_index = 3
    jupiter_transit_house = whole_sign_house(cancer_sign_index, asc_sign_index)
    moon_sign_index = positions["Moon"]["sign_index"]
    jupiter_transit_house_from_moon = whole_sign_house(cancer_sign_index, moon_sign_index)

    # Houses Jupiter will aspect during Cancer transit (5th, 7th, 9th from transit house)
    jupiter_transit_aspects = []
    for offset in [5, 7, 9]:
        h = ((jupiter_transit_house - 1 + offset - 1) % 12) + 1
        jupiter_transit_aspects.append(h)

    # Which natal planets fall in houses Jupiter will aspect?
    aspected_natal_planets = {}
    for planet, data in d1_planets.items():
        if data["house"] in [jupiter_transit_house] + jupiter_transit_aspects:
            aspected_natal_planets[planet] = {
                "house": data["house"],
                "dignity": data["dignity"],
                "sign": data["sign"]
            }

    # Is transit Jupiter aspecting natal Jupiter?
    natal_jupiter_house = d1_planets.get("Jupiter", {}).get("house")
    transit_aspects_natal_jupiter = natal_jupiter_house in ([jupiter_transit_house] + jupiter_transit_aspects)

    # Jupiter transit house nature
    transit_house_nature = get_house_nature(jupiter_transit_house)

    # Transit lord of Cancer = Moon (Cancer's lord)
    transit_sign_lord = "Moon"
    moon_natal_house = d1_planets.get("Moon", {}).get("house")
    moon_natal_dignity = d1_planets.get("Moon", {}).get("dignity")

    # ── Yoga Detection ─────────────────────────────────────────────────────────
    yogas = []

    # Raj Yoga: lord of kendra + lord of trikona in same house or mutual aspect
    kendra_lords = set()
    trikona_lords = set()
    for h in KENDRA:
        # Sign occupying house h from ascendant
        house_sign_index = (asc_sign_index + h - 1) % 12
        kendra_lords.add(sign_lord(house_sign_index))
    for h in TRIKONA:
        house_sign_index = (asc_sign_index + h - 1) % 12
        trikona_lords.add(sign_lord(house_sign_index))

    raj_yoga_planets = kendra_lords & trikona_lords
    if raj_yoga_planets:
        yogas.append({
            "name": "Raj Yoga potential",
            "planets": list(raj_yoga_planets),
            "reason": "Planet(s) lord both kendra and trikona"
        })

    # Dhana Yoga: 2nd and 11th lords conjunct or in each other's house
    second_lord = sign_lord((asc_sign_index + 1) % 12)
    eleventh_lord = sign_lord((asc_sign_index + 10) % 12)
    if (d1_planets.get(second_lord, {}).get("house") == 11 or
            d1_planets.get(eleventh_lord, {}).get("house") == 2):
        yogas.append({
            "name": "Dhana Yoga",
            "planets": [second_lord, eleventh_lord],
            "reason": "2nd and 11th lords exchange or mutual placement"
        })

    # Jupiter in Kendra or Trikona (Hamsa Yoga if in own/exalted + kendra)
    jupiter_house = d1_planets.get("Jupiter", {}).get("house")
    jupiter_dignity = d1_planets.get("Jupiter", {}).get("dignity")
    if jupiter_house in KENDRA and jupiter_dignity in ["exalted", "own_sign", "moolatrikona"]:
        yogas.append({
            "name": "Hamsa Yoga",
            "planets": ["Jupiter"],
            "reason": f"Jupiter in Kendra (house {jupiter_house}) in {jupiter_dignity}"
        })

    # Viparita Raj Yoga: dusthana lord in dusthana
    for h in DUSTHANA:
        house_sign_index = (asc_sign_index + h - 1) % 12
        lord = sign_lord(house_sign_index)
        lord_house = d1_planets.get(lord, {}).get("house")
        if lord_house in DUSTHANA and lord_house != h:
            yogas.append({
                "name": "Viparita Raj Yoga",
                "planets": [lord],
                "reason": f"Lord of {h}th house in dusthana (house {lord_house})"
            })

    # ── Key House Lords ────────────────────────────────────────────────────────
    key_houses = {}
    for h in [1, 2, 4, 5, 7, 9, 10, 11]:
        house_sign_index = (asc_sign_index + h - 1) % 12
        lord = sign_lord(house_sign_index)
        lord_placement = d1_planets.get(lord, {})
        key_houses[h] = {
            "sign": SIGNS[house_sign_index],
            "lord": lord,
            "lord_house": lord_placement.get("house"),
            "lord_dignity": lord_placement.get("dignity"),
            "lord_sign": lord_placement.get("sign"),
        }

    # ── Married Life Analysis (only if married=True) ───────────────────────────
    married_analysis = None
    if married:
        seventh_lord = sign_lord((asc_sign_index + 6) % 12)
        seventh_lord_data = d1_planets.get(seventh_lord, {})
        # Is Jupiter transiting 7th house?
        jupiter_in_7th = jupiter_transit_house == 7
        # Does Jupiter aspect 7th house?
        jupiter_aspects_7th = 7 in ([jupiter_transit_house] + jupiter_transit_aspects)
        # Darakaraka (planet with lowest degree — simplified: check Venus for female, Jupiter for male)
        married_analysis = {
            "seventh_house_sign": SIGNS[(asc_sign_index + 6) % 12],
            "seventh_lord": seventh_lord,
            "seventh_lord_house": seventh_lord_data.get("house"),
            "seventh_lord_dignity": seventh_lord_data.get("dignity"),
            "jupiter_transits_7th": jupiter_in_7th,
            "jupiter_aspects_7th": jupiter_aspects_7th,
            "venus_house": d1_planets.get("Venus", {}).get("house"),
            "venus_dignity": d1_planets.get("Venus", {}).get("dignity"),
        }

    # ── Compile Fact Sheet ─────────────────────────────────────────────────────
    return {
        "ascendant": {
            "sign": asc["sign"],
            "sign_index": asc_sign_index,
            "degree": asc["degree"],
            "minute": asc["minute"],
            "lord": asc_lord,
            "asc_lord_house": d1_planets.get(asc_lord, {}).get("house"),
            "asc_lord_dignity": d1_planets.get(asc_lord, {}).get("dignity"),
            "nakshatra": asc["nakshatra"],
        },
        "moon_sign": positions["Moon"]["sign"],
        "moon_house": d1_planets["Moon"]["house"],
        "d1_planets": d1_planets,
        "key_house_lords": key_houses,
        "yogas_detected": yogas,
        "dasha": {
            "current_mahadasha": dasha["current_mahadasha"],
            "current_antardasha": dasha["current_antardasha"],
            "md_lord_d1_house": md_d1.get("house"),
            "md_lord_d1_dignity": md_d1.get("dignity"),
            "ad_lord_d1_house": ad_d1.get("house"),
            "ad_lord_d1_dignity": ad_d1.get("dignity"),
        },
        "jupiter_transit": {
            "entering": "Cancer",
            "date": "June 1, 2025",
            "duration": "June 2025 – June 2026",
            "jupiter_dignity_in_cancer": "exalted",
            "transit_house_from_ascendant": jupiter_transit_house,
            "transit_house_from_moon": jupiter_transit_house_from_moon,
            "transit_house_nature": transit_house_nature,
            "houses_jupiter_will_aspect": jupiter_transit_aspects,
            "natal_planets_in_transit_path": aspected_natal_planets,
            "transit_aspects_natal_jupiter": transit_aspects_natal_jupiter,
            "natal_jupiter_house": natal_jupiter_house,
            "cancer_lord_is": transit_sign_lord,
            "cancer_lord_natal_house": moon_natal_house,
            "cancer_lord_natal_dignity": moon_natal_dignity,
        },
        "married_analysis": married_analysis,
    }
