#!python3

"""
Construct a mouseoverable SVG of three-party-preferred outcomes.

We'll call the three parties "blue" (x-axis), "green" (y-axis) and "red" (with R + G + B == 1).

The primary methods that you'll want to call are `get_args` and `construct_svg`.
"""


DEFAULT_CSS = """
text {font-family: sans-serif; font-size: 10px; fill: #222 }
/* dot, red, green, blue, tie*/
.d {opacity:0.6;}
.d:hover {opacity:1;}
.r {fill: #d04}
.g {fill: #0a2}
.b {fill: #08e}
.t {fill: #888}
/* point of interest */
.poi {stroke:#000; fill-opacity:0.4; stroke-width: 0.2%}
.line {stroke: #222; stroke-width: 0.5%; fill:none}
#triangle {fill: #222}
.bg {fill: #fff}
"""

import argparse
from enum import Enum
import sys
from typing import Tuple

class Party(Enum):
    RED = ("Labor", "r")
    GREEN = ("Greens", "g")
    BLUE = ("Coalition", "b") 

### NOTE: throughout this file we'll use a variable called `A` to store our general state
### This replaces the original and pervasive use of globals.
### Default values are set in `get_args`

def p2c(blue_pct: float, green_pct: float, A: argparse.Namespace) -> Tuple[float, float]:
    '''Percentages to Coordinates'''
    x = ((blue_pct - A.start) / (A.stop - A.start)) * A.inner_width + (A.offset)*A.scale
    y = A.inner_width * (1 - ((green_pct - A.start) / (A.stop - A.start))) + A.scale
    return (x, y)


def calculate_winner(red_pct: float, green_pct: float, blue_pct: float, A: argparse.Namespace) -> Tuple[Party, float]:
    '''Given 3PP percentages, calculate the winner and their 2CP result. 
        Ties for third are resolved where the winner is the same either way, 
        with the tighter 2CP result reported.'''
    # need to figure out who came third, then who won
    if red_pct < green_pct and red_pct < blue_pct:
        # Red came third
        tcp = green_pct + (A.red_to_green * red_pct)
        if tcp > 0.5:
            return (Party.GREEN, tcp)
        else:
            return (Party.BLUE, 1.0 - tcp)
    if green_pct < red_pct and green_pct < blue_pct:
        # Green came third
        tcp = red_pct + (A.green_to_red * green_pct)
        if tcp > 0.5:
            return (Party.RED, tcp)
        else:
            return (Party.BLUE, 1.0 - tcp)
    if blue_pct < red_pct and blue_pct < green_pct:
        # Blue came third
        tcp = red_pct + (A.blue_to_red * blue_pct)
        if tcp > 0.5:
            return (Party.RED, tcp)
        else:
            return (Party.GREEN, 1.0 - tcp)

    # resolve some ties for third
    # if the leading party would win EITHER way, report their win and tightest margin
    # else, return nothing (interpreted as a tie)
    if green_pct == blue_pct and green_pct < red_pct:
        gex = green_pct * A.green_to_red
        bex = blue_pct * A.blue_to_red
        if red_pct + gex > 0.5 and red_pct + bex > 0.5:
            return (Party.RED, red_pct + min(gex, bex))
    if red_pct == blue_pct and red_pct < green_pct:
        rex = red_pct * A.red_to_green
        bex = blue_pct * A.blue_to_green
        if green_pct + rex > 0.5 and green_pct + bex > 0.5:
            return (Party.GREEN, green_pct + min(rex, bex))
    if green_pct == red_pct and green_pct < blue_pct:
        gex = green_pct * A.green_to_blue
        rex = red_pct * A.red_to_blue
        if blue_pct + gex > 0.5 and blue_pct + rex > 0.5:
            return (Party.BLUE, blue_pct + min(gex, rex))


def construct_dot(blue_pct: float, green_pct: float, A: argparse.Namespace) -> str:
    '''Given green and blue percentages, return an SVG fragment corresponding to a dot at the appropriate position.'''
    red_pct = 1.0 - (green_pct + blue_pct)
    
    (x, y) = p2c(blue_pct, green_pct, A)

    tooltip_3cp = f"{Party.GREEN.value[0]}: {green_pct:.1%}, {Party.RED.value[0]}: {red_pct:.1%}, {Party.BLUE.value[0]}: {blue_pct:.1%}."

    try:
        (winner, margin) = calculate_winner(red_pct, green_pct, blue_pct, A)
        tooltip = f"{tooltip_3cp} Winner: {(winner.value)[0]} {margin:.1%}"
        return f'<circle cx="{x:g}" cy="{y:g}" r="{A.radius:g}" class="{(winner.value)[1]} d"><title>{tooltip}</title></circle>'

    except TypeError: # raised on a tie
        tooltip = f"{tooltip_3cp} Winner: TIE"
        return f'<circle cx="{x:g}" cy="{y:g}" r="{A.radius:g}" class="t d"><title>{tooltip}</title></circle>'


