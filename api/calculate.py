"""
api/calculate.py
Vercel serverless function — POST /api/calculate
Runs Swiss Ephemeris + Rule Engine, returns verified fact sheet.
"""

from http.server import BaseHTTPRequestHandler
import json
import sys
import os

# Make sure sibling files are importable
sys.path.insert(0, os.path.dirname(__file__))

from ephemeris import get_all_positions, get_julian_day
from rules import derive_facts
from tithi_pravesh import calculate_tithi_pravesh
from kundli_chart_svg import generate_north_indian_chart_svg, generate_north_indian_chart_png_base64


def validate_input(body: dict) -> str | None:
    """Returns error message if invalid, None if valid."""
    required = ["name", "date", "time", "latitude", "longitude", "timezone_offset"]
    for field in required:
        if field not in body:
            return f"Missing required field: {field}"

    import re
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(body["date"])):
        return "date must be in YYYY-MM-DD format"
    if not re.match(r"^\d{2}:\d{2}(:\d{2})?$", str(body["time"])):
        return "time must be in HH:MM or HH:MM:SS format (24hr)"

    if body.get("tithi_pravesh") is True and "target_year" not in body:
        return "target_year is required when tithi_pravesh is true"

    return None


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        # Read body
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length)

        try:
            body = json.loads(raw_body)
        except Exception:
            self._respond(400, {"error": "Invalid JSON body"})
            return

        # Validate
        error = validate_input(body)
        if error:
            self._respond(400, {"error": error})
            return

        try:
            # Step 1: Swiss Ephemeris raw positions
            raw = get_all_positions(
                date_str=str(body["date"]),
                time_str=str(body["time"]),
                tz_offset=float(body["timezone_offset"]),
                lat=float(body["latitude"]),
                lon=float(body["longitude"])
            )

            # Step 2: Rule engine derives verified facts
            facts = derive_facts(
                positions=raw["positions"],
                birth_date=str(body["date"]),
                birth_time=str(body["time"]),
                married=bool(body.get("married", False))
            )

            result = {
                "status": "success",
                "client": {
                    "name": body["name"],
                    "date": body["date"],
                    "time": body["time"],
                    "latitude": body["latitude"],
                    "longitude": body["longitude"],
                    "timezone_offset": body["timezone_offset"],
                    "gender": body.get("gender", "unknown"),
                    "married": body.get("married", False),
                },
                "ayanamsa": {
                    "system": "Lahiri",
                    "value": raw["ayanamsa_lahiri"]
                },
                "fact_sheet": facts
            }

            if body.get("tithi_pravesh") is True:
                natal_jd = get_julian_day(
                    date_str=str(body["date"]),
                    time_str=str(body["time"]),
                    tz_offset=float(body["timezone_offset"])
                )
                tp_result = calculate_tithi_pravesh(
                    natal_jd=natal_jd,
                    target_year=int(body["target_year"]),
                    birth_lat=float(body["latitude"]),
                    birth_lon=float(body["longitude"]),
                    d1_lagnesh=facts["ascendant"]["lord"]
                )

                tp_positions = tp_result["chart"]["positions"]
                planet_house_map = {
                    name: pos["house"]
                    for name, pos in tp_positions.items()
                    if name != "Ascendant"
                }
                planet_nakshatra_map = {
                    name: pos["nakshatra"]
                    for name, pos in tp_positions.items()
                    if name != "Ascendant"
                }
                planet_degree_map = {
                    name: (pos["degree"], pos["minute"])
                    for name, pos in tp_positions.items()
                    if name != "Ascendant"
                }
                tp_result["chart_svg"] = generate_north_indian_chart_svg(
                    ascendant_sign_index=tp_positions["Ascendant"]["sign_index"],
                    planet_house_map=planet_house_map,
                    planet_nakshatra_map=planet_nakshatra_map,
                    planet_degree_map=planet_degree_map,
                    ascendant_degree=(tp_positions["Ascendant"]["degree"], tp_positions["Ascendant"]["minute"])
                )
                tp_result["chart_png_base64"] = generate_north_indian_chart_png_base64(
                    ascendant_sign_index=tp_positions["Ascendant"]["sign_index"],
                    planet_house_map=planet_house_map,
                    size=400
                )

                result["tithi_pravesh"] = tp_result

            self._respond(200, result)

        except Exception as e:
            self._respond(500, {"error": f"Calculation error: {str(e)}"})

    def do_GET(self):
        # Health check
        self._respond(200, {
            "status": "ok",
            "engine": "Swiss Ephemeris + Jyotish Rule Engine",
            "ayanamsa": "Lahiri",
            "version": "2.0.0"
        })

    def do_OPTIONS(self):
        # CORS preflight
        self.send_response(200)
        self._cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _respond(self, status: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # Suppress default logging
