"""
yearly_report.py
2027 Yearly Report data builder.

Transits come ONLY from the hardcoded `transits_2027_data` module — no Swiss
Ephemeris calls for transiting planets and no datetime.now(). The natal chart
(raw_positions / facts) is passed in by the caller.
"""

from datetime import date, datetime, timedelta

from ephemeris import SIGNS, vimshottari_tree
from jyotish_fundamentals import get_dignity, houses_aspected_by, sign_lord
from transits_2027_data import YEAR, START_POSITIONS, EVENTS, DAILY

PLANETS_9 = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
TARGETS = ["Ascendant"] + PLANETS_9
SLOW_PLANETS = ["Jupiter", "Saturn", "Rahu", "Ketu"]

YEAR_START = f"{YEAR}-01-01"
YEAR_END = f"{YEAR}-12-31"

PEAK_ORB = 5.0

LUCKY_TABLE = {
    "Sun":     ("Orange / Copper", 1),
    "Moon":    ("White / Silver", 2),
    "Jupiter": ("Yellow", 3),
    "Rahu":    ("Smoky Grey", 4),
    "Mercury": ("Green", 5),
    "Venus":   ("Pink / Cream", 6),
    "Ketu":    ("Brown", 7),
    "Saturn":  ("Navy Blue", 8),
    "Mars":    ("Red", 9),
}
LUCKY_HOUSES = {1, 4, 5, 7, 9, 10}

SADE_SATI_PHASES = {
    12: "Sade Sati — rising phase",
    1: "Sade Sati — peak",
    2: "Sade Sati — setting phase",
    4: "Kantaka (Ardhashtama) Shani",
    8: "Ashtama Shani",
}

MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]


# ── Generic helpers ──────────────────────────────────────────────────────────

def _d(s: str) -> date:
    return date.fromisoformat(s)


def _fmt(dt) -> str:
    return dt.strftime("%Y-%m-%d")


def _merge_days(days: list) -> list:
    """days: list of (date_str, key) in chronological order (only matching days).
    Merges consecutive days with equal key → [(key, from, to)]."""
    out = []
    for ds, key in days:
        if out and out[-1][0] == key and _d(ds) - _d(out[-1][2]) == timedelta(days=1):
            out[-1][2] = ds
        else:
            out.append([key, ds, ds])
    return [tuple(x) for x in out]


def _daily_in(planet: str, from_date: str, to_date: str):
    for ds, lon, retro in DAILY[planet]:
        if from_date <= ds <= to_date:
            yield ds, lon, retro


