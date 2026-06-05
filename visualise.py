#!python3

"""
Construct a mouseoverable SVG of three-party-preferred outcomes.

We'll call the three parties "blue" (x-axis), "green" (y-axis) and "red" (with R + G + B == 1).

The primary methods that you'll want to call are `get_args` and `construct_svg`.
"""

from typing import Tuple
import sys
import math
from enum import Enum
import argparse
import re
from xml.sax.saxutils import escape
DEFAULT_CSS = """
text {font-family: sans-serif; font-size: 10px; fill: #222;}
text.label {filter: url(#keylineEffect); font-weight: bold}
/* dot, party, tie*/
.d {opacity:0.6;}
.d:hover {opacity:1;}
.t {fill: #888}
/* point of interest */
.poi {stroke:#000; fill-opacity:0.4; stroke-width: 0.3%}
.poi-label text {fill:#111; stroke:#fff; stroke-width:5px; paint-order:stroke fill markers; stroke-linejoin:round}
.line {stroke: #222; stroke-width: 0.5%; fill:none; stroke-linecap:round;}
#triangle {fill: #222}
.arrow {fill:none; stroke:#111; stroke-width:0.5%; stroke-dasharray:4 2; stroke-dashoffset:0;}
.bg {fill: #fff}
#preflabel {opacity: 0.9}
text.axis {text-anchor: middle; fill:#222;}
path.axis {stroke: #222; stroke-width: 2px;}
"""


class Party(Enum):
    RED = ("Labor", "z")
    GREEN = ("Greens", "y")
    BLUE = ("Coalition", "x")

# NOTE: throughout this file we'll use a variable called `A` to store our general state
# This replaces the original and pervasive use of globals.
# Default values are set in `get_args`

VALID_COLOUR = re.compile(r'^#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?$')

FLOW_ALIASES = {
    "x_to_y": "blue_to_green",
    "x_to_z": "blue_to_red",
    "y_to_x": "green_to_blue",
    "y_to_z": "green_to_red",
    "z_to_x": "red_to_blue",
    "z_to_y": "red_to_green",
}

FLOW_FIELDS = tuple(FLOW_ALIASES.keys())


def esc_text(text: str) -> str:
    """XML escape text and normalise control whitespace."""
    return escape(
        str(text), {"\n": " ", "\t": " ", "\b": " ", "\r": " ", "\f": " "}
    )


def party_name(party: Party, A: argparse.Namespace) -> str:
    """Return escaped display name for a party enum value."""
    if party == Party.BLUE:
        return esc_text(A.x_name)
    if party == Party.GREEN:
        return esc_text(A.y_name)
    return esc_text(A.z_name)


def party_class(party: Party) -> str:
    """Return the canonical CSS class for a party enum value."""
    if party == Party.BLUE:
        return "x"
    if party == Party.GREEN:
        return "y"
    return "z"


def party_fill_css(A: argparse.Namespace) -> str:
    """Return CSS classes for configured party colours."""
    return "\n".join([
        f".x {{fill: {A.x_colour}}}",
        f".y {{fill: {A.y_colour}}}",
        f".z {{fill: {A.z_colour}}}",
    ]) + "\n"


def normalise_colour(value: str, fallback: str) -> str:
    """Ensure a colour value is a safe hex literal."""
    if isinstance(value, str):
        candidate = value.strip()
        if VALID_COLOUR.fullmatch(candidate):
            return candidate.lower()
    return fallback


def sync_legacy_flow_aliases(A: argparse.Namespace) -> None:
    """Keep legacy blue/green/red flow fields aligned with x/y/z fields."""
    for canonical, legacy in FLOW_ALIASES.items():
        setattr(A, legacy, getattr(A, canonical))


def apply_flow_defaults(A: argparse.Namespace) -> None:
    """Resolve canonical flow fields from legacy defaults where needed."""
    for canonical, legacy in FLOW_ALIASES.items():
        if getattr(A, canonical) is None:
            setattr(A, canonical, getattr(A, legacy))
    sync_legacy_flow_aliases(A)


def normalise_labels_and_colours(A: argparse.Namespace) -> None:
    """Normalise public party labels and colour fields."""
    A.x_name = (str(A.x_name).strip() or "Coalition")
    A.y_name = (str(A.y_name).strip() or "Greens")
    A.z_name = (str(A.z_name).strip() or "Labor")
    A.x_colour = normalise_colour(A.x_colour, "#08e")
    A.y_colour = normalise_colour(A.y_colour, "#0a2")
    A.z_colour = normalise_colour(A.z_colour, "#d04")


def normalise_bound(value, fallback) -> float:
    """Normalise a single graph bound to a 0..1 ratio."""
    if value is None:
        value = fallback
    return max(min(abs(value), 1.0), 0.0)


def normalise_bound_pair(lo: float, hi: float) -> Tuple[float, float]:
    """Normalise a lower/upper bound pair without allowing inversion."""
    return (lo, max(lo, hi))


def normalise_chart_bounds(A: argparse.Namespace) -> None:
    """Normalise chart mode bounds and reject impossible ternary bounds."""
    if A.chart_mode == "cartesian":
        # clamp A.start to be a usable range
        A.start = max(min(abs(A.start), 0.5 - 10*A.step), 0.0)

        # If (1 - A.stop) < A.start the graph gets wonky
        A.stop = min(abs(A.stop), 1 - A.start)
    else:
        A.start = max(min(abs(A.start), 1.0), 0.0)
        A.stop = max(min(abs(A.stop), 1.0), 0.0)

    A.x_min, A.x_max = normalise_bound_pair(
        normalise_bound(A.x_min, A.start),
        normalise_bound(A.x_max, A.stop)
    )
    A.y_min, A.y_max = normalise_bound_pair(
        normalise_bound(A.y_min, A.start),
        normalise_bound(A.y_max, A.stop)
    )

    if A.chart_mode == "ternary":
        z_min_default = A.start
        z_max_default = A.stop
    else:
        z_min_default = 0.0
        z_max_default = 1.0

    A.z_min, A.z_max = normalise_bound_pair(
        normalise_bound(A.z_min, z_min_default),
        normalise_bound(A.z_max, z_max_default)
    )

    if A.chart_mode == "ternary":
        if A.x_min + A.y_min + A.z_min > 1.0:
            raise ValueError("minimum ternary bounds leave no valid points")
        if A.x_max + A.y_max + A.z_max < 1.0:
            raise ValueError("maximum ternary bounds leave no valid points")


