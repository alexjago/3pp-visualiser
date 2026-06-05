import unittest
import warnings
from pathlib import Path
from urllib.parse import parse_qs
from xml.etree import ElementTree
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore", category=PendingDeprecationWarning)

import threeparty
import visualise


def without_parser_warnings(fn, *args, **kwargs):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PendingDeprecationWarning)
        return fn(*args, **kwargs)


def args(argv=None):
    return visualise.validate_args(
        without_parser_warnings(visualise.get_args, argv or "")
    )


def make_args(query):
    return without_parser_warnings(threeparty.make_args, parse_qs(query))


def svg_for(argv=None):
    return visualise.construct_svg(args(argv))


def parse_svg(text):
    return ElementTree.fromstring(text)


def wsgi_response(query):
    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = headers

    body = b"".join(without_parser_warnings(
        threeparty.application,
        {
            "QUERY_STRING": query,
            "PATH_INFO": "/wsgi",
        },
        start_response,
    ))
    return captured["status"], dict(captured["headers"]), body


class ArgumentParsingTests(unittest.TestCase):
    def test_canonical_flow_params_override_legacy_aliases(self):
        A = make_args(
            "blue_to_green=0.9&x_to_y=0.25&"
            "blue_to_red=0.1&x_to_z=0.75"
        )

        self.assertAlmostEqual(A.x_to_y, 0.25)
        self.assertAlmostEqual(A.x_to_z, 0.75)
        self.assertAlmostEqual(A.blue_to_green, A.x_to_y)
        self.assertAlmostEqual(A.blue_to_red, A.x_to_z)

    def test_wsgi_accepts_chart_modes(self):
        cartesian = make_args("chart_mode=cartesian")
        ternary = make_args(
            "chart_mode=ternary&x_min=0.2&x_max=1&"
            "y_min=0.2&y_max=1&z_min=0.2&z_max=1"
        )

        self.assertEqual(cartesian.chart_mode, "cartesian")
        self.assertEqual(ternary.chart_mode, "ternary")

    def test_labels_and_colours_are_normalised(self):
        A = make_args(
            "x_name=%20Custom%20X%20&y_name=&z_name=Custom%20Z&"
            "x_colour=%23ABCDEF&y_colour=not-a-colour&z_colour=%23123"
        )

        self.assertEqual(A.x_name, "Custom X")
        self.assertEqual(A.y_name, "Greens")
        self.assertEqual(A.z_name, "Custom Z")
        self.assertEqual(A.x_colour, "#abcdef")
        self.assertEqual(A.y_colour, "#0a2")
        self.assertEqual(A.z_colour, "#123")


class ValidationTests(unittest.TestCase):
    def test_cartesian_start_stop_normalise(self):
        A = args(["--start", "0.2", "--stop", "0.6", "--step", "0.02"])

        self.assertEqual(A.chart_mode, "cartesian")
        self.assertAlmostEqual(A.start, 0.2)
        self.assertAlmostEqual(A.stop, 0.6)
        self.assertAlmostEqual(A.x_min, 0.2)
        self.assertAlmostEqual(A.x_max, 0.6)
        self.assertAlmostEqual(A.y_min, 0.2)
        self.assertAlmostEqual(A.y_max, 0.6)
        self.assertAlmostEqual(A.z_min, 0.0)
        self.assertAlmostEqual(A.z_max, 1.0)

    def test_ternary_bounds_produce_drawable_polygon(self):
        A = args([
            "--ternary",
            "--x-min", "0.2", "--x-max", "1",
            "--y-min", "0.2", "--y-max", "1",
            "--z-min", "0.2", "--z-max", "1",
        ])

        self.assertEqual(A.chart_mode, "ternary")
        self.assertEqual(len(A.ternary_polygon), 3)
        self.assertGreater(A.width, 0)
        self.assertGreater(A.height, 0)

    def test_invalid_ternary_minimum_bounds_raise(self):
        with self.assertRaisesRegex(ValueError, "minimum ternary bounds"):
            args([
                "--ternary",
                "--x-min", "0.5",
                "--y-min", "0.5",
                "--z-min", "0.1",
            ])

    def test_invalid_ternary_maximum_bounds_raise(self):
        with self.assertRaisesRegex(ValueError, "maximum ternary bounds"):
            args([
                "--ternary",
                "--x-max", "0.2",
                "--y-max", "0.2",
                "--z-max", "0.2",
            ])


