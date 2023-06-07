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
DEFAULT_CSS = """
text {font-family: sans-serif; font-size: 10px; fill: #222;}
text.label {filter: url(#keylineEffect); font-weight: bold}
/* dot, red, green, blue, tie*/
.d {opacity:0.6;}
.d:hover {opacity:1;}
.r {fill: #d04}
.g {fill: #0a2}
.b {fill: #08e}
.t {fill: #888}
/* point of interest */
.poi {stroke:#000; fill-opacity:0.4; stroke-width: 0.3%}
.line {stroke: #222; stroke-width: 0.5%; fill:none; stroke-linecap:round;}
#triangle {fill: #222}
.arrow {fill:none; stroke:#111; stroke-width:0.5%; stroke-dasharray:4 2; stroke-dashoffset:0;}
.bg {fill: #fff}
#preflabel {opacity: 0.9}
"""


class Party(Enum):
    RED = ("Labor", "r")
    GREEN = ("Greens", "g")
    BLUE = ("Coalition", "b")

# NOTE: throughout this file we'll use a variable called `A` to store our general state
# This replaces the original and pervasive use of globals.
# Default values are set in `get_args`


def p2c(blue_pct: float, green_pct: float, A: argparse.Namespace) -> Tuple[float, float]:
    '''Percentages to Coordinates'''
    # trying to account for being out-of-frame here was worse than not doing it
    # additional context is needed and hence now line() exists

    x = ((blue_pct - A.start) / (A.stop - A.start)) * \
        A.inner_width + A.offset * A.scale
    y = A.inner_width * (1 - ((green_pct - A.start) /
                         (A.stop - A.start))) + A.scale

    return (x, y)


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
        green_2cp = green_pct + (A.red_to_green * red_pct)
        blue_2cp = blue_pct + (A.red_to_blue * red_pct)
        if gt(green_2cp, blue_2cp):
            return (Party.GREEN, green_2cp)
        elif gt(blue_2cp, green_2cp):
            return (Party.BLUE, blue_2cp)
    if lt(green_pct, red_pct) and lt(green_pct, blue_pct):
        # Green came third
        red_2cp = red_pct + (A.green_to_red * green_pct)
        blue_2cp = blue_pct + (A.green_to_blue * green_pct)
        if gt(red_2cp, blue_2cp):
            return (Party.RED, red_2cp)
        elif gt(blue_2cp, red_2cp):
            return (Party.BLUE, blue_2cp)
    if lt(blue_pct, green_pct) and lt(blue_pct, red_pct):
        # Blue came third
        red_2cp = red_pct + (A.blue_to_red * blue_pct)
        green_2cp = green_pct + (A.blue_to_green * blue_pct)
        if gt(red_2cp, green_2cp):
            return (Party.RED, red_2cp)
        elif gt(green_2cp, red_2cp):
            return (Party.GREEN, green_2cp)

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

    tooltip_3cp = f"{Party.GREEN.value[0]}: {green_pct:.1%}, {Party.RED.value[0]}: {red_pct:.1%}, {Party.BLUE.value[0]}: {blue_pct:.1%}."

    try:
        (winner, margin) = calculate_winner(red_pct, green_pct, blue_pct, A)
        tooltip = f"{tooltip_3cp} Winner: {(winner.value)[0]} {margin:.1%}"
        return f'<circle cx="{x:g}" cy="{y:g}" r="{A.radius:g}" class="{(winner.value)[1]} d"><title>{tooltip}</title></circle>'.replace(".0%", "%")

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
    # g + A.blue_to_green * b == r + A.blue_to_red * b
    # g = r + (A.blue_to_red * b) - (A.blue_to_green * b)
    # g = (1 - (b + g)) + (A.blue_to_red - A.blue_to_green) * b
    # 2g = (1 - b) + (A.blue_to_red - A.blue_to_green) * b
    x1 = A.start
    y1 = ((1 - x1) + (A.blue_to_red - A.blue_to_green) * x1)/2.0

    # Point #2 is the Green vs Red midpoint
    # It is paramaterised by the ex-Blue split
    # The line between here and the terpoint marks G > R = B
    # r = b = (1 - g)/2
    # or alternatively the `y = 1 - 2x` line
    # While the line between here and point #1 marks the G vs R 2CP
    # y = ((1 - x) + (A.blue_to_red - A.blue_to_green)*x)/2
    # Point #2 is at the intersection of these lines
    a2 = A.blue_to_red - A.blue_to_green
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
    a4 = A.green_to_red - A.green_to_blue
    x4 = (a4 + 1)/(a4 + 3)
    y4 = 1/(a4 + 3)

    # CORRECTION: as for point #2
    if a4 < 0:
        x4 = 1/(3 - a4)
        y4 = 1/(3 - a4)

    # Point #5 is Red vs Blue on the X axis
    # The inverse of #1
    y5 = A.start
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
    a6 = A.red_to_blue - A.red_to_green

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