def configure_canvas(A: argparse.Namespace) -> None:
    """Calculate derived SVG dimensions and ternary viewport geometry."""
    if A.chart_mode == "ternary":
        A.ternary_polygon = ternary_viewport_polygon(A)

        area = 0.0
        for i, point in enumerate(A.ternary_polygon):
            next_point = A.ternary_polygon[(i + 1) % len(A.ternary_polygon)]
            area += point[0] * next_point[1] - next_point[0] * point[1]
        if len(A.ternary_polygon) < 3 or math.isclose(area, 0.0, abs_tol=1e-12):
            raise ValueError("ternary bounds collapse to no drawable area")

        raw_points = [ternary_raw_point(point[0], point[1], A)
                      for point in A.ternary_polygon]
        A.ternary_raw_min_x = min(point[0] for point in raw_points)
        A.ternary_raw_max_x = max(point[0] for point in raw_points)
        A.ternary_raw_min_y = min(point[1] for point in raw_points)
        A.ternary_raw_max_y = max(point[1] for point in raw_points)
        A.ternary_margin = max(A.offset * A.scale, A.scale * 12.0)
        A.inner_width = A.ternary_raw_max_x - A.ternary_raw_min_x
        A.width = A.inner_width + 2 * A.ternary_margin
        A.height = (A.ternary_raw_max_y - A.ternary_raw_min_y) + 2 * A.ternary_margin
        A.ternary_screen_polygon = [
            p2c(point[0], point[1], A) for point in A.ternary_polygon
        ]
    else:
        A.inner_width = A.scale * 100.0 * (A.stop - A.start)
        A.width = (A.offset + 1) * A.scale + A.inner_width
        A.height = A.width

    # A.scale is pixels per percent, A.step is percent per dot
    A.radius = 50.0 * A.scale * A.step


def normalise_preference_flows(A: argparse.Namespace) -> None:
    """Clamp flow fields to 0..1 and normalise over-full preference rows."""
    for field in FLOW_FIELDS:
        setattr(A, field, max(min(abs(getattr(A, field)), 1.0), 0.0))

    for first, second in [
        ("z_to_y", "z_to_x"),
        ("y_to_z", "y_to_x"),
        ("x_to_y", "x_to_z"),
    ]:
        total = getattr(A, first) + getattr(A, second)
        if total > 1.0:
            setattr(A, first, getattr(A, first) / total)
            setattr(A, second, getattr(A, second) / total)

    sync_legacy_flow_aliases(A)


def p2c(blue_pct: float, green_pct: float, A: argparse.Namespace) -> Tuple[float, float]:
    '''Percentages to Coordinates'''
    if A.chart_mode == "ternary":
        (raw_x, raw_y) = ternary_raw_point(blue_pct, green_pct, A)
        return (
            raw_x - A.ternary_raw_min_x + A.ternary_margin,
            raw_y - A.ternary_raw_min_y + A.ternary_margin,
        )

    # trying to account for being out-of-frame here was worse than not doing it
    # additional context is needed and hence now line() exists

    x = ((blue_pct - A.start) / (A.stop - A.start)) * \
        A.inner_width + A.offset * A.scale
    y = A.inner_width * (1 - ((green_pct - A.start) /
                         (A.stop - A.start))) + A.scale

    return (x, y)


def ternary_raw_point(blue_pct: float, green_pct: float, A: argparse.Namespace) -> Tuple[float, float]:
    """Project ternary percentages to unnormalised equilateral-triangle coordinates."""
    side = 100.0 * A.scale
    return (
        side * (blue_pct + 0.5 * green_pct),
        side * (math.sqrt(3.0) / 2.0) * (1.0 - green_pct),
    )


def ternary_value(axis: str, blue_pct: float, green_pct: float) -> float:
    """Return the party value for a ternary axis."""
    if axis == "x":
        return blue_pct
    if axis == "y":
        return green_pct
    return 1.0 - blue_pct - green_pct


def clip_polygon_half_plane(points, axis: str, bound: float, keep_greater: bool):
    """Clip a percentage-space polygon to a single ternary half-plane."""
    if not points:
        return []

    def inside(point):
        value = ternary_value(axis, point[0], point[1])
        if keep_greater:
            return value >= bound - 1e-12
        return value <= bound + 1e-12

    def intersect(start, end):
        start_value = ternary_value(axis, start[0], start[1])
        end_value = ternary_value(axis, end[0], end[1])
        denominator = end_value - start_value
        if math.isclose(denominator, 0.0):
            return end
        t = (bound - start_value) / denominator
        return (
            start[0] + t * (end[0] - start[0]),
            start[1] + t * (end[1] - start[1]),
        )

    clipped = []
    previous = points[-1]
    previous_inside = inside(previous)

    for current in points:
        current_inside = inside(current)
        if current_inside:
            if not previous_inside:
                clipped.append(intersect(previous, current))
            clipped.append(current)
        elif previous_inside:
            clipped.append(intersect(previous, current))

        previous = current
        previous_inside = current_inside

    deduped = []
    for point in clipped:
        if not deduped or not (math.isclose(deduped[-1][0], point[0]) and math.isclose(deduped[-1][1], point[1])):
            deduped.append(point)
    if len(deduped) > 1 and math.isclose(deduped[0][0], deduped[-1][0]) and math.isclose(deduped[0][1], deduped[-1][1]):
        deduped.pop()
    return deduped


def ternary_viewport_polygon(A: argparse.Namespace):
    """Return the clipped ternary viewport polygon in percentage-space coordinates."""
    polygon = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    for axis, bound, keep_greater in [
        ("x", A.x_min, True),
        ("x", A.x_max, False),
        ("y", A.y_min, True),
        ("y", A.y_max, False),
        ("z", A.z_min, True),
        ("z", A.z_max, False),
    ]:
        polygon = clip_polygon_half_plane(polygon, axis, bound, keep_greater)
    return polygon


def clip_ternary_segment(x0: float, y0: float, x1: float, y1: float, A: argparse.Namespace):
    """Clip a percentage-space line segment to the ternary viewport."""
    t_min = 0.0
    t_max = 1.0

    def update(axis: str, bound: float, keep_greater: bool):
        nonlocal t_min, t_max
        start_value = ternary_value(axis, x0, y0)
        end_value = ternary_value(axis, x1, y1)
        delta = end_value - start_value

        if math.isclose(delta, 0.0):
            if keep_greater:
                return start_value >= bound
            return start_value <= bound

        t = (bound - start_value) / delta
        if keep_greater:
            if delta > 0:
                t_min = max(t_min, t)
            else:
                t_max = min(t_max, t)
        else:
            if delta > 0:
                t_max = min(t_max, t)
            else:
                t_min = max(t_min, t)
        return t_min <= t_max

    for axis, bound, keep_greater in [
        ("x", A.x_min, True),
        ("x", A.x_max, False),
        ("y", A.y_min, True),
        ("y", A.y_max, False),
        ("z", A.z_min, True),
        ("z", A.z_max, False),
    ]:
        if not update(axis, bound, keep_greater):
            return None

    return (
        x0 + t_min * (x1 - x0),
        y0 + t_min * (y1 - y0),
        x0 + t_max * (x1 - x0),
        y0 + t_max * (y1 - y0),
    )


