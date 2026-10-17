"""
test_yearly.py — plain assert tests for the 2027 Yearly Report + Antardasha fix.
Run: python api/test_yearly.py
"""

import io
import json
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(__file__))

from ephemeris import get_all_positions, calculate_vimshottari, vimshottari_tree
from rules import derive_facts
from yearly_report import build_yearly_2027
import calculate

CLIENT = {"name": "Test", "date": "1992-09-07", "time": "06:35",
          "latitude": 23.3441, "longitude": 85.3096, "timezone_offset": 5.5}


def near(actual: str, expected: str, tol: int = 1) -> bool:
    return abs((date.fromisoformat(actual) - date.fromisoformat(expected)).days) <= tol


def check_period(p, lord, start=None, end=None):
    assert p["lord"] == lord, (p, lord)
    s = p["start"] if isinstance(p["start"], str) else p["start"].strftime("%Y-%m-%d")
    e = p["end"] if isinstance(p["end"], str) else p["end"].strftime("%Y-%m-%d")
    if start:
        assert near(s, start), (p, start)
    if end:
        assert near(e, end), (p, end)


def call_handler(body: dict) -> tuple:
    """Invoke the real HTTP handler without a socket."""
    h = calculate.handler.__new__(calculate.handler)
    raw = json.dumps(body).encode()
    h.headers = {"Content-Length": str(len(raw))}
    h.rfile = io.BytesIO(raw)
    h.wfile = io.BytesIO()
    status = {}
    h.send_response = lambda code: status.setdefault("code", code)
    h.send_header = lambda *a: None
    h.end_headers = lambda: None
    h.do_POST()
    return status["code"], json.loads(h.wfile.getvalue())


raw = get_all_positions(CLIENT["date"], CLIENT["time"], 5.5, 23.3441, 85.3096)
pos = raw["positions"]
facts = derive_facts(pos, CLIENT["date"], CLIENT["time"], married=False)
moon_lon = pos["Moon"]["longitude"]

# ── Part 1: Antardasha fix ────────────────────────────────────────────────────
assert pos["Moon"]["nakshatra"] == "Purva Ashadha" and pos["Moon"]["pada"] == 4, pos["Moon"]
v = calculate_vimshottari(moon_lon, CLIENT["date"], CLIENT["time"])
seq = v["sequence"]
assert seq[0]["lord"] == "Venus" and abs(seq[0]["years"] - 1.28) < 0.02, seq[0]
for p, (lord, end) in zip(seq, [("Venus", "1993-12-18"), ("Sun", "1999-12-19"),
                                ("Moon", "2009-12-18"), ("Mars", "2016-12-18"),
                                ("Rahu", "2034-12-19")]):
    check_period(p, lord, end=end)
assert seq[4]["start"] == "2016-12-18"

birth_tree = vimshottari_tree(moon_lon, CLIENT["date"], CLIENT["time"],
                              datetime(1992, 9, 7, 6, 35), datetime(1993, 12, 18))
ads = [p for p in birth_tree if p["level"] == "AD"]
assert ads[0]["md_lord"] == "Venus"
check_period(ads[0], "Mercury", end="1992-10-17")
check_period(ads[1], "Ketu", "1992-10-17", "1993-12-18")
assert len(ads) == 2

adult = vimshottari_tree(moon_lon, CLIENT["date"], CLIENT["time"],
                         datetime(2026, 1, 1), datetime(2026, 1, 2))
ad = next(p for p in adult if p["level"] == "AD")
assert ad["md_lord"] == "Rahu"
check_period(ad, "Mercury", "2024-11-30", "2027-06-19")
print("Part 1 (Antardasha fix) OK")

# ── Part 2: yearly report ─────────────────────────────────────────────────────
y = build_yearly_2027(pos, facts, CLIENT["date"], CLIENT["time"])
assert y["year"] == 2027
ns = y["natal_summary"]
assert (ns["lagna"], ns["lagnesh"], ns["moon_sign"], ns["ninth_lord"]) == \
       ("Virgo", "Mercury", "Sagittarius", "Venus"), ns

# Slow transits
t = y["transits_2027"]
def seg(planet, sign):
    return next(s for s in t[planet] if s["sign"] == sign)
assert [s["sign"] for s in t["Jupiter"]] == ["Leo", "Cancer", "Leo", "Virgo"]
assert [s["sign"] for s in t["Saturn"]] == ["Pisces", "Aries", "Pisces"]
assert [s["sign"] for s in t["Rahu"]] == ["Capricorn"] and [s["sign"] for s in t["Ketu"]] == ["Cancer"]
assert seg("Saturn", "Pisces")["house_from_lagna"] == 7
assert seg("Saturn", "Aries")["house_from_lagna"] == 8
assert seg("Jupiter", "Leo")["house_from_lagna"] == 12
assert seg("Jupiter", "Cancer")["house_from_lagna"] == 11
assert seg("Jupiter", "Virgo")["house_from_lagna"] == 1
assert t["Rahu"][0]["house_from_lagna"] == 5 and t["Ketu"][0]["house_from_lagna"] == 11
jc = seg("Jupiter", "Cancer")
assert near(jc["from"], "2027-01-25") and near(jc["to"], "2027-06-26")
assert {"type": "direct", "date": "2027-04-13"} in jc["stations"]
assert near(t["Jupiter"][3]["from"], "2027-11-26")
sa = seg("Saturn", "Aries")
assert near(sa["from"], "2027-06-03") and near(sa["to"], "2027-10-20")
assert sa["dignity"] == "debilitated"
assert [s["type"] for s in sa["stations"]] == ["retrograde"] and near(sa["stations"][0]["date"], "2027-08-09")
assert any(s["type"] == "direct" and near(s["date"], "2027-12-24") for s in t["Saturn"][2]["stations"])
for segs in t.values():
    for s in segs:
        assert not set(s["contacts"]["conjunct"]) & set(s["contacts"]["aspected"])