def draw_pois(A: argparse.Namespace) -> str:
    """Draw points of interest, as appearing in the specified CSV file"""

    out = ""

    import csv
    rdr = csv.reader(sys.stdin if A.input == "-" else open(A.input, 'r'))
    for row in rdr:
        try:
            r0 = float(row[0])
            r1 = float(row[1])

            if r0 + r1 > 1.0:
                raise ValueError("sum of X and Y columns must be <= 1")

            r2 = row[2] if len(row) > 2 else ""
            (x, y) = p2c(r0, r1, A)
            tooltip = f"{r2}\n{Party.GREEN.value[0]}: {r1:.1%}, {Party.RED.value[0]}: {(1 - (r1+r0)):.1%}, {Party.BLUE.value[0]}: {r0:.1%}.".replace(
                ".0%", "%")

            try:
                (winner, margin) = calculate_winner(1 - (r0 + r1), r1, r0, A)
                tooltip += f"\nWinner: {winner.value[0]} {margin:.1%}".replace(
                    ".0%", "%")
            except TypeError:  # ties A.n
                tooltip += "\nWinner: TIE"
            out += f'<circle cx="{x:g}" cy="{y:g}" r="{A.radius:g}" class="d poi"><title>{tooltip}</title></circle>\r\n'

        except (TypeError, IndexError, ValueError) as e:
            print("Could not parse input row:", e, file=sys.stderr)
            print(row, file=sys.stderr)

    return out


