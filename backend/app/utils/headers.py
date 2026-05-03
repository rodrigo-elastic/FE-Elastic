"""
filename: headers.py
description: Helpers to render canonical Python and HTML file headers.
date: 02-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from datetime import date

PY_HEADER = (
    '"""\n'
    "filename: {filename}\n"
    "description: {description}\n"
    "date: {date}\n"
    '"""\n'
    '__author__ = "Rodrigo Careaga"\n'
    '__copyright__ = "Copyright 2026, Rodrigo Careaga"\n'
    '__version__ = "0.1.0"\n'
    '__status__ = "Development"\n'
)

HTML_HEADER = (
    "<!--\n"
    "  filename: {filename}\n"
    "  description: {description}\n"
    "  Author: Rodrigo Careaga\n"
    "  Date: {date}\n"
    "-->\n"
)


def py_header(filename: str, description: str) -> str:
    return PY_HEADER.format(
        filename=filename, description=description, date=date.today().strftime("%d-%m-%Y")
    )


def html_header(filename: str, description: str) -> str:
    return HTML_HEADER.format(
        filename=filename, description=description, date=date.today().strftime("%d-%m-%Y")
    )