def point_in_polygon(point, polygon) -> bool:
    """Return whether a screen-space point is inside a polygon."""
    (x, y) = point
    inside = False
    previous = polygon[-1]

    for current in polygon:
        (x0, y0) = previous
        (x1, y1) = current
        if ((y0 > y) != (y1 > y)):
            x_at_y = (x1 - x0) * (y - y0) / (y1 - y0) + x0
            if x < x_at_y:
                inside = not inside
        previous = current

    return inside


def distance_to_segment(point, start, end) -> float:
    """Return the screen-space distance from a point to a line segment."""
    (px, py) = point
    (x0, y0) = start
    (x1, y1) = end
    dx = x1 - x0
    dy = y1 - y0
    length_sq = dx * dx + dy * dy
    if math.isclose(length_sq, 0.0):
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / length_sq))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def circle_intersects_polygon(centre, radius: float, polygon) -> bool:
    """Return whether a screen-space circle intersects a polygon."""
    if point_in_polygon(centre, polygon):
        return True

    for vertex in polygon:
        if math.hypot(centre[0] - vertex[0], centre[1] - vertex[1]) <= radius:
            return True

    previous = polygon[-1]
    for current in polygon:
        if distance_to_segment(centre, previous, current) <= radius:
            return True
        previous = current

    return False


def calculate_winner(red_pct: float, green_pct: float, blue_pct: float, A: argparse.Namespace) -> Tuple[Party, float]:
    '''Given 3PP percentages, calculate the winner and their 2CP result. 
        Ties for third are resolved where the winner is the same either way, 
        with the tighter 2CP result reported.'''

    def eq(x, y):
        """Equal, to a certain tolerance"""
        # sufficiently close for our purposes
        return math.isclose(x, y, abs_tol=A.step/10.0)

    def lt(x, y):
        """Strictly less than, beyond a certain tolerance"""
        return (x < y) and not eq(x, y)

    def gt(x, y):
        """Strictly greater than, beyond a certain tolerance"""
        return lt(y, x)

    # need to figure out who came third, then who won
    if lt(red_pct, green_pct) and lt(red_pct, blue_pct):
        # Red came third
        green_2cp = green_pct + (A.z_to_y * red_pct)
        blue_2cp = blue_pct + (A.z_to_x * red_pct)
        margin = green_2cp / (green_2cp + blue_2cp) - 0.5
        if gt(green_2cp, blue_2cp):
            return (Party.GREEN, margin)
        elif gt(blue_2cp, green_2cp):
            return (Party.BLUE, -margin)
    if lt(green_pct, red_pct) and lt(green_pct, blue_pct):
        # Green came third
        red_2cp = red_pct + (A.y_to_z * green_pct)
        blue_2cp = blue_pct + (A.y_to_x * green_pct)
        margin = red_2cp / (red_2cp + blue_2cp) - 0.5
        if gt(red_2cp, blue_2cp):
            return (Party.RED, red_2cp)
        elif gt(blue_2cp, margin):
            return (Party.BLUE, -margin)
    if lt(blue_pct, green_pct) and lt(blue_pct, red_pct):
        # Blue came third
        red_2cp = red_pct + (A.x_to_z * blue_pct)
        green_2cp = green_pct + (A.x_to_y * blue_pct)
        margin = red_2cp / (green_2cp + red_2cp) - 0.5
        if gt(red_2cp, green_2cp):
            return (Party.RED, margin)
        elif gt(green_2cp, red_2cp):
            return (Party.GREEN, -margin)

    # print("likely tie:", green_pct, red_pct, blue_pct, file=sys.stderr)

    # resolve ties for third with casting vote of A.step/10
    # if the leading party would win EITHER way, report their win and tightest margin
    # else, return nothing (interpreted as a tie)
    if eq(green_pct, blue_pct) and lt(green_pct, red_pct):
        # Red leading

        # casting vote to exclude Green
        gex = calculate_winner(red_pct, green_pct -
                               A.step/10.0, blue_pct + A.step/10.0, A)
        # casting vote to exclude Blue
        bex = calculate_winner(red_pct, green_pct +
                               A.step/10.0, blue_pct - A.step/10.0, A)

        if gex[0] == Party.RED and bex[0] == Party.RED:
            return (Party.RED, min(gex[1], bex[1]))

    if eq(red_pct, blue_pct) and lt(red_pct, green_pct):
        # Green leading

        # casting vote to exclude Red
        rex = calculate_winner(red_pct - A.step/10,
                               green_pct, blue_pct + A.step/10, A)
        # casting vote to exclude Blue
        bex = calculate_winner(red_pct + A.step/10,
                               green_pct, blue_pct - A.step/10, A)

        if rex[0] == Party.GREEN and bex[0] == Party.GREEN:
            return (Party.GREEN, min(rex[1], bex[1]))

    if eq(green_pct, red_pct) and lt(green_pct, blue_pct):
        # Blue leading

        # casting vote to exclude Green
        gex = calculate_winner(red_pct + A.step/10, green_pct -
                               A.step/10, blue_pct, A)
        # casting vote to exclude Red
        rex = calculate_winner(red_pct - A.step/10, green_pct +
                               A.step/10, blue_pct, A)

        if gex[0] == Party.BLUE and rex[0] == Party.BLUE:
            return (Party.BLUE, min(gex[1], rex[1]))

    # print("actual tie:", green_pct, red_pct, blue_pct, file=sys.stderr)


def construct_dot(blue_pct: float, green_pct: float, A: argparse.Namespace) -> str:
    '''Given green and blue percentages, return an SVG fragment corresponding to a dot at the appropriate position.'''
    red_pct = 1.0 - (green_pct + blue_pct)

    (x, y) = p2c(blue_pct, green_pct, A)

    tooltip_3cp = f"{party_name(Party.GREEN, A)}: {green_pct:.1%}, {party_name(Party.RED, A)}: {red_pct:.1%}, {party_name(Party.BLUE, A)}: {blue_pct:.1%}."

    try:
        (winner, margin) = calculate_winner(red_pct, green_pct, blue_pct, A)
        tooltip = f"{tooltip_3cp} Winner: {party_name(winner, A)} {margin:.1%}"
        return f'<circle cx="{x:g}" cy="{y:g}" r="{A.radius:g}" class="{party_class(winner)} d"><title>{tooltip}</title></circle>'.replace(".0%", "%")

    except TypeError:  # raised on a tie
        tooltip = f"{tooltip_3cp} Winner: TIE"
        return f'<circle cx="{x:g}" cy="{y:g}" r="{A.radius:g}" class="t d"><title>{tooltip}</title></circle>'.replace(".0%", "%")


def frange(start, stop=None, step=None) -> float:
    '''Floating-point range. [start = 0.0], stop, [step = 1.0]'''
    start = float(start)
    if not stop:  # switcheroo
        stop = start
        start = 0.0
    if not step:
        step = 1.0

    count = 0.0
    while True:
        t = start + count * step
        if stop > 0.0 and t >= stop:
            break
        elif stop < 0.0 and t <= stop:
            break
        yield t
        count += 1.0