def construct_svg(A: argparse.Namespace) -> str:
    """Returns an SVG of the graph for given parameters as specified in `A`."""
    # let's output some SVG!

    out = ""

    out += f'<svg viewBox="0 0 {A.width:.0f} {A.width:.0f}" version="1.1" xmlns="http://www.w3.org/2000/svg">'

    # Set up <defs> section, including our triangle marker, the keyline effect and our CSS

    css = DEFAULT_CSS
    if A.css:
        css = (A.css).read()

    out += '<defs>' + \
        f'<marker id="triangle" viewBox="0 0 10 10" \
            refX="1" refY="5" \
            markerUnits="strokeWidth" \
            markerWidth="{A.scale * 0.5}" markerHeight="{A.scale * 0.5}" \
            orient="auto"> \
        <path d="M 0 0 L 10 5 L 0 10 z"/> \
        </marker>' + \
        """<filter id="keylineEffect" color-interpolation-filters="sRGB">
            <feMorphology in="SourceGraphic" result="MORPH" operator="dilate" radius="1.5"/>
            <feComponentTransfer result="KEYLINE">
                <!-- invert colors -->
                <feFuncR type="linear" slope="-1" intercept="1" />
                <feFuncG type="linear" slope="-1" intercept="1" />
                <feFuncB type="linear" slope="-1" intercept="1" />
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
        '</defs>'

    # place a bg rect

    out += f'<rect width="{A.width:.0f}" height="{A.width:.0f}" class="bg" />'

    # place our dots

    for b in frange(A.start, (A.stop + A.step), A.step):
        for g in frange(A.start, (A.stop + A.step), A.step):
            if g + b > 1.0:
                continue
            out += construct_dot(b, g, A)

    # Draw change-of-winner lines
    out += draw_lines(A)

    # place points of interest
    if A.input:
        out += draw_pois(A)

    # Draw labels stating preference assumptions
    out += '<g id="preflabel">'
    # place a rect
    out += f'<rect width="{A.scale*13:g}" height="{6.5*A.scale:g}" x="{A.width - A.scale*12.5:g}" y="{A.scale:g}" class="bg"/>'
    out += f'<text x="{A.width - A.scale*12:g}" y="{2*A.scale:g}" style="font-size:{A.scale:g}">{Party.RED.value[0]} to {Party.GREEN.value[0]}: {100.0*A.red_to_green:.1f}%</text>'
    out += f'<text x="{A.width - A.scale*12:g}" y="{3*A.scale:g}" style="font-size:{A.scale:g}">{Party.RED.value[0]} to {Party.BLUE.value[0]}: {100.0*A.red_to_blue:.1f}%</text>'
    out += f'<text x="{A.width - A.scale*12:g}" y="{4*A.scale:g}" style="font-size:{A.scale:g}">{Party.GREEN.value[0]} to {Party.RED.value[0]}: {100.0*A.green_to_red:.1f}%</text>'
    out += f'<text x="{A.width - A.scale*12:g}" y="{5*A.scale:g}" style="font-size:{A.scale:g}">{Party.GREEN.value[0]} to {Party.BLUE.value[0]}: {100.0*A.green_to_blue:.1f}%</text>'
    out += f'<text x="{A.width - A.scale*12:g}" y="{6*A.scale:g}" style="font-size:{A.scale:g}">{Party.BLUE.value[0]} to {Party.RED.value[0]}: {100.0*A.blue_to_red:.1f}%</text>'
    out += f'<text x="{A.width - A.scale*12:g}" y="{7*A.scale:g}" style="font-size:{A.scale:g}">{Party.BLUE.value[0]} to {Party.GREEN.value[0]}: {100.0*A.blue_to_green:.1f}%</text>'
    out += '</g>'

    (x0, y0) = p2c(A.start, A.start,  A)
    (x0, y100) = p2c(A.start, A.stop,   A)
    (x100, y0) = p2c(A.stop,  A.start,  A)

    # Draw Y axis
    out += f'<path d="M {x0:g} {A.width:g} V {y100:g}" style="stroke: #222; stroke-width: {A.scale * 0.2:g}px" marker-end="url(#triangle)"/>'
    out += f'<text transform="translate({(x0 - (A.offset - 1)*A.scale):g}, {A.width/2 :g}) rotate(270)" style="text-anchor:middle">{Party.GREEN.value[0]} 3CP</text>'

    for g in A.marks:
        if g > A.start and g <= (A.stop):
            (xpos, ypos) = p2c(A.start, g, A)
            out += f'<path d="M {xpos:g} {ypos:g} h {-A.scale:g}" style="stroke: #222; stroke-width: {A.scale * 0.2:g}px"/>'
            out += f'<text y="{(ypos + A.scale/2):g}" x="{(xpos - 3*A.scale):g}" style="font-size:{A.scale:g}; text-anchor:right; text-align:middle">{g:.0%}</text>'

    # Draw X axis
    out += f'<path d="M {0:g} {y0:g} H {x100:g}" style="stroke: #222; stroke-width: {A.scale * 0.2:g}px" marker-end="url(#triangle)"/>'
    out += f'<text x="{A.width/2:g}" y="{y0 + 3.5*A.scale:g}" style="text-anchor:middle">{Party.BLUE.value[0]} 3CP</text>'

    for b in A.marks:
        if b > A.start and b <= (A.stop):
            (xpos, ypos) = p2c(b, A.start, A)
            out += f'<path d="M {xpos:g} {ypos:g} v {A.scale:g}" style="stroke: #222; stroke-width: {A.scale * 0.2:g}px"/>'
            out += f'<text x="{xpos:g}" y="{ypos + 2*A.scale:g}" style="font-size:{A.scale}; text-anchor:middle">{b:.0%}</text>'

    out += "\r\n<!-- Generated by https://abjago.net/3pp/ -->\r\n"
    out += "</svg>"

    return out


def get_args(args=None) -> argparse.Namespace:
    """pass args='' for defaults, or leave as None for checking argv.
    DEFAULT VALUES are set here."""
    import argparse

    parser = argparse.ArgumentParser(description=f"Three-Candidate-Preferred Visualiser.\
        Constructs a 2D graph with {Party.BLUE.value[0]} on the X-axis, \
        {Party.GREEN.value[0]} on the Y-axis, and dots shaded by winning party.\
        Prints an SVG to standard output and optionally takes a CSV of points of interest.\
        N.B. all numeric values should be between zero and one.")

    parser.add_argument("--green-to-red", default=0.8, type=float,
                        help=f"{Party.GREEN.value[0]}-to-{Party.RED.value[0]} preference ratio (default: %(default)g)")
    parser.add_argument("--green-to-blue", default=0.2, type=float,
                        help=f"{Party.GREEN.value[0]}-to-{Party.BLUE.value[0]} preference ratio (default: %(default)g)")
    parser.add_argument(f"--red-to-green", default=0.8, type=float,
                        help=f"{Party.RED.value[0]}-to-{Party.GREEN.value[0]} preference ratio (default: %(default)g)")
    parser.add_argument(f"--red-to-blue", default=0.2, type=float,
                        help=f"{Party.RED.value[0]}-to-{Party.BLUE.value[0]} preference ratio (default: %(default)g)")
    parser.add_argument(f"--blue-to-red", default=0.7, type=float,
                        help=f"{Party.BLUE.value[0]}-to-{Party.RED.value[0]} preference ratio (default: %(default)g)")
    parser.add_argument(f"--blue-to-green", default=0.3, type=float,
                        help=f"{Party.BLUE.value[0]}-to-{Party.GREEN.value[0]} preference ratio (default: %(default)g)")
    parser.add_argument("--start", default=0.2, type=float,
                        help="minimum X and Y axis value (default: %(default)g)")
    parser.add_argument("--stop", default=0.6, type=float,
                        help="maximum X and Y axis value (default: %(default)g)")
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
    parser.add_argument(
        "--input", "-i", help="input CSV of points of interest (format: x, y, label) (pass - for standard input)")
    parser.add_argument("--output", "-o", type=argparse.FileType('w'),
                        default=sys.stdout, help="output SVG (default: standard output)")

    return (parser.parse_args(args))


def validate_args(A: argparse.Namespace) -> argparse.Namespace:
    # Clamp A.step to be in a reasonable range
    A.step = max(min(abs(A.step), 0.05), 0.002)

    # clamp A.start to be a usable range
    A.start = max(min(abs(A.start), 0.5 - 10*A.step), 0.0)

    # If (1 - A.stop) < A.start the graph gets wonky
    A.stop = min(abs(A.stop), 1 - A.start)

    # Calculate sizes...
    A.inner_width = A.scale * 100.0 * (A.stop - A.start)
    A.width = (A.offset + 1) * A.scale + \
        A.inner_width  # extra on right and top
    # A.scale is pixels per percent, A.step is percent per dot
    A.radius = 50.0 * A.scale * A.step

    # Clamp our preference flows...

    A.green_to_red = max(min(abs(A.green_to_red),  1.0), 0.0)
    A.red_to_green = max(min(abs(A.red_to_green),  1.0), 0.0)
    A.blue_to_red = max(min(abs(A.blue_to_red),   1.0), 0.0)
    A.green_to_blue = max(min(abs(A.green_to_blue),  1.0), 0.0)
    A.red_to_blue = max(min(abs(A.red_to_blue),  1.0), 0.0)
    A.blue_to_green = max(min(abs(A.blue_to_green),   1.0), 0.0)

    # ... and conditionally normalise them
    red_total = A.red_to_green + A.red_to_blue
    if red_total > 1.0:
        A.red_to_green /= red_total
        A.red_to_blue /= red_total

    green_total = A.green_to_red + A.green_to_blue
    if green_total > 1.0:
        A.green_to_red /= green_total
        A.green_to_blue /= green_total

    blue_total = A.blue_to_green + A.blue_to_red
    if blue_total > 1.0:
        A.blue_to_green /= blue_total
        A.blue_to_red /= blue_total

    return A


# the main shoparty!
if __name__ == "__main__":
    try:
        A = validate_args(get_args())
        # print(A, file=sys.stderr)
        print(construct_svg(A), file=A.output)
    except ValueError as e:
        print(e, file=sys.stderr)