def frange(start, stop=None, step=None) -> float:
    '''Floating-point range. [start = 0.0], stop, [step = 1.0]'''
    start = float(start);
    if not stop: # switcheroo
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


def draw_lines(A: argparse.Namespace) -> str:
    """Draw change-of-winner lines."""

    # There are at least 8 points to draw lines between. 

    # Firstly, a line #1-#2-#3
    # 1. Green vs Red on Y axis
    (x1, y1) = p2c(A.start, (0.5 - (A.start * A.blue_to_green)), A)

    # 2. Green vs Rd midpoint. Controlled by ex-Blue split
    # At max Greens-Red preferencing, it varies from 
    # (0.25, 0.5) at full Blue-to-Red
    # degenerates at equal split (to terpoint)
    # (0.25, 0.25) at full Blue-to-Green
    
    # there's a line coming out of the terpoint that (at least for normal values) 
    # A.marks out the "Greens 3CP >= Labor 3CP == Liberal 3CP" 
    #   1 - (g+b) = b

    # and another coming in from #1 that A.marks the Labor-Greens 2CP boundary
    #   g + (b * A.blue_to_green) = 0.5

    # This point is where those lines cross: we have Greens 3CP >= Labor 3CP == Liberal 3CP
    #   g = 0.5 - (b * A.blue_to_green)
    #   b = 1 - ((0.5 - (b * A.blue_to_green)) + b)
    #   b = 0.5 + (b * A.blue_to_green) - b
    #   2b = 0.5 + (b * A.blue_to_green)
    #   b (2 - A.blue_to_green) = 0.5
    #   b = 0.5 / (2 - A.blue_to_green)

    b = 0.5 / (2 - A.blue_to_green)
    g = 0.5 - (b * A.blue_to_green)

    # if A.blue_to_red is less than half, then #2 sits on the b = g line instead
    # (the gradient of the #1-#2 line is still correct)
    if A.blue_to_red <= 0.5:
        # g = 0.5 - (b * A.blue_to_green)
        # g = 0.5 - (g * A.blue_to_green)
        # g (1 + A.blue_to_green) = 0.5
        g = 0.5 / (1 + A.blue_to_green)
        b = g

    (x2, y2) = p2c(b, g, A)


    # 3. the (1/3, 1/3) point ("terpoint")
    # Always some sort of boundary
    (x3, y3) = p2c(1.0/3.0, 1.0/3.0, A)

    # Line #1-#2-#3 represents the Red/Green boundary
    red_green = f'M {x1:g} {y1:g} {x2:g} {y2:g} {x3:g} {y3:g}'

    # 4. Red vs Blue midpoint. Basically the inverse of #2, pA.eterised by ex-Green split
    # same as above except swap b and g and use GREEN_TO_*
    g = 0.5 / (2 - A.green_to_blue)
    b = 0.5 - (g * A.green_to_blue)
    if A.green_to_red <= 0.5:
        b = 0.5 / (1 + A.green_to_blue)
        g = b
    (x4, y4) = p2c(b, g, A)

    # 5. Red vs Blue on X axis 
    (x5, y5) = p2c(0.5 - A.start * A.green_to_blue, A.start, A)

    # Lines #3 - #4 - #5 represents the Red/Blue boundary
    red_blue = f'M {x3:g} {y3:g} {x4:g} {y4:g} {x5:g} {y5:g}'

    # 6. Blue vs Green point. This is controlled by Red's Blue/Green split
    # there's one line coming "out" of the terpoint #3
    # (it's NW if red favours blue, SE if red favours green)
    # and one out of the hapoint #7 (the Red-comes-third line)
    # (mostly W if red favours blue, mostly S if red favours green)
    # This point occurs where these two lines cross
    # (if red favours blue, then red and blue will be equal here)
    # (if red favours green, then red and green will be equal here)
    # degenerates to terpoint if equal ex-Red split

    # terpoint degeneration (A.red_to_blue == 0.5)
    b = 1.0/3.0
    g = 1.0/3.0

    if A.red_to_green == 0.0:
        b = 0.25
        g = 0.5
    elif A.red_to_blue == 0.0:
        b = 0.5
        g = 0.25
    elif A.red_to_blue < 0.5:
        # red's coming third and favouring green
        # we follow the b >= (r == g) line out of the terpoint
        # (1 - (b+g)) == g
        # 1 - b = 2g
        # g = (1 - b)/2

        # we also follow the green == blue 2CP from the hapoint
        # b + r * A.red_to_blue == g + r - r * A.red_to_blue == 0.5

        # b + r * A.red_to_blue = 0.5
        # b + (1 - (b+g))*A.red_to_blue = 0.5
        # b + (1 - (b + ((1-b)/2))) * A.red_to_blue = 0.5
        # b + (1 - (b + 0.5 - 0.5b)) * A.red_to_blue = 0.5
        # b + (1 - (b + 1)/2) * A.red_to_blue = 0.5
        # b + ((1 - b) * A.red_to_blue / 2) = 0.5
        # b - b*A.red_to_blue/2 + A.red_to_blue/2 = 0.5
        # 2b - b*A.red_to_blue + A.red_to_blue = 1
        # b * (2 - A.red_to_blue) + A.red_to_blue = 1
        # b = A.red_to_green / (2 - A.red_to_blue)
        b = A.red_to_green / (2 - A.red_to_blue)
        g = (1 - b)/2

    elif A.red_to_blue > 0.5:
        # transpose of the < 0.5 case... 
        g = A.red_to_blue / (2 - A.red_to_green)
        b = (1 - g)/2

    (x6, y6) = p2c(b, g, A)

    # 7. Green vs Blue on 45 (hapoint)
    # Also always some sort of boundary
    (x7, y7) = p2c(0.5, 0.5, A)

    # Lines #3 - #6 - #7 represents the Blue/Green boundary
    blue_green = f'M {x3:g} {y3:g} {x6:g} {y6:g} {x7:g} {y7:g}' 

    # Unconditionally we also have
    # Top: Green max 45 at top (1 - A.stop, A.stop)
    # Right: Blue max 45 at right (A.stop, 1 - A.stop)
    # (this passes through the hapoint too, but no direction change)
    (xtop, ytop) = p2c(1 - A.stop, A.stop, A)
    (xright, yright) = p2c(A.stop, 1 - A.stop, A)
    top_right = f'M {xtop:g} {ytop:g} {xright:g} {yright:g}'

    # OK, time to draw all the lines!

    return f'<path d="{red_green} {red_blue} {blue_green} {top_right}" class="line" />'

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
            tooltip = f"{r2}\n{Party.GREEN.value[0]}: {r1:.1%}, {Party.RED.value[0]}: {(1 - (r1+r0)):.1%}, {Party.BLUE.value[0]}: {r0:.1%}."

            try:
                (winner, margin) = calculate_winner(1 - (r0 + r1), r1, r0)
                tooltip += f"\nWinner: {winner.value[0]} {margin:.1%}"
            except TypeError: # ties A.n
                tooltip += "\nWinner: TIE"                
            out += f'<circle cx="{x:g}" cy="{y:g}" r="{A.radius:g}" class="d poi"><title>{tooltip}</title></circle>'

        except (TypeError, IndexError, ValueError) as e:
            print("Error while parsing input row:", e, file=sys.stderr)
            print(row, file=sys.stderr)

    return out

