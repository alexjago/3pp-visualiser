import urllib.parse
import os.path

# local copy
import visualise

def esc(str):
    """XML escape, but forward slashes are also converted to entity references
    and whitespace control characters are converted to spaces"""
    from xml.sax.saxutils import escape

    return escape(
        str, {"\n": " ", "\t": " ", "\b": " ", "\r": " ", "\f": " ", "/": "&#47;"}
    )

def make_args(query_dict):
    """Update the argparse namespace from the query dict."""

    A = visualise.get_args("")

    string_fields = {"x_name", "y_name", "z_name",
                     "x_colour", "y_colour", "z_colour"}

    for k, values in query_dict.items():
        if k not in vars(A) or not values:
            continue
        if k == "chart_mode":
            if values[0] in {"cartesian", "ternary"}:
                vars(A)[k] = values[0]
            continue
        if k in string_fields:
            vars(A)[k] = values[0]
            continue
        try:
            vars(A)[k] = float(values[0])
        except (TypeError, ValueError):
            continue

    # Not these though. #blocked
    A.css = None
    A.input = None
    A.output = None
    A.marks = [i/10.0 for i in range(0, 10)]
    # and keep this reasonable too
    A.step = max(0.005, A.step)

    # Canonical flow params always override legacy aliases when both exist
    flow_aliases = {
        "x_to_y": "blue_to_green",
        "x_to_z": "blue_to_red",
        "y_to_x": "green_to_blue",
        "y_to_z": "green_to_red",
        "z_to_x": "red_to_blue",
        "z_to_y": "red_to_green",
    }
    for canonical, legacy in flow_aliases.items():
        if canonical in query_dict and query_dict[canonical]:
            try:
                vars(A)[canonical] = float(query_dict[canonical][0])
            except (TypeError, ValueError):
                pass
        elif legacy in query_dict and query_dict[legacy]:
            try:
                vars(A)[canonical] = float(query_dict[legacy][0])
            except (TypeError, ValueError):
                pass

    if 'px' in query_dict and 'py' in query_dict and 'pl' in query_dict:
        A.point = []
        for i in range(len(query_dict['px'])):
            try:
                px = float(query_dict['px'][i])
                py = float(query_dict['py'][i])
                pl = esc(query_dict['pl'][i])
                A.point.append([px, py, pl])
            except:
                continue

    return visualise.validate_args(A)


def download_filename(A):
    """Return a deterministic SVG filename using canonical argument names."""
    parts = [
        "3pp_vis",
        A.chart_mode,
        f"x_to_y{A.x_to_y:g}",
        f"x_to_z{A.x_to_z:g}",
        f"y_to_x{A.y_to_x:g}",
        f"y_to_z{A.y_to_z:g}",
        f"z_to_x{A.z_to_x:g}",
        f"z_to_y{A.z_to_y:g}",
    ]

    if A.chart_mode == "ternary":
        parts.extend([
            f"x_min{A.x_min:g}",
            f"x_max{A.x_max:g}",
            f"y_min{A.y_min:g}",
            f"y_max{A.y_max:g}",
            f"z_min{A.z_min:g}",
            f"z_max{A.z_max:g}",
        ])
    else:
        parts.extend([
            f"start{A.start:g}",
            f"stop{A.stop:g}",
        ])

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