class SvgOutputTests(unittest.TestCase):
    def test_svg_is_parseable_and_uses_party_fill_classes(self):
        svg = svg_for([
            "--x-colour", "#123456",
            "--y-colour", "#abcdef",
            "--z-colour", "#fedcba",
            "--step", "0.05",
            "--start", "0",
            "--stop", "0.6",
        ])
        root = parse_svg(svg)

        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertIn(".x {fill: #123456}", svg)
        self.assertIn(".y {fill: #abcdef}", svg)
        self.assertIn(".z {fill: #fedcba}", svg)
        self.assertNotIn(".r {fill:", svg)
        self.assertNotIn(".g {fill:", svg)
        self.assertNotIn(".b {fill:", svg)

        classes = {
            circle.attrib.get("class", "")
            for circle in root.iter()
            if circle.tag.endswith("circle")
        }
        self.assertTrue(any("x d" in class_name for class_name in classes))
        self.assertTrue(any("y d" in class_name for class_name in classes))
        self.assertTrue(any("z d" in class_name for class_name in classes))
        self.assertFalse(any(class_name in {"r d", "g d", "b d"} for class_name in classes))
        for circle in root.iter():
            if circle.tag.endswith("circle"):
                self.assertNotIn("fill:", circle.attrib.get("style", ""))

    def test_ternary_svg_has_clip_path_and_parses(self):
        svg = svg_for([
            "--ternary",
            "--step", "0.05",
            "--x-min", "0.2", "--x-max", "1",
            "--y-min", "0.2", "--y-max", "1",
            "--z-min", "0.2", "--z-max", "1",
        ])

        parse_svg(svg)
        self.assertIn('clipPath id="ternaryViewportClip"', svg)
        self.assertIn('clip-path="url(#ternaryViewportClip)"', svg)


class WsgiDownloadTests(unittest.TestCase):
    def test_inline_wsgi_response_uses_inline_disposition(self):
        status, headers, body = wsgi_response("chart_mode=cartesian")

        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Disposition"], "inline")
        self.assertTrue(body.startswith(b"<svg "))

    def test_cartesian_download_filename_uses_canonical_params(self):
        A = make_args(
            "chart_mode=cartesian&x_to_y=0.3&x_to_z=0.7&"
            "y_to_x=0.2&y_to_z=0.8&z_to_x=0.2&z_to_y=0.8&"
            "start=0.2&stop=0.6&step=0.01"
        )
        filename = threeparty.download_filename(A)

        self.assertEqual(
            filename,
            "3pp_vis_cartesian_x_to_y0.3_x_to_z0.7_"
            "y_to_x0.2_y_to_z0.8_z_to_x0.2_z_to_y0.8_"
            "start0.2_stop0.6_step0.01.svg",
        )

    def test_ternary_download_filename_includes_all_bounds(self):
        query = (
            "dl=true&chart_mode=ternary&x_to_y=0.3&x_to_z=0.7&"
            "y_to_x=0.2&y_to_z=0.8&z_to_x=0.2&z_to_y=0.8&"
            "x_min=0.2&x_max=1&y_min=0.2&y_max=1&"
            "z_min=0.2&z_max=1&step=0.01"
        )
        status, headers, _ = wsgi_response(query)

        self.assertEqual(status, "200 OK")
        disposition = headers["Content-Disposition"]
        self.assertIn("download;", disposition)
        self.assertIn("3pp_vis_ternary", disposition)
        for part in [
            "x_to_y0.3", "x_to_z0.7", "y_to_x0.2", "y_to_z0.8",
            "z_to_x0.2", "z_to_y0.8", "x_min0.2", "x_max1",
            "y_min0.2", "y_max1", "z_min0.2", "z_max1", "step0.01",
        ]:
            self.assertIn(part, disposition)


