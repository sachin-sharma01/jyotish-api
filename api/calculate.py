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

from ephemeris import get_all_positions
from rules import derive_facts


def validate_input(body: dict) -> str | None:
    """Returns error message if invalid, None if valid."""
    required = ["name", "date", "time", "latitude", "longitude", "timezone_offset"]
    for field in required:
        if field not in body:
            return f"Missing required field: {field}"

    import re
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(body["date"])):
        return "date must be in YYYY-MM-DD format"
    if not re.match(r"^\d{2}:\d{2}$", str(body["time"])):
        return "time must be in HH:MM format (24hr)"

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
