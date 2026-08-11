"""
tithi_pravesh_rules.py
Deterministic Tithi Pravesh rule engine (R1-R18, M1-M2).
Takes the D1 fact sheet + Phase 2-enriched TP chart -> structured findings.
NO language generation here — prediction_text is a short factual note, not
prose; narrative writing happens downstream (n8n Claude node).
"""

import calendar
from datetime import date

from ephemeris import SIGNS, whole_sign_house
from jyotish_fundamentals import NATURAL_MALEFICS, NATURAL_BENEFICS

MARRIAGE_KEYWORDS = ["marry", "marriage", "wedding", "wed ", "spouse", "partner", "relationship"]

PLANET_SIGNIFICATIONS = {
    "Sun": "father, authority, government, health/vitality, self-confidence, career status",
    "Moon": "mother, mind/emotions, home, public image, comfort",
    "Mars": "siblings, courage, property/land, conflict, accidents, energy",
    "Mercury": "communication, business, intellect, education, short travel",
    "Jupiter": "wisdom, teaching/learning, wealth growth, children, marriage (for women), spirituality",
    "Venus": "money, relationships/marriage, luxury, comfort, creativity",
    "Saturn": "discipline, delays, hard work, longevity, career structure, chronic issues",
    "Rahu": "obsession, foreign connections, sudden gains, unconventional paths, illusion",
    "Ketu": "detachment, spirituality, losses, past-life matters, isolation",
}

GOOD_DIGNITIES = ("exalted", "own_sign", "moolatrikona", "friendly")
BAD_DIGNITIES = ("debilitated", "enemy")


# ── Shared helpers ───────────────────────────────────────────────────────────

def _finding(rule_id, title, prediction_text, houses_involved, planets_involved,
             severity, priority_tier, **extra):
    d = {
        "rule_id": rule_id,
        "title": title,
        "prediction_text": prediction_text,
        "houses_involved": houses_involved,
        "planets_involved": planets_involved,
        "severity": severity,
        "priority_tier": priority_tier,
    }
    d.update(extra)
    return d


def _afflicting_malefics(influences):
    """Distinct malefics conjunct or aspecting, per §0.3."""
    return sorted({i["planet"] for i in influences if i["nature"] == "malefic"})


def _supporting_benefics(influences, relation=None):
    return sorted({i["planet"] for i in influences
                   if i["nature"] == "benefic" and (relation is None or i["relation"] == relation)})


def _severity_from_count(n):
    if n >= 3:
        return "significant"
    if n == 2:
        return "moderate"
    return "mild"


def _check_multi_malefic_aspect(house_summary, house):
    """R2 / M2 — houses receiving aspects from 2+ malefics."""
    malefics = house_summary[str(house)]["aspecting_malefics"]
    return malefics if len(malefics) >= 2 else None


def _check_multi_malefic_conjunct(house_summary, house):
    """M1 — houses with 2+ malefics conjunct (occupying)."""
    occupants = house_summary[str(house)]["occupants"]
    malefics = [p for p in occupants if p in NATURAL_MALEFICS]
    return malefics if len(malefics) >= 2 else None


def _check_afflicted_occupant(tp_positions, house_summary, house):
    """Generalized R8 — occupants of `house` that are themselves afflicted.
    Returns list of (planet, afflicting_malefics)."""
    results = []
    for p in house_summary[str(house)]["occupants"]:
        malefics = _afflicting_malefics(tp_positions[p]["influences"])
        if malefics:
            results.append((p, malefics))
    return results


def _check_benefic_occupant(tp_positions, house_summary, house):
    """Generalized R11 — benefic(s) occupying `house`."""
    return [p for p in house_summary[str(house)]["occupants"] if p in NATURAL_BENEFICS]


def _check_malefic_occupant(tp_positions, house_summary, house):
    """Generalized R12 — malefic(s) occupying `house`, flagging the own-sign exception.
    Returns list of (planet, own_sign_exception)."""
    results = []
    for p in house_summary[str(house)]["occupants"]:
        if p in NATURAL_MALEFICS:
            exception = tp_positions[p]["dignity"] in ("own_sign", "moolatrikona")
            results.append((p, exception))
    return results