def _sign_of(lon: float) -> int:
    return int(lon // 30) % 12


def house_from(ref_sign_index: int, sign_index: int) -> int:
    return ((sign_index - ref_sign_index) % 12) + 1


def _month_bounds(month: int):
    start = date(YEAR, month, 1)
    nxt = date(YEAR + 1, 1, 1) if month == 12 else date(YEAR, month + 1, 1)
    return start.isoformat(), (nxt - timedelta(days=1)).isoformat()


# ── Report builder (closure over the natal chart) ────────────────────────────

class _Ctx:
    def __init__(self, raw_positions: dict, facts: dict):
        self.pos = raw_positions
        self.facts = facts
        self.asc = facts["ascendant"]["sign_index"]
        self.moon = raw_positions["Moon"]["sign_index"]
        self.d1 = facts["d1_planets"]

    def houses_ruled(self, planet: str) -> list:
        return sorted(h for h in range(1, 13)
                      if sign_lord((self.asc + h - 1) % 12) == planet)

    def lord_info(self, planet: str) -> dict:
        p = self.d1.get(planet, {})
        return {"planet": planet, "natal_house": p.get("house"),
                "natal_sign": p.get("sign"), "dignity": p.get("dignity"),
                "houses_ruled": self.houses_ruled(planet)}

    def contacts(self, transit_planet: str, transit_sign_index: int) -> dict:
        h = house_from(self.asc, transit_sign_index)
        asp_signs = {(self.asc + ah - 1) % 12 for ah in houses_aspected_by(transit_planet, h)}
        conj, asp = [], []
        for t in TARGETS:
            s = self.pos[t]["sign_index"]
            if s == transit_sign_index:
                conj.append(t)
            elif s in asp_signs:
                asp.append(t)
        return {"conjunct": conj, "aspected": asp}

    def peak_windows(self, transit_planet: str, target: str, from_date: str, to_date: str) -> list:
        tsign = self.pos[target]["sign_index"]
        tlon = self.pos[target]["longitude"]
        days = []
        for ds, lon, _ in _daily_in(transit_planet, from_date, to_date):
            diff = abs((lon - tlon + 180) % 360 - 180)
            if _sign_of(lon) == tsign and diff <= PEAK_ORB:
                days.append((ds, None))
        return [{"from": f, "to": t} for _, f, t in _merge_days(days)]

    def segment(self, planet: str, sign_index: int, frm: str, to: str, with_dignity=False) -> dict:
        seg = {"sign": SIGNS[sign_index], "from": frm, "to": to,
               "house_from_lagna": house_from(self.asc, sign_index),
               "house_from_moon": house_from(self.moon, sign_index)}
        if with_dignity:
            seg["stations"] = [{"type": e["type"], "date": e["date"]} for e in EVENTS
                               if e["planet"] == planet and e["type"] != "ingress"
                               and frm <= e["date"] <= to]
            seg["dignity"] = get_dignity(planet, sign_index)
        c = self.contacts(planet, sign_index)
        seg["contacts"] = c
        seg["peaks"] = [{"target": t, **w} for t in c["conjunct"]
                        for w in self.peak_windows(planet, t, frm, to)]
        return seg


def _sign_segments(planet: str) -> list:
    """[(sign_index, from, to)] for the whole year from ingress EVENTS."""
    cur = SIGNS.index(START_POSITIONS[planet]["sign"])
    frm = YEAR_START
    out = []
    for e in EVENTS:
        if e["planet"] == planet and e["type"] == "ingress":
            out.append((cur, frm, e["date"]))
            cur, frm = SIGNS.index(e["to_sign"]), e["date"]
    out.append((cur, frm, YEAR_END))
    return out


# ── Sections ────────────────────────────────────────────────────────────────

def _dasha_2027(ctx: _Ctx, tree: list) -> dict:
    def item(p):
        return {"lord": p["lord"], "start": _fmt(p["start"]), "end": _fmt(p["end"]),
                "md_lord": p["md_lord"], "ad_lord": p["ad_lord"],
                "lord_info": ctx.lord_info(p["lord"])}

    res = {"mahadasha": [], "antardasha": [], "pratyantardasha": []}
    key = {"MD": "mahadasha", "AD": "antardasha", "PD": "pratyantardasha"}
    for p in tree:
        res[key[p["level"]]].append(item(p))

    changes = []
    for level in ("MD", "AD"):
        items = [p for p in tree if p["level"] == level]
        for a, b in zip(items, items[1:]):
            ds = _fmt(b["start"])
            if YEAR_START <= ds <= YEAR_END:
                changes.append({"level": level, "from_lord": a["lord"],
                                "to_lord": b["lord"], "date": ds})
    res["changes_in_2027"] = sorted(changes, key=lambda c: c["date"])
    return res


def _transits(ctx: _Ctx) -> dict:
    return {p: [ctx.segment(p, s, f, t, with_dignity=True) for s, f, t in _sign_segments(p)]
            for p in SLOW_PLANETS}


def _sade_sati(ctx: _Ctx) -> list:
    days = []
    for ds, lon, _ in DAILY["Saturn"]:
        h = house_from(ctx.moon, _sign_of(lon))
        days.append((ds, (SADE_SATI_PHASES.get(h, "None"), h)))
    return [{"phase": k[0], "from": f, "to": t, "saturn_house_from_moon": k[1]}
            for k, f, t in _merge_days(days)]


def _double_transit(ctx: _Ctx) -> list:
    jup = {ds: lon for ds, lon, _ in DAILY["Jupiter"]}
    per_house = {h: [] for h in range(1, 13)}
    for ds, slon, _ in DAILY["Saturn"]:
        sh = house_from(ctx.asc, _sign_of(slon))
        jh = house_from(ctx.asc, _sign_of(jup[ds]))
        s_set = {sh, *houses_aspected_by("Saturn", sh)}
        j_set = {jh, *houses_aspected_by("Jupiter", jh)}
        for h in s_set & j_set:
            per_house[h].append((ds, h))
    out = []
    for h in range(1, 13):
        out.extend({"house": h, "from": f, "to": t} for _, f, t in _merge_days(per_house[h]))
    return out


def lucky_for_month(month: int, pd_items, asc_sign_index: int, lagnesh: str) -> dict:
    """Lucky planet/color/numbers for a month. Self-contained for later tuning.
    pd_items: PD tree items (start/end as datetime)."""
    probe = datetime(YEAR, month, 15, 12, 0)
    pd_lord = next((p["lord"] for p in pd_items if p["start"] <= probe < p["end"]), None)

    def ruled(planet):
        return {h for h in range(1, 13)
                if sign_lord((asc_sign_index + h - 1) % 12) == planet}

    if pd_lord and ruled(pd_lord) & LUCKY_HOUSES:
        planet = pd_lord
    else:
        planet = sign_lord((asc_sign_index + 8) % 12)  # 9th lord

    color, n1 = LUCKY_TABLE[planet]
    n2 = LUCKY_TABLE[lagnesh][1]
    if n2 == n1:
        n2 = n1 + 9
    return {"planet": planet, "color": color, "numbers": [n1, n2]}


def _monthly(ctx: _Ctx, tree: list) -> list:
    lagnesh = ctx.facts["ascendant"]["lord"]
    pd_items = [p for p in tree if p["level"] == "PD"]
    segs = {p: _sign_segments(p) for p in ("Sun", "Mars")}
    daily_sign = {p: {ds: _sign_of(lon) for ds, lon, _ in DAILY[p]}
                  for p in ("Sun", "Mars", "Saturn", "Rahu")}
    out = []
    for m in range(1, 13):
        ms, me = _month_bounds(m)
        ms_dt, me_dt = datetime.fromisoformat(ms), datetime.fromisoformat(me) + timedelta(days=1)
        item = {"month": f"{MONTH_NAMES[m - 1]} {YEAR}"}

        for p in ("Sun", "Mars"):
            item[p.lower()] = [ctx.segment(p, s, max(f, ms), min(t, me))
                               for s, f, t in segs[p] if f <= me and t >= ms]

        retro = [(ds, None) for ds, _, r in _daily_in("Mars", ms, me) if r]
        item["mars_retrograde"] = [{"from": f, "to": t} for _, f, t in _merge_days(retro)]
        debil = [(ds, None) for ds, lon, _ in _daily_in("Mars", ms, me) if _sign_of(lon) == 3]
        item["mars_debilitated"] = [{"from": f, "to": t} for _, f, t in _merge_days(debil)]

        fof = []
        for p in ("Sun", "Mars"):
            for w in ("Saturn", "Rahu"):
                days = [(ds, s) for ds, s in daily_sign[p].items()
                        if ms <= ds <= me and daily_sign[w][ds] == s]
                fof.extend({"planet": p, "with": w, "sign": SIGNS[s],
                            "house_from_lagna": house_from(ctx.asc, s), "from": f, "to": t}
                           for s, f, t in _merge_days(days))
        item["fire_on_fire"] = sorted(fof, key=lambda x: x["from"])

        item["slow_events"] = [e for e in EVENTS if ms <= e["date"] <= me
                               and not (e["planet"] == "Sun" and e["type"] == "ingress")]

        def overlapping(level):
            return [{"lord": p["lord"], "start": _fmt(p["start"]), "end": _fmt(p["end"])}
                    for p in tree if p["level"] == level
                    and p["start"] < me_dt and p["end"] > ms_dt]
        item["dasha"] = {"antardasha": overlapping("AD"), "pratyantardasha": overlapping("PD")}
        item["lucky"] = lucky_for_month(m, pd_items, ctx.asc, lagnesh)
        out.append(item)
    return out


# ── Public entry point ──────────────────────────────────────────────────────

def build_yearly_2027(raw_positions: dict, facts: dict, birth_date: str,
                      birth_time: str) -> dict:
    ctx = _Ctx(raw_positions, facts)
    tree = vimshottari_tree(raw_positions["Moon"]["longitude"], birth_date, birth_time,
                            datetime(YEAR, 1, 1), datetime(YEAR + 1, 1, 1))
    asc = ctx.asc
    return {
        "year": YEAR,
        "natal_summary": {
            "lagna": SIGNS[asc],
            "lagnesh": sign_lord(asc),
            "moon_sign": SIGNS[ctx.moon],
            "ninth_lord": sign_lord((asc + 8) % 12),
            "seventh_lord": sign_lord((asc + 6) % 12),
        },
        "dasha_2027": _dasha_2027(ctx, tree),
        "transits_2027": _transits(ctx),
        "sade_sati_phases": _sade_sati(ctx),
        "double_transit_windows": _double_transit(ctx),
        "monthly": _monthly(ctx, tree),
    }