def construct_svg(A: argparse.Namespace) -> str:
    """Returns an SVG of the graph for given parameters as specified in `A`."""
    # let's output some SVG!

    out = ""

    out += f'<svg viewBox="0 0 {A.width:.0f} {A.width:.0f}" version="1.1" xmlns="http://www.w3.org/2000/svg">'

    # Set up <defs> section, including our triangle marker and our CSS

    css = DEFAULT_CSS
    if A.css:
        css = (A.css).read()

    out += f'<defs> \
        <marker id="triangle" viewBox="0 0 10 10" \
            refX="1" refY="5" \
            markerUnits="strokeWidth" \
            markerWidth="{A.scale * 0.5}" markerHeight="{A.scale * 0.5}" \
            orient="auto"> \
        <path d="M 0 0 L 10 5 L 0 10 z"/> \
        </marker> \
        <style type="text/css"><![CDATA[ \
            {css} \
        ]]> \
        </style> \
    </defs>'

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

    # draw labels saying assumptions?

    out += f'<text x="{A.width - A.scale*12:g}" y="{2*A.scale:g}" style="font-size:{A.scale:g}">{Party.RED.value[0]} to {Party.GREEN.value[0]}: {100.0*A.red_to_green:.1f}%</text>'
    out += f'<text x="{A.width - A.scale*12:g}" y="{4*A.scale:g}" style="font-size:{A.scale:g}">{Party.GREEN.value[0]} to {Party.RED.value[0]}: {100.0*A.green_to_red:.1f}%</text>'
    out += f'<text x="{A.width - A.scale*12:g}" y="{6*A.scale:g}" style="font-size:{A.scale:g}">{Party.BLUE.value[0]} to {Party.RED.value[0]}: {100.0*A.blue_to_red:.1f}%</text>'

    (x0, y0)   = p2c(A.start, A.stop, A)
    (x0, y100) = p2c(A.start, A.stop, A)
    (x100, y0) = p2c(A.stop, A.start, A)

    # Draw Y axis
    out += f'<path d="M {x0:g} {A.width:g} V {A.scale:g}" style="stroke: #222; stroke-width: {A.scale * 0.2:g}px" marker-end="url(#triangle)"/>'
    out += f'<text transform="translate({(x0 - (A.offset - 1)*A.scale):g}, {A.width/2 :g}) rotate(270)" style="text-anchor:middle">{Party.GREEN.value[0]} 3CP</text>'

    for g in A.marks:
        if g > A.start and g < A.stop:
            (xpos, ypos) = p2c(A.start, g, A)
            out += f'<path d="M {xpos:g} {ypos:g} h {-A.scale:g}" style="stroke: #222; stroke-width: {A.scale * 0.2:g}px"/>'
            out += f'<text y="{(ypos + A.scale/2):g}" x="{(xpos - 3*A.scale):g}" style="font-size:{A.scale:g}; text-anchor:right; text-align:middle">{g:.0%}</text>'


    # Draw X axis 
    out += f'<path d="M {0:g} {y0:g} H {x100:g}" style="stroke: #222; stroke-width: {A.scale * 0.2:g}px" marker-end="url(#triangle)"/>'
    out += f'<text x="{A.width/2:g}" y="{y0 + 3.5*A.scale:g}" style="text-anchor:middle">{Party.BLUE.value[0]} 3CP</text>'


    for b in A.marks:
        if b > A.start and b < A.stop:
            (xpos, ypos) = p2c(b, A.start, A)
            out += f'<path d="M {xpos:g} {ypos:g} v {A.scale:g}" style="stroke: #222; stroke-width: {A.scale * 0.2:g}px"/>'
            out += f'<text x="{xpos:g}" y="{ypos + 2*A.scale:g}" style="font-size:{A.scale}; text-anchor:middle">{b:.0%}</text>'

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
    parser.add_argument(f"--red-to-green", default=0.8, type=float,
        help=f"{Party.RED.value[0]}-to-{Party.GREEN.value[0]} preference ratio (default: %(default)g)")
    parser.add_argument(f"--blue-to-red", default=0.7, type=float,
        help=f"{Party.BLUE.value[0]}-to-{Party.RED.value[0]} preference ratio (default: %(default)g)")
    parser.add_argument("--start", default=0.2, type=float, help="minimum X and Y axis value (default: %(default)g)")
    parser.add_argument("--stop", default=0.6, type=float, help="maximum X and Y axis value (default: %(default)g)")
    parser.add_argument("--step", default=0.01, type=float, help="precision of dots (default: %(default)g)")
    parser.add_argument('--scale', default=10, type=int, help="pixels per percent (default: %(default)g)")
    parser.add_argument('--offset', default=5, type=int, help="multiple of scale factor to A.offset axis by (default: %(default)g)")
    parser.add_argument("--marks", nargs='+', default=[i/10.0 for i in range(0,10)], metavar="MARK", type=float, 
        help="place axis marks at these values (default: every 10%%)")
    parser.add_argument("--css", metavar='FILE', type=argparse.FileType('r'), help="Use CSS from specified file")
    parser.add_argument("--input", "-i", help="input CSV of points of interest (format: x, y, label) (pass - for standard input)")
    parser.add_argument("--output", "-o", type=argparse.FileType('w'), default=sys.stdout, help="output SVG (default: standard output)")

    A = parser.parse_args(args)

    # Infer these...
    A.green_to_blue  = 1.0 - A.green_to_red
    A.red_to_blue    = 1.0 - A.red_to_green
    A.blue_to_green  = 1.0 - A.blue_to_red

    # and these...
    A.inner_width = A.scale * 100.0 * (A.stop - A.start)
    A.width = (A.offset + 1) * A.scale + A.inner_width # extra on right and top
    A.radius = A.inner_width / (((A.stop - A.start) / A.step) * 2)

    if A.red_to_green < 0.0 or A.red_to_green > 1.0:
        print("ERROR: constant RED_TO_GREEN must be between 0.0 and 1.0", file=sys.stderr)
        exit(1)
    if A.green_to_red < 0.0 or A.green_to_red > 1.0:
        print("ERROR: constant GREEN_TO_RED must be between 0.0 and 1.0", file=sys.stderr)
        exit(1)
    if A.blue_to_red < 0.0 or A.blue_to_red > 1.0:
        print("ERROR: constant BLUE_TO_RED must be between 0.0 and 1.0", file=sys.stderr)
        exit(1)

    return A


# the main show!
if __name__ == "__main__":
    A = get_args()
    print(construct_svg(A), file=A.output)