def _client_age(birth_date_str, target_year):
    try:
        return target_year - int(birth_date_str[:4])
    except (ValueError, TypeError):
        return None


def _mentions_marriage_interest(text):
    t = (text or "").lower()
    return any(k in t for k in MARRIAGE_KEYWORDS)


# ── Year-level rules (Tier 1: Lagna/Lagnesh-anchored) ───────────────────────

def _r1(ctx):
    result = whole_sign_house(ctx["tp_asc_sign_index"], ctx["d1_asc_sign_index"])
    if result in (2, 12):
        relationship = "2-12 relationship (Dwidwadasha)"
    elif result in (6, 8):
        relationship = "6-8 relationship (Shadashtaka)"
    else:
        return None

    occupants = [p for p, d in ctx["d1_fact_sheet"]["d1_planets"].items() if d["house"] == result]
    malefic_occupants = [p for p in occupants if p in NATURAL_MALEFICS]
    benefic_occupants = [p for p in occupants if p in NATURAL_BENEFICS]
    if malefic_occupants:
        note = f"D1 house {result} occupied by malefic(s) {', '.join(malefic_occupants)} — raised expenses/financial loss likely."
    elif benefic_occupants:
        note = f"D1 house {result} occupied by benefic(s) {', '.join(benefic_occupants)} — travel opportunity likely."
    else:
        note = f"D1 house {result} has no occupants."
    text = f"TP Lagna falls in D1 house {result} — {relationship}. {note} Generally not favorable overall."
    return _finding("R1", "TP Lagna rashi's house-position in D1", text, [result], occupants, "moderate", 1)


def _r15(ctx):
    result = whole_sign_house(ctx["tp_asc_sign_index"], ctx["d1_asc_sign_index"])
    mapping = {
        5: "5-9 relationship (trikona)", 9: "5-9 relationship (trikona)",
        3: "3-11 relationship (upachaya/growth)", 11: "3-11 relationship (upachaya/growth)",
        4: "4-10 relationship (kendra)", 10: "4-10 relationship (kendra)",
    }
    if result not in mapping:
        return None
    text = f"TP Lagna falls in D1 house {result} — {mapping[result]}. Favorable, new gains possible."
    return _finding("R15", "TP Lagna - D1 Lagna favorable relationship", text, [result], [], "moderate", 1)


def _r3_r9(ctx):
    occupants = ctx["house_summary"]["1"]["occupants"]
    if not occupants:
        return None

    house1_malefics = set(ctx["house_summary"]["1"]["aspecting_malefics"]) | {
        p for p in occupants if p in NATURAL_MALEFICS
    }
    lagnesh_pos = ctx["tp_lagnesh_position"]
    lagnesh_malefics = set(_afflicting_malefics(lagnesh_pos["influences"])) if lagnesh_pos else set()
    combined = sorted(house1_malefics | lagnesh_malefics)

    parts = [f"TP Lagna occupied by {', '.join(occupants)}."]
    if "Saturn" in occupants:
        parts.append("Saturn's own nature brings delays and hard work — growth still happens, "
                      "through struggle/discipline rather than ease.")

    if len(combined) >= 2:
        parts.append(f"Lagna/Lagnesh afflicted by {len(combined)} malefics: {', '.join(combined)} "
                      f"— hardships dominate over growth.")
        severity = _severity_from_count(len(combined))
    elif len(combined) == 1:
        parts.append(f"Lagna/Lagnesh under a single malefic influence ({combined[0]}) — present/felt, "
                      f"but overall effect still leans toward growth/support.")
        severity = "mild"
    else:
        parts.append("Unafflicted — significations supported and tend to grow.")
        severity = "moderate"

    text = " ".join(parts)
    return _finding("R3/R9", "Planet occupying TP Lagna", text, [1], occupants + combined, severity, 1)