def clamp_val(val: float, lo: float, hi: float) -> float:
    """Constrain val to be between hi and lo"""
    return max(min(val, hi), lo)


def clamp(val: float, A: argparse.Namespace) -> float:
    """Constrain val to be within A.start and A.stop"""
    return clamp_val(val, A.start, A.stop)


def line(x0: float, y0: float, x1: float, y1: float, A: argparse.Namespace) -> str:
    """Takes two points (percentage-space) and returns the appropriate path fragment, ensuring that they're all in-bounds."""

    if A.chart_mode == "ternary":
        clipped = clip_ternary_segment(x0, y0, x1, y1, A)
        if not clipped:
            return ""
        (xa, ya, xb, yb) = clipped
        (xp, yp) = p2c(xa, ya, A)
        (xq, yq) = p2c(xb, yb, A)
        return f"M {xp:g} {yp:g} {xq:g} {yq:g}"

    # we COULD have just used <clipPath> but this is even cleaner in the SVG

    # general principle: there'll be a gradient.
    # if anything is off the edge, we can replace with appropriate point on the edge

    xa = clamp(x0, A)
    ya = clamp(y0, A)
    xb = clamp(x1, A)
    yb = clamp(y1, A)

    if math.isclose(x0, x1):
        # special case: vertical line
        # we can clamp without fear
        pass
    elif math.isclose(y0, y1):
        # horizontal line
        pass
    elif (x0 <= A.start and x1 <= A.start) or (y0 <= A.start and y1 <= A.start) or \
            (x0 >= A.stop and x1 >= A.stop) or (y0 >= A.stop and y1 >= A.stop):
        # whole of line would be off-viewport
        return ""
    else:
        # get the line equation...
        m = (y1 - y0)/(x1 - x0)  # gradient
        c = y0 - m * x0         # y-offset

        if x0 < A.start:
            ya = m * A.start + c
        elif x0 > A.stop:
            ya = m * A.stop + c

        if x1 < A.start:
            yb = m * A.start + c
        elif x0 > A.stop:
            yb = m * A.stop + c

        if y0 < A.start:
            xa = (A.start - c) / m
        elif y0 > A.stop:
            xa = (A.stop - c) / m

        if y1 < A.start:
            xb = (A.start - c) / m
        elif y1 > A.stop:
            xb = (A.stop - c) / m

    # Finally, convert to coordinates and return
    (xp, yp) = p2c(xa, ya, A)
    (xq, yq) = p2c(xb, yb, A)

    return f"M {xp:g} {yp:g} {xq:g} {yq:g}"


def draw_lines(A: argparse.Namespace) -> str:
    """Draw change-of-winner lines."""

    # Point #1, the Green vs Red point on the Y axis, is at
    # g + A.x_to_y * b == r + A.x_to_z * b
    # g = r + (A.x_to_z * b) - (A.x_to_y * b)
    # g = (1 - (b + g)) + (A.x_to_z - A.x_to_y) * b
    # 2g = (1 - b) + (A.x_to_z - A.x_to_y) * b
    edge_min = 0.0 if A.chart_mode == "ternary" else A.start

    x1 = edge_min
    y1 = ((1 - x1) + (A.x_to_z - A.x_to_y) * x1)/2.0

    # Point #2 is the Green vs Red midpoint
    # It is paramaterised by the ex-Blue split
    # The line between here and the terpoint marks G > R = B
    # r = b = (1 - g)/2
    # or alternatively the `y = 1 - 2x` line
    # While the line between here and point #1 marks the G vs R 2CP
    # y = ((1 - x) + (A.x_to_z - A.x_to_y)*x)/2
    # Point #2 is at the intersection of these lines
    a2 = A.x_to_z - A.x_to_y
    x2 = 1/(a2 + 3)
    y2 = (a2+1)/(a2+3)

    # CORRECTION: When Blue favours Red it's G > R = B
    # But when Blue favours Green it's R > G = B
    # g = b = (1 - r)/2
    # g = b = (1 - (1 - (g + b)))/2
    # y = x
    if a2 < 0:
        x2 = 1/(3 - a2)
        y2 = 1/(3 - a2)

    # Point #3 is the (1/3, 1/3) point ("terpoint")
    # Always some sort of boundary
    (x3, y3) = (1.0/3.0, 1.0/3.0)

    # Line #1-#2-#3 represents the Red/Green boundary
    red_green = f'{line(x1, y1, x2, y2, A)} {line(x2, y2, x3, y3, A)}'

    # Point #4 is the Red vs Blue midpoint.
    # Basically the inverse of #2, parameterised by ex-Green split
    a4 = A.y_to_z - A.y_to_x
    x4 = (a4 + 1)/(a4 + 3)
    y4 = 1/(a4 + 3)

    # CORRECTION: as for point #2
    if a4 < 0:
        x4 = 1/(3 - a4)
        y4 = 1/(3 - a4)

    # Point #5 is Red vs Blue on the X axis
    # The inverse of #1
    y5 = edge_min
    x5 = ((1 - y5) + a4 * y5)/2.0

    # Lines #3 - #4 - #5 represents the Red/Blue boundary
    red_blue = f'{line(x3, y3, x4, y4, A)} {line(x4, y4, x5, y5, A)}'

    # 6. Blue vs Green point. This is controlled by Red's Blue/Green split
    # there's one line coming "out" of the terpoint #3
    # (it's NW if red favours blue, SE if red favours green)
    # (i.e. it's either the #2-#3 gradient or the #3-#4 gradient)
    # and one out of the hapoint #7 (the Red-comes-third line)
    # (mostly W if red favours blue, mostly S if red favours green)
    # This point occurs where these two lines cross
    # (if red favours blue, then red and blue will be equal here)
    # (if red favours green, then red and green will be equal here)
    # degenerates to terpoint if equal ex-Red split

    # Set the following for convenience
    a6 = A.z_to_x - A.z_to_y

    # green-blue line at
    # green + A.red_to_green * red == blue + A.red_to_blue * red
    # green = blue + A.red_to_blue * red - A.red_to_green * red
    # green = blue + red * (A.red_to_blue - A.red_to_green)
    # green = blue + (1 - (green + blue)) * (A.red_to_blue - A.red_to_green)
    # green = blue + 1*a - green*a - blue*a
    # green (1 + a) = blue + (1 - blue) * a
    # green = (blue + (1 - blue) * a) / (1 + a)
    # (where a in range [-1, 1])

    if a6 == 0:
        (x6, y6) = (1.0/3.0, 1.0/3.0)
    elif a6 > 0:
        # Red favours Blue
        # Intersection on the #2-#3 gradient
        # The solution appears to be
        x6 = 1 / (a6 + 3)
        y6 = (a6 + 1) / (a6 + 3)
    else:
        # Red favours Green
        # Intersection on the #3-#4 gradient
        # Solution appears to be
        x6 = (a6 - 1)/(a6 - 3)
        y6 = 1/(3 - a6)

    # 7. Green vs Blue on 45 (hapoint)
    # Also always some sort of boundary
    (x7, y7) = (0.5, 0.5)

    # Lines #3 - #6 - #7 represents the Blue/Green boundary
    blue_green = f'{line(x3, y3, x6, y6, A)} {line(x6, y6, x7, y7, A)}'

    top_right = ""
    if A.chart_mode == "cartesian":
        # Unconditionally we also have a line down y = 1 - x
        # (this passes through the hapoint too, but no direction change)
        (xtop, ytop) = p2c(1.0 - A.stop, A.stop, A)
        (xright, yright) = p2c(A.stop, 1.0 - A.stop, A)
        top_right = f'M {xtop:g} {ytop:g} {xright:g} {yright:g}'

    # OK, time to draw all the lines!
    # print(f'R-G: ({x1:2.1%}, {y1:2.1%}), ({x2:2.1%}, {y2:2.1%}), ({x3:2.1%}, {y3:2.1%})',
    #       f'R-B: ({x3:2.1%}, {y3:2.1%}), ({x4:2.1%}, {y4:2.1%}), ({x5:2.1%}, {y5:2.1%})',
    #       f'B-G: ({x3:2.1%}, {y3:2.1%}), ({x6:2.1%}, {y6:2.1%}), ({x7:2.1%}, {y7:2.1%})', sep='\n', file=sys.stderr)
    return f'\r\n<path d="{red_green} {red_blue} {blue_green} {top_right}" class="line" />\r\n'


