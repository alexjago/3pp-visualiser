import urllib.parse
import os.path
import re
import argparse

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
    """Update the argparse namespace from the query dict. """
    A = visualise.get_args("")

    for k in query_dict:
        if k in vars(A):
            vars(A)[k] = query_dict[k]

    # Not these though. #blocked
    A.css = None
    A.input = None
    A.output = None

    return A


def application(env, start_response):
    head = ["200 OK", [("Content-Type", "text/html")]]
    body = b""

    # print(env)

    doc_root = env["DOCUMENT_ROOT"]
    page_root = os.path.dirname(env["PATH_INFO"])[1:]  # drop leading /

    # do intelligent things based on env['QUERY_STRING']
    query_dict = urllib.parse.parse_qs(env["QUERY_STRING"])
    # print(query_dict)

    # Now get the response out
    body = (visualise.construct_svg(make_args(query_dict))).encode("utf8")

    # Name the file we return
    head[1].append(
        (
            "Content-Disposition",
            (
                'inline; filename="'
                + re.sub(
                    "[^0-9a-zA-Z-_.]+",
                    "-",
                    "3pp_vis.svg", # TODO something to do with query_dict here
                )
                + '"'
            ),
        )
    )
    # cache it for a day, but only in the browser
    head[1].append(("Cache-Control", "private; max-age=86400"))

    # check head status again rather than an else, just in case something went wrong
    if not head[0] == "200 OK":
        body = (head[0] + " " + repr(query_dict)).encode("utf8")
        head[1] = [
            ("Content-Type", "text/html")
        ]  # reverts whatever we did with Content-Disposition

    # print(repr(head))
    start_response(head[0], head[1])
    return [body]