def _r4(ctx):
    pos = ctx["tp_lagnesh_position"]
    if not pos:
        return None
    dignity = pos["dignity"]
    nature = pos["house_nature"]
    good_dignity = dignity in GOOD_DIGNITIES
    bad_dignity = dignity in BAD_DIGNITIES
    good_house = "kendra" in nature or "trikona" in nature
    bad_house = "dusthana" in nature

    if good_dignity and good_house:
        verdict, severity = "favorable", "significant"
    elif bad_dignity and bad_house:
        verdict, severity = "unfavorable", "significant"
    elif bad_dignity or bad_house:
        verdict, severity = "mixed, leaning unfavorable", "moderate"
    elif good_dignity or good_house:
        verdict, severity = "favorable", "moderate"
    else:
        verdict, severity = "average", "mild"

    text = (f"TP Lagnesh {ctx['tp_lagnesh']} is {dignity} in house {pos['house']} "
            f"({', '.join(nature)}) — {verdict} year overall (primary barometer).")
    return _finding("R4", "TP Lagnesh placement quality", text, [pos["house"]], [ctx["tp_lagnesh"]], severity, 1)


def _r5(ctx):
    pos = ctx["tp_lagnesh_position"]
    if not pos:
        return None
    conjunct = [i["planet"] for i in pos["influences"]
                if i["relation"] == "conjunct" and i["planet"] in ("Rahu", "Ketu")]
    if not conjunct:
        return None
    text = (f"TP Lagnesh {ctx['tp_lagnesh']} conjunct {', '.join(conjunct)} in TP house {pos['house']} "
            f"— sudden shifts/changes likely this year.")
    return _finding("R5", "TP Lagnesh on the Rahu-Ketu axis", text, [pos["house"]],
                     [ctx["tp_lagnesh"]] + conjunct, "moderate", 1)


def _r6(ctx):
    pos = ctx["tp_lagnesh_position"]
    if not pos:
        return None
    malefics = _afflicting_malefics(pos["influences"])
    if not malefics:
        text = f"TP Lagnesh {ctx['tp_lagnesh']} unafflicted — smooth year regarding Lagnesh."
        return _finding("R6", "TP Lagnesh affliction count", text, [pos["house"]], [ctx["tp_lagnesh"]], "mild", 1)
    text = f"TP Lagnesh {ctx['tp_lagnesh']} afflicted by {len(malefics)} malefic(s): {', '.join(malefics)}."
    return _finding("R6", "TP Lagnesh affliction count", text, [pos["house"]],
                     [ctx["tp_lagnesh"]] + malefics, _severity_from_count(len(malefics)), 1)


def _r7(ctx):
    pos = ctx["tp_lagnesh_position"]
    if not pos:
        return None
    malefics = _afflicting_malefics(pos["influences"])
    if len(malefics) < 2:
        return None
    text = (f"TP Lagnesh {ctx['tp_lagnesh']} afflicted by {len(malefics)} malefics: {', '.join(malefics)} "
            f"— health problems flagged for the year.")
    return _finding("R7", "TP Lagnesh double-malefic affliction - health", text, [pos["house"]],
                     [ctx["tp_lagnesh"]] + malefics, _severity_from_count(len(malefics)), 1)


def _r13(ctx):
    findings = []
    pos = ctx["d1_lagnesh_tp_position"]
    if not pos or pos["house"] != 7:
        return findings
    if pos["dignity"] not in GOOD_DIGNITIES:
        return findings

    text = (f"D1 Lagnesh {ctx['d1_lagnesh']} placed in TP house 7, {pos['dignity']} in {pos['sign']} "
            f"— favorable for business and relationships this year.")
    findings.append(_finding("R13", "D1 Lagnesh in TP 7th house", text, [7], [ctx["d1_lagnesh"]], "moderate", 1))

    tp_lagnesh_pos = ctx["tp_lagnesh_position"]
    if tp_lagnesh_pos and tp_lagnesh_pos["house"] == 7 and not ctx["client_married"]:
        age = _client_age(ctx["client_birth_date"], ctx["target_year"])
        interested = _mentions_marriage_interest(ctx["personal_concern"]) or (age is not None and age < 37)
        if interested:
            marriage_text = (f"Both D1 Lagnesh {ctx['d1_lagnesh']} and TP Lagnesh {ctx['tp_lagnesh']} in TP house 7 "
                              f"— high potential for marriage this year.")
            findings.append(_finding("R13-marriage", "D1 Lagnesh + TP Lagnesh in TP 7th house - marriage potential",
                                      marriage_text, [7], sorted({ctx["d1_lagnesh"], ctx["tp_lagnesh"]}),
                                      "significant", 1))
    return findings


