# test_tp.py — api/ folder ke andar rakh (taaki imports kaam karein)

from ephemeris import get_julian_day
from tithi_pravesh import calculate_tithi_pravesh

# Sample natal data
natal_jd = get_julian_day(
    date_str="1992-09-07",
    time_str="06:30:00",
    tz_offset=5.5
)

result = calculate_tithi_pravesh(
    natal_jd=natal_jd,
    target_year=2026,
    birth_lat=23.3441,
    birth_lon=85.3096
)

import json
print(json.dumps(result, indent=2, default=str))