# Dasha 2027
d = y["dasha_2027"]
assert len(d["mahadasha"]) == 1
check_period(d["mahadasha"][0], "Rahu", "2016-12-18", "2034-12-19")
assert [a["lord"] for a in d["antardasha"]] == ["Mercury", "Ketu"]
check_period(d["antardasha"][0], "Mercury", end="2027-06-19")
check_period(d["antardasha"][1], "Ketu", "2027-06-19", "2028-07-07")
expected_pd = [("Jupiter", None, "2027-01-23"), ("Saturn", "2027-01-23", "2027-06-19"),
               ("Ketu", "2027-06-19", "2027-07-12"), ("Venus", "2027-07-12", "2027-09-14"),
               ("Sun", "2027-09-14", "2027-10-03"), ("Moon", "2027-10-03", "2027-11-04"),
               ("Mars", "2027-11-04", "2027-11-26"), ("Rahu", "2027-11-26", "2028-01-23")]
assert len(d["pratyantardasha"]) == len(expected_pd), [p["lord"] for p in d["pratyantardasha"]]
for p, (lord, s, e) in zip(d["pratyantardasha"], expected_pd):
    check_period(p, lord, s, e)
assert any(c["level"] == "AD" and c["from_lord"] == "Mercury" and c["to_lord"] == "Ketu"
           and near(c["date"], "2027-06-19") for c in d["changes_in_2027"]), d["changes_in_2027"]
assert "lord_info" in d["antardasha"][0]

# Sade Sati
ss = y["sade_sati_phases"]
exp_ss = [("Kantaka (Ardhashtama) Shani", "2027-01-01", "2027-06-02"),
          ("None", "2027-06-03", "2027-10-19"),
          ("Kantaka (Ardhashtama) Shani", "2027-10-20", "2027-12-31")]
assert len(ss) == 3, ss
for p, (ph, f, to) in zip(ss, exp_ss):
    assert p["phase"] == ph and near(p["from"], f) and near(p["to"], to), p

# Double transit
dt = y["double_transit_windows"]
exp_dt = [(1, "2027-11-27", "2027-12-31"), (4, "2027-01-01", "2027-01-24"),
          (4, "2027-10-20", "2027-11-26"), (5, "2027-06-03", "2027-06-25"),
          (7, "2027-01-25", "2027-06-02"), (7, "2027-11-27", "2027-12-31"),
          (8, "2027-06-26", "2027-10-19"), (9, "2027-11-27", "2027-12-31")]
assert len(dt) == len(exp_dt), dt
for w, (h, f, to) in zip(dt, exp_dt):
    assert w["house"] == h and near(w["from"], f) and near(w["to"], to), (w, h, f, to)

# Monthly
m = y["monthly"]
assert len(m) == 12 and m[0]["month"] == "January 2027" and m[11]["month"] == "December 2027"
lucky = [(x["lucky"]["planet"], x["lucky"]["color"], x["lucky"]["numbers"]) for x in m]
assert lucky[0] == ("Jupiter", "Yellow", [3, 5])
assert all(l == ("Saturn", "Navy Blue", [8, 5]) for l in lucky[1:6]), lucky
assert all(l == ("Venus", "Pink / Cream", [6, 5]) for l in lucky[6:]), lucky
assert m[2]["mars_debilitated"] and near(m[2]["mars_debilitated"][0]["from"], "2027-03-10")
assert m[0]["mars_retrograde"] and near(m[0]["mars_retrograde"][0]["from"], "2027-01-10")
assert all(e["planet"] != "Sun" or e["type"] != "ingress" for x in m for e in x["slow_events"])
print("Part 2 (yearly report) OK")

# ── Part 3 / regression via handler ──────────────────────────────────────────
code, plain = call_handler(CLIENT)
assert code == 200 and "yearly_2027" not in plain
assert set(plain) == {"status", "client", "ayanamsa", "fact_sheet"}
code, tp = call_handler({**CLIENT, "tithi_pravesh": True, "target_year": 2026})
assert code == 200 and "yearly_2027" not in tp
assert set(tp) == {"status", "client", "ayanamsa", "fact_sheet", "tithi_pravesh"}
code, err = call_handler({**CLIENT, "yearly_report": True, "report_year": 2028})
assert code == 400 and err["error"] == "Only report_year 2027 is supported"
code, full = call_handler({**CLIENT, "yearly_report": True,
                           "relationship_status": "single", "looking_to_marry": True})
assert code == 200 and "yearly_2027" in full
assert full["client"]["relationship_status"] == "single" and full["client"]["looking_to_marry"] is True
assert set(full["yearly_2027"]) == {"year", "natal_summary", "dasha_2027", "transits_2027",
                                    "sade_sati_phases", "double_transit_windows", "monthly"}
print("Part 3 (handler + regression) OK")

size_kb = len(json.dumps(full["yearly_2027"]).encode()) / 1024
print(f"yearly_2027 size: {size_kb:.1f} KB")
assert size_kb < 100

if "--june" in sys.argv:
    print(json.dumps(full["yearly_2027"]["monthly"][5], indent=2, ensure_ascii=False))

print("ALL TESTS PASSED")