def _r14(ctx):
    d1_asc = ctx["d1_fact_sheet"]["ascendant"]
    tp_asc = ctx["tp_positions"]["Ascendant"]
    if d1_asc["sign_index"] != tp_asc["sign_index"]:
        return None
    d1_deg = d1_asc["degree"] + d1_asc["minute"] / 60.0
    tp_deg = tp_asc["degree"] + tp_asc["minute"] / 60.0
    diff = abs(d1_deg - tp_deg)
    if diff > 1.0:
        return None
    d1_moon_nak = ctx["d1_fact_sheet"]["d1_planets"]["Moon"]["nakshatra"]
    tp_moon_nak = ctx["tp_positions"]["Moon"]["nakshatra"]
    if d1_moon_nak != tp_moon_nak:
        return None
    text = (f"D1 Lagna and TP Lagna both in {tp_asc['sign']} within {diff:.2f}°, "
            f"Moon in {tp_moon_nak} in both charts — entire year flagged as potentially problematic.")
    return _finding("R14", "D1 Lagna = TP Lagna (tight match)", text, [1], ["Moon"], "significant", 1)


def _r16(ctx):
    pos = ctx["d1_lagnesh_tp_position"]
    if not pos:
        return None
    good_dignity = pos["dignity"] in GOOD_DIGNITIES
    good_house = pos["house"] in (1, 4, 5, 7, 9, 10)
    if not (good_dignity or good_house):
        return None
    text = (f"D1 Lagnesh {ctx['d1_lagnesh']} is {pos['dignity']} in TP house {pos['house']} "
            f"({', '.join(pos['house_nature'])}) — gains strength for the year.")
    return _finding("R16", "D1 Lagnesh gaining strength in the TP chart", text, [pos["house"]],
                     [ctx["d1_lagnesh"]], "moderate", 1)


def _r17(ctx):
    pos = ctx["d1_lagnesh_tp_position"]
    if not pos:
        return None
    benefics = _supporting_benefics(pos["influences"], relation="aspect")
    if not benefics:
        return None
    text = (f"D1 Lagnesh {ctx['d1_lagnesh']} aspected by benefic(s) {', '.join(benefics)} in the TP chart "
            f"— positive for the year.")
    return _finding("R17", "D1 Lagnesh aspected by benefics", text, [pos["house"]],
                     [ctx["d1_lagnesh"]] + benefics, _severity_from_count(len(benefics)), 1)


def _r18(ctx):
    pos = ctx["tp_lagnesh_position"]
    if not pos:
        return None
    benefics = _supporting_benefics(pos["influences"], relation="aspect")
    occupant_benefics = [p for p in ctx["house_summary"]["1"]["occupants"] if p in NATURAL_BENEFICS]
    if not benefics and not occupant_benefics:
        return None
    parts = []
    if benefics:
        parts.append(f"TP Lagnesh {ctx['tp_lagnesh']} aspected by benefic(s) {', '.join(benefics)}")
    if occupant_benefics:
        parts.append(f"benefic(s) {', '.join(occupant_benefics)} occupy TP Lagna itself")
    text = "; ".join(parts) + " — supportive, positive year (counterpart to R6)."
    involved = sorted(set([ctx["tp_lagnesh"]] + benefics + occupant_benefics))
    severity = _severity_from_count(max(len(benefics), len(occupant_benefics), 1))
    return _finding("R18", "TP Lagnesh aspected by benefics", text, [1, pos["house"]], involved, severity, 1)


# ── Year-level rules (Tier 2: house/planet-specific) ────────────────────────

def _r2_for_house(ctx, house):
    malefics = _check_multi_malefic_aspect(ctx["house_summary"], house)
    if not malefics:
        return None
    text = (f"TP house {house} receives aspects from {len(malefics)} malefics: {', '.join(malefics)} "
            f"— that house's significations suffer this year.")
    return _finding("R2", "TP houses under multi-malefic aspect", text, [house], malefics,
                     _severity_from_count(len(malefics)), 2)