def parse_poi_row(row, A: argparse.Namespace):
    """Parse and enrich a point-of-interest row for marker and label rendering."""
    try:
        blue_pct = float(row[0])
        green_pct = float(row[1])

        if blue_pct + green_pct > 1.0:
            raise ValueError("sum of X and Y columns must be <= 1")

        label = row[2] if len(row) > 2 else ""
        (x, y) = p2c(blue_pct, green_pct, A)
        red_pct = 1 - (green_pct + blue_pct)
        tooltip = f"{esc_text(label)}\n{party_name(Party.GREEN, A)}: {green_pct:.1%}, {party_name(Party.RED, A)}: {red_pct:.1%}, {party_name(Party.BLUE, A)}: {blue_pct:.1%}.".replace(
            ".0%", "%")

        try:
            (winner, margin) = calculate_winner(red_pct, green_pct, blue_pct, A)
            tooltip += f"\nWinner: {party_name(winner, A)} {margin:.1%}".replace(
                ".0%", "%")
        except TypeError:  # ties A.n
            tooltip += "\nWinner: TIE"

        return {
            "x": x,
            "y": y,
            "label": str(label),
            "escaped_label": esc_text(label),
            "tooltip": tooltip,
        }

    except (TypeError, IndexError, ValueError) as e:
        print("Could not parse input row:", e, file=sys.stderr)
        print(row, file=sys.stderr)
        return None


def parse_pois(A: argparse.Namespace):
    """Return valid points of interest from query args and optional CSV input."""
    pois = []

    for row in (A.point or []):
        poi = parse_poi_row(row, A)
        if poi:
            pois.append(poi)

    if A.input:
        import csv
        rdr = csv.reader(sys.stdin if A.input == "-" else open(A.input, 'r'))
        for row in rdr:
            poi = parse_poi_row(row, A)
            if poi:
                pois.append(poi)

    return pois


def draw_poi_markers(pois, A: argparse.Namespace) -> str:
    """Draw POI marker circles with tooltip details."""
    out = ""
    for poi in pois:
        out += f'<circle cx="{poi["x"]:g}" cy="{poi["y"]:g}" r="{A.radius:g}" class="d poi"><title>{poi["tooltip"]}</title></circle>\r\n'
    return out


def boxes_overlap(a, b) -> bool:
    """Return whether two screen-space boxes overlap."""
    return not (
        a["x"] + a["width"] <= b["x"] or
        b["x"] + b["width"] <= a["x"] or
        a["y"] + a["height"] <= b["y"] or
        b["y"] + b["height"] <= a["y"]
    )


def label_candidates(poi, width: float, height: float, gap: float):
    """Return deterministic candidate label boxes around a POI marker."""
    x = poi["x"]
    y = poi["y"]
    return [
        {"x": x + gap, "y": y - height / 2.0, "width": width, "height": height},
        {"x": x + gap, "y": y - gap - height, "width": width, "height": height},
        {"x": x + gap, "y": y + gap, "width": width, "height": height},
        {"x": x - gap - width, "y": y - height / 2.0, "width": width, "height": height},
        {"x": x - gap - width, "y": y - gap - height, "width": width, "height": height},
        {"x": x - gap - width, "y": y + gap, "width": width, "height": height},
        {"x": x - width / 2.0, "y": y - gap - height, "width": width, "height": height},
        {"x": x - width / 2.0, "y": y + gap, "width": width, "height": height},
    ]


def box_inside_viewbox(box, A: argparse.Namespace) -> bool:
    """Return whether a label box fits within the SVG viewBox."""
    return (
        box["x"] >= 0.0 and
        box["y"] >= 0.0 and
        box["x"] + box["width"] <= A.width and
        box["y"] + box["height"] <= A.height
    )


def draw_poi_labels(pois, A: argparse.Namespace) -> str:
    """Draw non-overlapping visible labels for labelled POIs."""
    font_size = A.scale
    padding = A.scale * 0.35
    gap = A.radius + A.scale * 0.8
    occupied = [preference_legend_box(A)]
    out = ""

    for poi in pois:
        if not poi["label"].strip():
            continue

        text_width = len(poi["label"]) * font_size * 0.62
        box_width = text_width + 2 * padding
        box_height = font_size * 1.4
        chosen = None

        for candidate in label_candidates(poi, box_width, box_height, gap):
            if not box_inside_viewbox(candidate, A):
                continue
            if any(boxes_overlap(candidate, box) for box in occupied):
                continue
            chosen = candidate
            break

        if not chosen:
            continue

        occupied.append(chosen)
        text_x = chosen["x"] + padding
        text_y = chosen["y"] + chosen["height"] / 2.0
        out += f'<g class="poi-label"><text x="{text_x:g}" y="{text_y:g}" style="font-size:{font_size:g}; dominant-baseline:middle">{poi["escaped_label"]}</text></g>\r\n'

    return out


