"""
jyotish_fundamentals.py
Reusable Jyotish reference tables and pure lookup helpers — no product-specific
business logic. Shared by the Jupiter Transit rule engine (rules.py) and the
Tithi Pravesh rule engine (tithi_pravesh_rules.py), and by any future product.
"""

# ── Jyotish Reference Tables ───────────────────────────────────────────────────

# Sign lords (0-based sign index)
SIGN_LORDS = {
    0: "Mars",      # Aries
    1: "Venus",     # Taurus
    2: "Mercury",   # Gemini
    3: "Moon",      # Cancer
    4: "Sun",       # Leo
    5: "Mercury",   # Virgo
    6: "Venus",     # Libra
    7: "Mars",      # Scorpio
    8: "Jupiter",   # Sagittarius
    9: "Saturn",    # Capricorn
    10: "Saturn",   # Aquarius
    11: "Jupiter",  # Pisces
}

# Exaltation signs (0-based)
EXALTATION = {
    "Sun": 0,       # Aries
    "Moon": 1,      # Taurus
    "Mars": 9,      # Capricorn
    "Mercury": 5,   # Virgo
    "Jupiter": 3,   # Cancer ← exalted!
    "Venus": 11,    # Pisces
    "Saturn": 6,    # Libra
    "Rahu": 1,      # Taurus (Parashari)
    "Ketu": 7,      # Scorpio (Parashari)
}

# Debilitation signs (0-based)
DEBILITATION = {
    "Sun": 6,       # Libra
    "Moon": 7,      # Scorpio
    "Mars": 3,      # Cancer
    "Mercury": 11,  # Pisces
    "Jupiter": 9,   # Capricorn
    "Venus": 5,     # Virgo
    "Saturn": 0,    # Aries
    "Rahu": 7,      # Scorpio
    "Ketu": 1,      # Taurus
}

# Own signs (0-based)
OWN_SIGNS = {
    "Sun":     [4],
    "Moon":    [3],
    "Mars":    [0, 7],
    "Mercury": [2, 5],
    "Jupiter": [8, 11],
    "Venus":   [1, 6],
    "Saturn":  [9, 10],
}

# Moolatrikona signs (0-based)
MOOLATRIKONA = {
    "Sun": 4,       # Leo
    "Moon": 1,      # Taurus (0-20 deg)
    "Mars": 0,      # Aries
    "Mercury": 2,   # Gemini
    "Jupiter": 8,   # Sagittarius
    "Venus": 6,     # Libra
    "Saturn": 9,    # Aquarius (actually Aquarius=10, Capricorn=9 — let's use Aquarius)
}

# Natural benefics / malefics
NATURAL_BENEFICS = ["Jupiter", "Venus", "Moon", "Mercury"]
NATURAL_MALEFICS = ["Sun", "Mars", "Saturn", "Rahu", "Ketu"]

# Kendra houses
KENDRA = [1, 4, 7, 10]

# Trikona houses
TRIKONA = [1, 5, 9]

# Dusthana houses
DUSTHANA = [6, 8, 12]

# Upachaya houses
UPACHAYA = [3, 6, 10, 11]

# All planet aspects: {planet: [houses it aspects from its position]}
PLANET_ASPECTS = {
    "Sun":     [1, 7],
    "Moon":    [1, 7],
    "Mars":    [1, 4, 7, 8],
    "Mercury": [1, 7],
    "Jupiter": [1, 5, 7, 9],
    "Venus":   [1, 7],
    "Saturn":  [1, 3, 7, 10],
    "Rahu":    [1, 5, 7, 9],
    "Ketu":    [1, 5, 7, 9],
}

# Naisargika Maitri (natural friendship)
NAISARGIKA_MAITRI = {
    "Sun":     {"friends": ["Moon", "Mars", "Jupiter"], "neutral": ["Mercury"], "enemies": ["Venus", "Saturn"]},
    "Moon":    {"friends": ["Sun", "Mercury"], "neutral": ["Mars", "Jupiter", "Venus", "Saturn"], "enemies": []},
    "Mars":    {"friends": ["Sun", "Moon", "Jupiter"], "neutral": ["Venus", "Saturn"], "enemies": ["Mercury"]},
    "Mercury": {"friends": ["Sun", "Venus"], "neutral": ["Mars", "Jupiter", "Saturn"], "enemies": ["Moon"]},
    "Jupiter": {"friends": ["Sun", "Moon", "Mars"], "neutral": ["Saturn"], "enemies": ["Mercury", "Venus"]},
    "Venus":   {"friends": ["Mercury", "Saturn"], "neutral": ["Mars", "Jupiter"], "enemies": ["Sun", "Moon"]},
    "Saturn":  {"friends": ["Mercury", "Venus"], "neutral": ["Jupiter"], "enemies": ["Sun", "Moon", "Mars"]},
}

# ── Helper Functions ───────────────────────────────────────────────────────────

def get_dignity(planet: str, sign_index: int) -> str:
    if sign_index == EXALTATION.get(planet):
        return "exalted"
    if sign_index == DEBILITATION.get(planet):
        return "debilitated"
    if sign_index in OWN_SIGNS.get(planet, []):
        if sign_index == MOOLATRIKONA.get(planet):
            return "moolatrikona"
        return "own_sign"
    return "neutral"


def get_house_nature(house: int) -> list:
    natures = []
    if house in KENDRA:
        natures.append("kendra")
    if house in TRIKONA:
        natures.append("trikona")
    if house in DUSTHANA:
        natures.append("dusthana")
    if house in UPACHAYA:
        natures.append("upachaya")
    if not natures:
        natures.append("neutral")
    return natures


def houses_aspected_by(planet: str, planet_house: int) -> list:
    """Houses aspected by `planet` from `planet_house`. PLANET_ASPECTS'
    offset 1 always resolves back to planet_house itself (self-reference,
    not a real aspect on another house), so it's excluded from the result."""
    aspect_offsets = PLANET_ASPECTS.get(planet, [1, 7])
    aspected = []
    for offset in aspect_offsets:
        h = ((planet_house - 1 + offset - 1) % 12) + 1
        if h != planet_house:
            aspected.append(h)
    return list(set(aspected))


def sign_lord(sign_index: int) -> str:
    return SIGN_LORDS[sign_index % 12]


def get_full_dignity(planet: str, sign_index: int) -> str:
    """Extends get_dignity() with a 'friendly'/'enemy' tier for signs that
    are neither own/exalted/debilitated. Used by Tithi Pravesh rules
    R13 and R16."""
    base = get_dignity(planet, sign_index)
    if base != "neutral":
        return base
    lord = sign_lord(sign_index)
    maitri = NAISARGIKA_MAITRI.get(planet, {})
    if lord in maitri.get("friends", []):
        return "friendly"
    if lord in maitri.get("enemies", []):
        return "enemy"
    return "neutral"