def _r8(ctx):
    afflicted = _check_afflicted_occupant(ctx["tp_positions"], ctx["house_summary"], 4)
    if not afflicted:
        return None
    text_parts, planets_involved = [], []
    for p, malefics in afflicted:
        text_parts.append(f"{p} (afflicted by {', '.join(malefics)}) — significations affected: "
                           f"{PLANET_SIGNIFICATIONS.get(p, '')}")
        planets_involved.append(p)
        planets_involved.extend(malefics)
    text = "TP house 4 afflicted planet(s): " + "; ".join(text_parts)
    max_count = max(len(m) for _, m in afflicted)
    return _finding("R8", "Afflicted planet in TP 4th house", text, [4],
                     sorted(set(planets_involved)), _severity_from_count(max_count), 2)


def _r10_for_rashi(ctx, house):
    malefics = ctx["house_summary"][str(house)]["aspecting_malefics"]
    if len(malefics) < 2:
        return None
    rashi_index = (ctx["tp_asc_sign_index"] + house - 1) % 12
    d1_occupants = [p for p, d in ctx["d1_fact_sheet"]["d1_planets"].items() if d["sign_index"] == rashi_index]
    if not d1_occupants:
        return None
    rashi_name = SIGNS[rashi_index]
    text = (f"TP rashi {rashi_name} (house {house}) aspected by {len(malefics)} malefics: {', '.join(malefics)}; "
            f"D1 planet(s) {', '.join(d1_occupants)} occupy this same rashi — their significations suffer this year.")
    return _finding("R10", "Malefic aspect on a TP rashi, cross-referenced to D1 occupant", text, [house],
                     sorted(set(malefics) | set(d1_occupants)), _severity_from_count(len(malefics)), 2)


def _r11(ctx):
    benefics = _check_benefic_occupant(ctx["tp_positions"], ctx["house_summary"], 2)
    if not benefics:
        return None
    text = f"Benefic(s) {', '.join(benefics)} placed in TP house 2 — favorable year for earning money."
    return _finding("R11", "Benefic planet in TP 2nd house", text, [2], benefics, "moderate", 2)


def _r12(ctx):
    malefics = _check_malefic_occupant(ctx["tp_positions"], ctx["house_summary"], 2)
    triggering = [p for p, exception in malefics if not exception]
    if not triggering:
        return None
    text = f"Malefic(s) {', '.join(triggering)} placed in TP house 2 — unfavorable for material prosperity this year."
    return _finding("R12", "Malefic planet in TP 2nd house", text, [2], triggering, "moderate", 2)


# ── Month-level (§2) ─────────────────────────────────────────────────────────

def _add_months(d, months):
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _month_windows(client_birth_date, target_year):
    birth_month = int(client_birth_date[5:7])
    birth_day = int(client_birth_date[8:10])
    day = min(birth_day, calendar.monthrange(target_year, birth_month)[1])
    anchor = date(target_year, birth_month, day)
    return {n: (_add_months(anchor, n - 1).isoformat(), _add_months(anchor, n).isoformat())
            for n in range(1, 13)}


def _month_house_map(ctx):
    sun_house = ctx["tp_positions"]["Sun"]["house"]
    return {n: ((sun_house - 1 + (n - 1)) % 12) + 1 for n in range(1, 13)}