def constant_party_segment(axis: str, value: float, A: argparse.Namespace):
    """Return the visible segment for a constant-party ternary gridline."""
    if axis == "x":
        if value < A.x_min or value > A.x_max:
            return None
        lower = max(A.y_min, 1.0 - value - A.z_max)
        upper = min(A.y_max, 1.0 - value - A.z_min)
        if lower > upper:
            return None
        return (value, lower, value, upper)

    if axis == "y":
        if value < A.y_min or value > A.y_max:
            return None
        lower = max(A.x_min, 1.0 - value - A.z_max)
        upper = min(A.x_max, 1.0 - value - A.z_min)
        if lower > upper:
            return None
        return (lower, value, upper, value)

    if value < A.z_min or value > A.z_max:
        return None
    lower = max(A.x_min, 1.0 - value - A.y_max)
    upper = min(A.x_max, 1.0 - value - A.y_min)
    if lower > upper:
        return None
    return (lower, 1.0 - value - lower, upper, 1.0 - value - upper)


def draw_ternary_grid(A: argparse.Namespace) -> str:
    """Draw ternary constant-party gridlines."""
    out = ""
    for axis, lo, hi in [
        ("x", A.x_min, A.x_max),
        ("y", A.y_min, A.y_max),
        ("z", A.z_min, A.z_max),
    ]:
        for mark in A.marks:
            if mark <= lo or mark >= hi:
                continue
            segment = constant_party_segment(axis, mark, A)
            if not segment:
                continue
            (x0, y0, x1, y1) = segment
            (xp, yp) = p2c(x0, y0, A)
            (xq, yq) = p2c(x1, y1, A)
            out += f'<path d="M {xp:g} {yp:g} {xq:g} {yq:g}" style="stroke:#ddd; stroke-width:{A.scale * 0.1:g}px; fill:none"/>\r\n'
    return out


def draw_ternary_grid_labels(A: argparse.Namespace) -> str:
    """Draw labels for ternary constant-party gridlines."""
    out = ""
    polygon = [p2c(point[0], point[1], A) for point in A.ternary_polygon]
    centre_x = sum(point[0] for point in polygon) / len(polygon)
    centre_y = sum(point[1] for point in polygon) / len(polygon)

    for axis, lo, hi in [
        ("x", A.x_min, A.x_max),
        ("y", A.y_min, A.y_max),
        ("z", A.z_min, A.z_max),
    ]:
        (target_axis, target_value, _) = ternary_axis_side(axis, A)
        for mark in A.marks:
            if mark <= lo or mark >= hi:
                continue
            segment = constant_party_segment(axis, mark, A)
            if not segment:
                continue
            percentage_endpoints = [
                (segment[0], segment[1]),
                (segment[2], segment[3]),
            ]
            label_point = min(
                percentage_endpoints,
                key=lambda point: abs(ternary_value(target_axis, point[0], point[1]) - target_value)
            )
            if not math.isclose(ternary_value(target_axis, label_point[0], label_point[1]), target_value, abs_tol=1e-9):
                continue
            (label_x, label_y) = p2c(label_point[0], label_point[1], A)
            dx = label_x - centre_x
            dy = label_y - centre_y
            length = math.hypot(dx, dy) or 1.0
            label_x += (dx / length) * A.scale * 2.2
            label_y += (dy / length) * A.scale * 2.2
            anchor = "middle"
            if label_x < centre_x - A.scale:
                anchor = "end"
            elif label_x > centre_x + A.scale:
                anchor = "start"
            out += f'<text x="{label_x:g}" y="{label_y:g}" style="font-size:{A.scale:g}; text-anchor:{anchor}; dominant-baseline:middle">{mark:.0%}</text>\r\n'

    return out


def ternary_axis_side(axis: str, A: argparse.Namespace):
    """Return the side used to label a ternary party axis."""
    if axis == "x":
        return ("y", A.y_min, A.x_name)
    if axis == "y":
        return ("z", A.z_min, A.y_name)
    return ("x", A.x_min, A.z_name)


def draw_ternary_side_labels(A: argparse.Namespace) -> str:
    """Draw rotated party labels on the sides where their ticks appear."""
    polygon = [p2c(point[0], point[1], A) for point in A.ternary_polygon]
    centre_x = sum(point[0] for point in polygon) / len(polygon)
    centre_y = sum(point[1] for point in polygon) / len(polygon)
    out = ""

    for axis in ["x", "y", "z"]:
        (side_axis, side_value, party_label) = ternary_axis_side(axis, A)
        segment = constant_party_segment(side_axis, side_value, A)
        if not segment:
            continue

        endpoints = [
            (segment[0], segment[1]),
            (segment[2], segment[3]),
        ]
        endpoints.sort(key=lambda point: ternary_value(axis, point[0], point[1]))
        (start_x, start_y) = p2c(endpoints[0][0], endpoints[0][1], A)
        (end_x, end_y) = p2c(endpoints[1][0], endpoints[1][1], A)

        label_x = (start_x + end_x) / 2.0
        label_y = (start_y + end_y) / 2.0
        dx = label_x - centre_x
        dy = label_y - centre_y
        length = math.hypot(dx, dy) or 1.0
        label_x += (dx / length) * A.scale * 5.0
        label_y += (dy / length) * A.scale * 5.0

        angle = math.degrees(math.atan2(end_y - start_y, end_x - start_x))
        text = f"{esc_text(party_label)} 3CP &#8594;"
        if angle > 90.0 or angle < -90.0:
            angle += 180.0
            text = f"&#8592; {esc_text(party_label)} 3CP"
        if angle > 180.0:
            angle -= 360.0

        out += f'<text transform="translate({label_x:g}, {label_y:g}) rotate({angle:g})" style="font-size:{A.scale:g}; text-anchor:middle; dominant-baseline:middle">{text}</text>\r\n'

    return out


def draw_ternary_frame(A: argparse.Namespace) -> str:
    """Draw ternary viewport outline and party labels."""
    polygon = [p2c(point[0], point[1], A) for point in A.ternary_polygon]
    if not polygon:
        return ""

    path = " ".join(
        f"{'M' if i == 0 else 'L'} {point[0]:g} {point[1]:g}"
        for i, point in enumerate(polygon)
    )
    out = f'<path d="{path} Z" class="axis" style="fill:none"/>\r\n'

    return out


def ternary_clip_path(A: argparse.Namespace) -> str:
    """Return the ternary viewport clip path definition."""
    polygon = [p2c(point[0], point[1], A) for point in A.ternary_polygon]
    path = " ".join(
        f"{'M' if i == 0 else 'L'} {point[0]:g} {point[1]:g}"
        for i, point in enumerate(polygon)
    )
    return f'<clipPath id="ternaryViewportClip"><path d="{path} Z"/></clipPath>'


