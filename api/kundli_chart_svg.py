"""
kundli_chart_svg.py
Renders a North Indian style diamond Kundli chart as an inline SVG string.

Construction: square + both diagonals + inner diamond (connecting the
midpoints of the square's sides) produces the standard 12 compartments —
4 kite-shaped kendra houses (1, 4, 7, 10) touching the top/right/bottom/left
edge midpoints, and 8 triangular houses filling the four corners (two per
corner). House 1 (Lagna) is always the fixed top-center kite; houses are
numbered 1-12 counter-clockwise from there in fixed screen positions — only
the rashi numbers and planets written inside change per chart.
"""

PLANET_ABBR = {
    "Sun": "Su", "Moon": "Mo", "Mars": "Ma", "Mercury": "Me",
    "Jupiter": "Ju", "Venus": "Ve", "Saturn": "Sa", "Rahu": "Ra", "Ketu": "Ke"
}

GOLD = "#8b6914"
NAVY = "#1a1a2e"
FONT_STACK = "Georgia, 'Times New Roman', serif"


def _house_geometry(size: float):
    """Returns (houses, lines) for a size x size canvas.
    houses: {house_number: (polygon_points, outer_vertex)}
    lines: the four structural strokes (square / diag1 / diag2 / diamond)
    """
    S = size
    q, h, t3 = S / 4, S / 2, 3 * S / 4

    TL, TR, BR, BL = (0, 0), (S, 0), (S, S), (0, S)
    T, R, B, L = (h, 0), (S, h), (h, S), (0, h)
    C = (h, h)
    P1, P2, P3, P4 = (t3, q), (q, q), (t3, t3), (q, t3)

    # House numbers increase COUNTER-clockwise from the fixed top kite (House 1)
    # — e.g. an Ascendant of Scorpio (8) puts Sagittarius (9) in House 2, which
    # sits at the top-left (not top-right).
    houses = {
        1:  ([T, P1, C, P2], T),
        2:  ([T, TL, P2], TL),
        3:  ([TL, L, P2], TL),
        4:  ([L, P2, C, P4], L),
        5:  ([BL, L, P4], BL),
        6:  ([B, BL, P4], BL),
        7:  ([B, P4, C, P3], B),
        8:  ([BR, B, P3], BR),
        9:  ([R, BR, P3], BR),
        10: ([R, P3, C, P1], R),
        11: ([TR, R, P1], TR),
        12: ([T, TR, P1], TR),
    }

    lines = {
        "square": [TL, TR, BR, BL],
        "diag1": [TL, BR],
        "diag2": [TR, BL],
        "diamond": [T, R, B, L],
    }
    return houses, lines


def _degree_str(degree: int, minute: int) -> str:
    return f"{degree}°{minute:02d}'"


def generate_north_indian_chart_svg(
    ascendant_sign_index: int,
    planet_house_map: dict,
    planet_nakshatra_map: dict = None,
    planet_degree_map: dict = None,
    ascendant_degree: tuple = None,
    size: int = 400
) -> str:
    S = float(size)
    houses, lines = _house_geometry(S)

    # Each house collects ready-to-render <tspan>-based line contents, so
    # the Ascendant marker (house 1 only) and regular planets share one
    # rendering path.
    house_lines = {i: [] for i in range(1, 13)}

    if ascendant_degree is not None:
        deg, minute = ascendant_degree
        house_lines[1].append(f'<tspan>Asc({_degree_str(deg, minute)})</tspan>')

    for planet, house_num in planet_house_map.items():
        abbr = PLANET_ABBR.get(planet)
        if not abbr or house_num not in house_lines:
            continue

        line = [f'<tspan>{abbr}</tspan>']

        if planet_degree_map and planet in planet_degree_map:
            deg, minute = planet_degree_map[planet]
            line.append(f'<tspan font-size="8" font-weight="normal" dx="2">{_degree_str(deg, minute)}</tspan>')

        if planet_nakshatra_map:
            nak_name = planet_nakshatra_map.get(planet)
            if nak_name:
                line.append(f'<tspan font-size="8" font-weight="normal" dx="2">{nak_name[:3]}</tspan>')

        house_lines[house_num].append("".join(line))

    def pts(points):
        return " ".join(f"{x:.2f},{y:.2f}" for x, y in points)

    parts = [
        f'<svg viewBox="0 0 {S:g} {S:g}" width="100%" height="100%" '
        f'style="width:100%;height:auto;display:block;" xmlns="http://www.w3.org/2000/svg">'
    ]

    # Outer border (heavier gold stroke)
    parts.append(f'<rect x="0" y="0" width="{S:g}" height="{S:g}" fill="none" stroke="{GOLD}" stroke-width="3"/>')

    # Diagonals
    (x1, y1), (x2, y2) = lines["diag1"]
    parts.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{GOLD}" stroke-width="1.5"/>')
    (x1, y1), (x2, y2) = lines["diag2"]
    parts.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{GOLD}" stroke-width="1.5"/>')

    # Inner diamond
    parts.append(f'<polygon points="{pts(lines["diamond"])}" fill="none" stroke="{GOLD}" stroke-width="1.5"/>')

    for house_num in range(1, 13):
        verts, outer = houses[house_num]
        cx = sum(p[0] for p in verts) / len(verts)
        cy = sum(p[1] for p in verts) / len(verts)

        # Rashi number: nudged from the house centroid toward its outer
        # (periphery-facing) vertex, so it sits in a "corner" of the shape.
        rx = cx + 0.65 * (outer[0] - cx)
        ry = cy + 0.65 * (outer[1] - cy)

        sign_num = (ascendant_sign_index + house_num - 1) % 12 + 1
        parts.append(
            f'<text x="{rx:.2f}" y="{ry:.2f}" font-size="11" fill="{GOLD}" '
            f'text-anchor="middle" dominant-baseline="middle" font-family="{FONT_STACK}">{sign_num}</text>'
        )

        lines_here = house_lines[house_num]
        if not lines_here:
            continue

        # One line per entry (Ascendant marker and/or planets), stacked
        # vertically so nothing overlaps.
        line_height = 14
        start_y = cy - (len(lines_here) - 1) * line_height / 2
        for i, content in enumerate(lines_here):
            py = start_y + i * line_height
            parts.append(
                f'<text x="{cx:.2f}" y="{py:.2f}" font-size="13" font-weight="bold" fill="{NAVY}" '
                f'text-anchor="middle" dominant-baseline="middle" font-family="{FONT_STACK}">{content}</text>'
            )

    parts.append('</svg>')
    return "".join(parts)
