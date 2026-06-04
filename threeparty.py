import urllib.parse
import os.path

# local copy
import visualise

STRING_FIELDS = {"x_name", "y_name", "z_name",
                 "x_colour", "y_colour", "z_colour"}


def esc(str):
    """XML escape, but forward slashes are also converted to entity references
    and whitespace control characters are converted to spaces"""
    from xml.sax.saxutils import escape

    return escape(
        str, {"\n": " ", "\t": " ", "\b": " ", "\r": " ", "\f": " ", "/": "&#47;"}
    )


def first_query_value(query_dict, key):
    """Return the first query value for a key, or None when absent."""
    values = query_dict.get(key)
    if not values:
        return None
    return values[0]


def first_query_float(query_dict, key):
    """Return the first query value parsed as float, or None when invalid."""
    value = first_query_value(query_dict, key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def apply_query_values(A, query_dict):
    """Apply direct query-string fields to a visualise argument namespace."""
    for key, values in query_dict.items():
        if key not in vars(A) or not values:
            continue
        if key == "chart_mode":
            if values[0] in {"cartesian", "ternary"}:
                vars(A)[key] = values[0]
            continue
        if key in STRING_FIELDS:
            vars(A)[key] = values[0]
            continue
        value = first_query_float(query_dict, key)
        if value is not None:
            vars(A)[key] = value


def apply_flow_alias_query_values(A, query_dict):
    """Apply canonical flow query params, falling back to legacy aliases."""
    for canonical, legacy in visualise.FLOW_ALIASES.items():
        if first_query_value(query_dict, canonical) is not None:
            value = first_query_float(query_dict, canonical)
        else:
            value = first_query_float(query_dict, legacy)
        if value is not None:
            vars(A)[canonical] = value


def query_points(query_dict):
    """Return sanitised point-of-interest rows from repeated query params."""
    if 'px' not in query_dict or 'py' not in query_dict or 'pl' not in query_dict:
        return None

    points = []
    for i in range(len(query_dict['px'])):
        try:
            px = float(query_dict['px'][i])
            py = float(query_dict['py'][i])
            pl = esc(query_dict['pl'][i])
            points.append([px, py, pl])
        except:
            continue
    return points


def make_args(query_dict):
    """Update the argparse namespace from the query dict."""

    A = visualise.get_args("")

    apply_query_values(A, query_dict)

    # Not these though. #blocked
    A.css = None
    A.input = None
    A.output = None
    A.marks = [i/10.0 for i in range(0, 10)]
    # and keep this reasonable too
    A.step = max(0.005, A.step)

    # Canonical flow params always override legacy aliases when both exist
    apply_flow_alias_query_values(A, query_dict)

    points = query_points(query_dict)
    if points is not None:
        A.point = points

    return visualise.validate_args(A)


def filename_flow_parts(A):
    """Return canonical flow parts for SVG download filenames."""
    return [
        f"{field}{getattr(A, field):g}"
        for field in visualise.FLOW_FIELDS
    ]


def filename_bound_parts(A):
    """Return mode-specific bound parts for SVG download filenames."""
    if A.chart_mode == "ternary":
        return [
            f"x_min{A.x_min:g}",
            f"x_max{A.x_max:g}",
            f"y_min{A.y_min:g}",
            f"y_max{A.y_max:g}",
            f"z_min{A.z_min:g}",
            f"z_max{A.z_max:g}",
        ]

    return [
        f"start{A.start:g}",
        f"stop{A.stop:g}",
    ]


def download_filename(A):
    """Return a deterministic SVG filename using canonical argument names."""
    parts = [
        "3pp_vis",
        A.chart_mode,
    ]
    parts.extend(filename_flow_parts(A))
    parts.extend(filename_bound_parts(A))
    parts.append(f"step{A.step:g}")
    return "_".join(parts) + ".svg"



def application(env, start_response):
    head = ["200 OK", [("Content-Type", "image/svg+xml; charset=utf-8")]]
    body = b""

    # print(env)

    # Present behind nginx/uWSGI, but may be absent in local WSGI servers.
    doc_root = env.get("DOCUMENT_ROOT", "")
    page_root = os.path.dirname(env.get("PATH_INFO", ""))[1:]  # drop leading /

    # do intelligent things based on env['QUERY_STRING']
    query_dict = urllib.parse.parse_qs(env["QUERY_STRING"])

    try:
        # Now get the response out
        A = make_args(query_dict)
        body = visualise.construct_svg(A).encode("utf8")

        # Name the file we return
        if query_dict.get("dl", False):
            head[1].append(
                (
                    "Content-Disposition",
                    f'download; filename="{download_filename(A)}"',
                )
            )
        else:
            head[1].append(("Content-Disposition", "inline"))
        
        # One week cache for browser and shared caches (eg Cloudflare).
        head[1].append(("Cache-Control", "public, max-age=604800, s-maxage=604800"))

    except ValueError as e:
        head = ["400 Bad Request", [("Content-Type", "text/plain; charset=utf-8")]]
        body = ("\r\n".join([head[0], str(e) + repr(query_dict)])).encode("utf8")


    start_response(head[0], head[1])
    return [body]