def svg_defs(A: argparse.Namespace) -> str:
    """Return SVG definitions, including marker, filter, CSS and clip paths."""
    css = DEFAULT_CSS
    if A.css:
        css = (A.css).read()
    css += "\n" + party_fill_css(A)

    clip_path = ternary_clip_path(A) if A.chart_mode == "ternary" else ""

    return '<defs>' + \
        f'<marker id="triangle" viewBox="0 0 10 10" \
            refX="1" refY="5" \
            markerUnits="strokeWidth" \
            markerWidth="{A.scale * 0.5}" markerHeight="{A.scale * 0.5}" \
            orient="auto"> \
        <path d="M 0 0 L 10 5 L 0 10 z"/> \
        </marker>' + \
        """<filter id="keylineEffect" color-interpolation-filters="sRGB">
            <feMorphology in="SourceGraphic" operator="dilate" radius="2"/>
            <feColorMatrix type="saturate" values="0" />
            <feComponentTransfer in="greyed" result="KEYLINE">
                <feFuncR type="discrete" tableValues="1 0" />
                <feFuncG type="discrete" tableValues="1 0" />
                <feFuncB type="discrete" tableValues="1 0" />
            </feComponentTransfer>
            <feMerge>
                <feMergeNode in="KEYLINE"/>
                <feMergeNode in="SourceGraphic"/>
            </feMerge>
        </filter>""" + \
        f'<style type="text/css"><![CDATA[ \
            {css} \
        ]]> \
        </style>' + \
        clip_path + \
        '</defs>'


def draw_winner_dots(A: argparse.Namespace) -> str:
    """Draw the grid of winner dots for the selected chart mode."""
    out = ""

    if A.chart_mode == "ternary":
        dot_pad = A.step
        x_start = max(0.0, A.x_min - dot_pad)
        x_stop = min(1.0, A.x_max + dot_pad)
        y_start = max(0.0, A.y_min - dot_pad)
        y_stop = min(1.0, A.y_max + dot_pad)

        for b in frange(x_start, (x_stop + A.step), A.step):
            for g in frange(y_start, (y_stop + A.step), A.step):
                r = 1.0 - (g + b)
                if r < 0.0 or r > 1.0:
                    continue
                if r < A.z_min - dot_pad or r > A.z_max + dot_pad:
                    continue
                if not circle_intersects_polygon(
                    p2c(b, g, A),
                    A.radius,
                    A.ternary_screen_polygon
                ):
                    continue
                out += construct_dot(b, g, A)
    else:
        for b in frange(A.start, (A.stop + A.step), A.step):
            for g in frange(A.start, (A.stop + A.step), A.step):
                if g + b > 1.0:
                    continue
                out += construct_dot(b, g, A)

    return out


def preference_legend_lines(A: argparse.Namespace):
    """Return preference-flow legend lines."""
    return [
        f"{A.z_name} to {A.y_name}: {100.0*A.z_to_y:.1f}%",
        f"{A.z_name} to {A.x_name}: {100.0*A.z_to_x:.1f}%",
        f"{A.y_name} to {A.z_name}: {100.0*A.y_to_z:.1f}%",
        f"{A.y_name} to {A.x_name}: {100.0*A.y_to_x:.1f}%",
        f"{A.x_name} to {A.z_name}: {100.0*A.x_to_z:.1f}%",
        f"{A.x_name} to {A.y_name}: {100.0*A.x_to_y:.1f}%",
    ]


def preference_legend_box(A: argparse.Namespace):
    """Return the screen-space preference legend box."""
    legend_lines = preference_legend_lines(A)

    # Estimate text width and size legend box to prevent overflow with long names.
    # For the default sans-serif font, ~0.62 * font-size per character is a reasonable fit.
    max_chars = max(len(line) for line in legend_lines)
    est_text_width = max_chars * A.scale * 0.62
    legend_padding = A.scale * 0.5
    legend_width = est_text_width + 2 * legend_padding
    legend_height = 6.5 * A.scale
    legend_x = max(A.scale * 0.5, A.width - legend_width - legend_padding)
    return {
        "x": legend_x,
        "y": A.scale,
        "width": legend_width,
        "height": legend_height,
    }


def draw_preference_legend(A: argparse.Namespace) -> str:
    """Draw the preference-flow legend."""
    legend_lines = preference_legend_lines(A)
    legend_box = preference_legend_box(A)
    legend_padding = A.scale * 0.5
    legend_text_x = legend_box["x"] + legend_padding

    out = '<g id="preflabel">'
    out += f'<rect width="{legend_box["width"]:g}" height="{legend_box["height"]:g}" x="{legend_box["x"]:g}" y="{legend_box["y"]:g}" class="bg"/>'
    for i, line_text in enumerate(legend_lines, start=2):
        out += f'<text x="{legend_text_x:g}" y="{i*A.scale:g}" style="font-size:{A.scale:g}">{esc_text(line_text)}</text>'
    out += '</g>'
    return out


def draw_cartesian_axes(A: argparse.Namespace) -> str:
    """Draw cartesian axes and labels."""
    (x0, y0) = p2c(A.start, A.start,  A)
    (x0, y100) = p2c(A.start, A.stop,   A)
    (x100, y0) = p2c(A.stop,  A.start,  A)

    out = ""

    # Draw Y axis
    out += f'<path d="M {x0:g} {A.height:g} V {y100:g}" style="stroke: #222; stroke-width: {A.scale * 0.2:g}px" marker-end="url(#triangle)"/>'
    out += f'<text transform="translate({(x0 - (A.offset - 1)*A.scale):g}, {A.height/2 :g}) rotate(270)" style="text-anchor:middle">{esc_text(A.y_name)} 3CP</text>'

    for g in A.marks:
        if g > A.start and g <= (A.stop):
            (xpos, ypos) = p2c(A.start, g, A)
            out += f'<path d="M {xpos:g} {ypos:g} h {-A.scale:g}" style="stroke: #222; stroke-width: {A.scale * 0.2:g}px"/>'
            out += f'<text y="{(ypos + A.scale/2):g}" x="{(xpos - 3*A.scale):g}" style="font-size:{A.scale:g}; text-anchor:right; text-align:middle">{g:.0%}</text>'

    # Draw X axis
    out += f'<path d="M {0:g} {y0:g} H {x100:g}" style="stroke: #222; stroke-width: {A.scale * 0.2:g}px" marker-end="url(#triangle)"/>'
    out += f'<text x="{A.width/2:g}" y="{y0 + 3.5*A.scale:g}" style="text-anchor:middle">{esc_text(A.x_name)} 3CP</text>'

    for b in A.marks:
        if b > A.start and b <= (A.stop):
            (xpos, ypos) = p2c(b, A.start, A)
            out += f'<path d="M {xpos:g} {ypos:g} v {A.scale:g}" style="stroke: #222; stroke-width: {A.scale * 0.2:g}px"/>'
            out += f'<text x="{xpos:g}" y="{ypos + 2*A.scale:g}" style="font-size:{A.scale}; text-anchor:middle">{b:.0%}</text>'

    return out