def _month_findings(ctx):
    findings = []
    house_map = _month_house_map(ctx)
    windows = _month_windows(ctx["client_birth_date"], ctx["target_year"])

    for month, house in house_map.items():
        window_start, window_end = windows[month]
        label = f"Month {month} ({window_start} to {window_end}, house {house})"

        conjunct_malefics = _check_multi_malefic_conjunct(ctx["house_summary"], house)
        if conjunct_malefics:
            text = (f"{label}: {len(conjunct_malefics)} malefics conjunct — {', '.join(conjunct_malefics)}. "
                    f"Problems likely for this house's significations.")
            findings.append(_finding("M1", "Multi-malefic conjunction in a house", text, [house],
                                      conjunct_malefics, _severity_from_count(len(conjunct_malefics)),
                                      3, month=month))

        aspecting_malefics = _check_multi_malefic_aspect(ctx["house_summary"], house)
        if aspecting_malefics:
            text = f"{label}: {len(aspecting_malefics)} malefics aspecting — {', '.join(aspecting_malefics)}."
            findings.append(_finding("M2", "Multi-malefic aspect on a house", text, [house],
                                      aspecting_malefics, _severity_from_count(len(aspecting_malefics)),
                                      3, month=month))

        for p, malefics in _check_afflicted_occupant(ctx["tp_positions"], ctx["house_summary"], house):
            text = (f"{label}: {p} afflicted by {', '.join(malefics)} — significations affected: "
                    f"{PLANET_SIGNIFICATIONS.get(p, '')}")
            findings.append(_finding("R8", "Afflicted planet in house (monthly)", text, [house],
                                      [p] + malefics, _severity_from_count(len(malefics)), 3, month=month))

        benefics = _check_benefic_occupant(ctx["tp_positions"], ctx["house_summary"], house)
        if benefics:
            text = f"{label}: benefic(s) {', '.join(benefics)} present — supportive influence."
            findings.append(_finding("R11", "Benefic planet in house (monthly)", text, [house],
                                      benefics, "moderate", 3, month=month))

        malefic_occupants = [p for p, exception in _check_malefic_occupant(ctx["tp_positions"], ctx["house_summary"], house)
                              if not exception]
        if malefic_occupants:
            text = f"{label}: malefic(s) {', '.join(malefic_occupants)} present — unfavorable influence."
            findings.append(_finding("R12", "Malefic planet in house (monthly)", text, [house],
                                      malefic_occupants, "moderate", 3, month=month))

        r10 = _r10_for_rashi(ctx, house)
        if r10:
            r10 = dict(r10)
            r10["prediction_text"] = f"{label}: " + r10["prediction_text"]
            r10["priority_tier"] = 3
            r10["month"] = month
            findings.append(r10)

    return findings


# ── Entry point ──────────────────────────────────────────────────────────────

def apply_tithi_pravesh_rules(d1_fact_sheet: dict, tp_chart: dict, client_married: bool,
                               client_birth_date: str, target_year: int,
                               personal_concern: str = "") -> dict:
    """Runs all R1-R18 and M1-M2 rules, returns {"applied_rules": [...]}"""
    tp_positions = tp_chart["chart"]["positions"]
    house_summary = tp_chart["house_summary"]
    lagnesh_analysis = tp_chart["lagnesh_analysis"]

    ctx = {
        "d1_fact_sheet": d1_fact_sheet,
        "tp_positions": tp_positions,
        "house_summary": house_summary,
        "tp_asc_sign_index": tp_positions["Ascendant"]["sign_index"],
        "d1_asc_sign_index": d1_fact_sheet["ascendant"]["sign_index"],
        "tp_lagnesh": lagnesh_analysis["tp_lagnesh"],
        "tp_lagnesh_position": lagnesh_analysis["tp_lagnesh_position"],
        "d1_lagnesh": lagnesh_analysis["d1_lagnesh"],
        "d1_lagnesh_tp_position": lagnesh_analysis["d1_lagnesh_tp_position"],
        "client_married": client_married,
        "client_birth_date": client_birth_date,
        "target_year": target_year,
        "personal_concern": personal_concern,
    }

    findings = []

    for fn in (_r1, _r3_r9, _r4, _r5, _r6, _r7, _r14, _r15, _r16, _r17, _r18):
        result = fn(ctx)
        if result:
            findings.append(result)

    findings.extend(_r13(ctx))

    for fn in (_r8, _r11, _r12):
        result = fn(ctx)
        if result:
            findings.append(result)

    for house in range(1, 13):
        r2 = _r2_for_house(ctx, house)
        if r2:
            findings.append(r2)
        r10 = _r10_for_rashi(ctx, house)
        if r10:
            findings.append(r10)

    findings.extend(_month_findings(ctx))

    return {"applied_rules": findings}