class PoiTests(unittest.TestCase):
    def test_repeated_poi_params_become_points_and_invalid_rows_are_skipped(self):
        A = make_args(
            "px=0.43&py=0.33&pl=Ryan%202022&"
            "px=bad&py=0.29&pl=Invalid&"
            "px=0.36&py=0.29&pl=Brisbane%2Fsample"
        )

        self.assertEqual(A.point, [
            [0.43, 0.33, "Ryan 2022"],
            [0.36, 0.29, "Brisbane&#47;sample"],
        ])

    def test_poi_labels_are_escaped_in_svg(self):
        A = make_args(
            "px=0.43&py=0.33&pl=Bad%2F%3Cname%3E"
        )
        svg = visualise.construct_svg(A)

        parse_svg(svg)
        self.assertIn("Bad&amp;#47;&amp;lt;name&amp;gt;", svg)
        self.assertNotIn("Bad/<name>", svg)

    def test_poi_label_is_visible_and_svg_remains_parseable(self):
        A = args([
            "--step", "0.05",
            "--start", "0.2",
            "--stop", "0.6",
            "--point", "0.43", "0.33", "Ryan 2022",
        ])
        svg = visualise.construct_svg(A)

        parse_svg(svg)
        self.assertIn('class="poi-label"', svg)
        self.assertIn(">Ryan 2022</text>", svg)
        self.assertIn("paint-order:stroke fill markers", svg)
        self.assertIn('class="d poi"', svg)

    def test_blank_poi_label_draws_marker_without_visible_label(self):
        A = args([
            "--step", "0.05",
            "--start", "0.2",
            "--stop", "0.6",
            "--point", "0.43", "0.33", "",
        ])
        svg = visualise.construct_svg(A)

        parse_svg(svg)
        self.assertIn('class="d poi"', svg)
        self.assertNotIn('class="poi-label"', svg)

    def test_visible_poi_label_boxes_do_not_overlap(self):
        A = args([
            "--step", "0.05",
            "--start", "0.2",
            "--stop", "0.6",
            "--point", "0.35", "0.35", "Alpha",
            "--point", "0.35", "0.35", "Beta",
            "--point", "0.35", "0.35", "Gamma",
        ])
        root = parse_svg(visualise.construct_svg(A))
        boxes = [
            {
                "x": float(text.attrib["x"]) - A.scale * 0.35,
                "y": float(text.attrib["y"]) - (A.scale * 1.4) / 2.0,
                "width": len(text.text) * A.scale * 0.62 + 2 * A.scale * 0.35,
                "height": A.scale * 1.4,
            }
            for group in root.iter()
            if group.tag.endswith("g") and group.attrib.get("class") == "poi-label"
            for text in group
            if text.tag.endswith("text")
        ]

        self.assertGreaterEqual(len(boxes), 2)
        for i, first in enumerate(boxes):
            for second in boxes[i + 1:]:
                self.assertFalse(visualise.boxes_overlap(first, second))

        for group in root.iter():
            if group.tag.endswith("g") and group.attrib.get("class") == "poi-label":
                self.assertFalse(any(child.tag.endswith("rect") for child in group))

    def test_ternary_poi_label_is_outside_clipped_marker_group(self):
        A = args([
            "--ternary",
            "--step", "0.05",
            "--x-min", "0.2", "--x-max", "1",
            "--y-min", "0.2", "--y-max", "1",
            "--z-min", "0.2", "--z-max", "1",
            "--point", "0.4", "0.2", "Boundary sample",
        ])
        svg = visualise.construct_svg(A)

        parse_svg(svg)
        self.assertIn('clip-path="url(#ternaryViewportClip)"', svg)
        self.assertIn('class="d poi"', svg)
        self.assertIn('class="poi-label"', svg)
        self.assertLess(
            svg.index('class="d poi"'),
            svg.index('class="poi-label"'),
        )
        self.assertLess(
            svg.index('class="axis"'),
            svg.index('class="poi-label"'),
        )


if __name__ == "__main__":
    unittest.main()