def construct_svg(A: argparse.Namespace) -> str:
    """Returns an SVG of the graph for given parameters as specified in `A`."""
    # let's output some SVG!

    out = ""

    out += f'<svg viewBox="0 0 {A.width:.0f} {A.height:.0f}" version="1.1" xmlns="http://www.w3.org/2000/svg">'

    # Set up <defs> section, including our triangle marker, the keyline effect and our CSS

    out += svg_defs(A)

    # place a bg rect

    out += f'<rect width="{A.width:.0f}" height="{A.height:.0f}" class="bg" />'
    pois = parse_pois(A) if (A.input or A.point) else []

    if A.chart_mode == "ternary":
        out += '<g clip-path="url(#ternaryViewportClip)">'
        out += draw_ternary_grid(A)

    # place our dots

    out += draw_winner_dots(A)

    # Draw change-of-winner lines
    out += draw_lines(A)

    # place points of interest
    if pois:
        out += draw_poi_markers(pois, A)

    if A.chart_mode == "ternary":
        out += '</g>'

    if pois:
        out += draw_poi_labels(pois, A)

    # Draw labels stating preference assumptions
    out += draw_preference_legend(A)

    if A.chart_mode == "ternary":
        out += draw_ternary_frame(A)
        out += draw_ternary_grid_labels(A)
        out += draw_ternary_side_labels(A)
    else:
        out += draw_cartesian_axes(A)

    out += "\r\n<!-- Generated by https://abjago.net/3pp/ -->\r\n"
    out += "</svg>"

    return out


def get_args(args=None) -> argparse.Namespace:
    """pass args='' for defaults, or leave as None for checking argv.
    DEFAULT VALUES are set here."""
    import argparse

    parser = argparse.ArgumentParser(description="Three-Candidate-Preferred Visualiser.\
        Constructs a 2D graph with configurable X-axis and Y-axis parties, \
        and dots shaded by winning party.\
        Prints an SVG to standard output and optionally takes a CSV of points of interest.\
        N.B. all numeric values should be between zero and one.")

    # Matchup configuration
    parser.add_argument("--x-name", default="Coalition", type=str,
                        help="Name of X-axis party (default: %(default)s)")
    parser.add_argument("--y-name", default="Greens", type=str,
                        help="Name of Y-axis party (default: %(default)s)")
    parser.add_argument("--z-name", default="Labor", type=str,
                        help="Name of balance party (default: %(default)s)")
    parser.add_argument("--x-colour", default="#08e", type=str,
                        help="Colour of X-axis winning dots, hex format (default: %(default)s)")
    parser.add_argument("--y-colour", default="#0a2", type=str,
                        help="Colour of Y-axis winning dots, hex format (default: %(default)s)")
    parser.add_argument("--z-colour", default="#d04", type=str,
                        help="Colour of balance-party winning dots, hex format (default: %(default)s)")

    # Canonical flow parameters
    parser.add_argument("--x-to-y", default=None, type=float,
                        help="X-to-Y preference ratio")
    parser.add_argument("--x-to-z", default=None, type=float,
                        help="X-to-Z preference ratio")
    parser.add_argument("--y-to-x", default=None, type=float,
                        help="Y-to-X preference ratio")
    parser.add_argument("--y-to-z", default=None, type=float,
                        help="Y-to-Z preference ratio")
    parser.add_argument("--z-to-x", default=None, type=float,
                        help="Z-to-X preference ratio")
    parser.add_argument("--z-to-y", default=None, type=float,
                        help="Z-to-Y preference ratio")

    # Legacy aliases (retained for backward compatibility)
    parser.add_argument("--green-to-red", default=0.8, type=float,
                        help="Legacy alias for --y-to-z")
    parser.add_argument("--green-to-blue", default=0.2, type=float,
                        help="Legacy alias for --y-to-x")
    parser.add_argument("--red-to-green", default=0.8, type=float,
                        help="Legacy alias for --z-to-y")
    parser.add_argument("--red-to-blue", default=0.2, type=float,
                        help="Legacy alias for --z-to-x")
    parser.add_argument("--blue-to-red", default=0.7, type=float,
                        help="Legacy alias for --x-to-z")
    parser.add_argument("--blue-to-green", default=0.3, type=float,
                        help="Legacy alias for --x-to-y")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--cartesian", dest="chart_mode", action="store_const", const="cartesian",
                      default="cartesian", help="Draw the current right-angle chart (default)")
    mode.add_argument("--ternary", dest="chart_mode", action="store_const", const="ternary",
                      help="Draw a ternary chart")

    parser.add_argument("--start", default=0.2, type=float,
                        help="minimum axis value shorthand (default: %(default)g)")
    parser.add_argument("--stop", default=0.6, type=float,
                        help="maximum axis value shorthand (default: %(default)g)")
    parser.add_argument("--x-min", default=None, type=float,
                        help="minimum X-party value; defaults to --start")
    parser.add_argument("--x-max", default=None, type=float,
                        help="maximum X-party value; defaults to --stop")
    parser.add_argument("--y-min", default=None, type=float,
                        help="minimum Y-party value; defaults to --start")
    parser.add_argument("--y-max", default=None, type=float,
                        help="maximum Y-party value; defaults to --stop")
    parser.add_argument("--z-min", default=None, type=float,
                        help="minimum Z-party value; in ternary mode defaults to --start")
    parser.add_argument("--z-max", default=None, type=float,
                        help="maximum Z-party value; in ternary mode defaults to --stop")
    parser.add_argument("--step", default=0.01, type=float,
                        help="precision of dots (default: %(default)g)")
    parser.add_argument('--scale', default=10, type=int,
                        help="pixels per percent (default: %(default)g)")
    parser.add_argument('--offset', default=5, type=int,
                        help="multiple of scale factor to A.offset axis by (default: %(default)g)")
    parser.add_argument("--marks", nargs='+', default=[i/10.0 for i in range(0, 10)], metavar="MARK", type=float,
                        help="place axis marks at these values (default: every 10%%)")
    parser.add_argument("--css", metavar='FILE',
                        type=argparse.FileType('r'), help="Use CSS from specified file")
    parser.add_argument("--point", metavar=('X', 'Y', 'LABEL'), nargs=3, action='append', help="Specify a point of interest")
    parser.add_argument(
        "--input", "-i", help="input CSV of points of interest (format: x, y, label) (pass - for standard input)")
    parser.add_argument("--output", "-o", type=argparse.FileType('w'),
                        default=sys.stdout, help="output SVG (default: standard output)")

    return (parser.parse_args(args))


def validate_args(A: argparse.Namespace) -> argparse.Namespace:
    apply_flow_defaults(A)
    normalise_labels_and_colours(A)

    # Clamp A.step to be in a reasonable range
    A.step = max(min(abs(A.step), 0.05), 0.002)

    normalise_chart_bounds(A)
    configure_canvas(A)
    normalise_preference_flows(A)

    return A


# the main shoparty!
if __name__ == "__main__":
    try:
        A = validate_args(get_args())
        print(A, file=sys.stderr)
        print(construct_svg(A), file=A.output)
    except ValueError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
