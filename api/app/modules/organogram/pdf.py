"""The org chart as a PDF (plan 8.13). Text only, rendered by the WeasyPrint path for records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment


def _count(people: list[dict[str, Any]]) -> int:
    total = 0
    stack = list(people)
    while stack:
        person = stack.pop()
        total += 1
        stack.extend(person["reports"])
    return total


def org_chart_html(people: list[dict[str, Any]], *, generated: str, rtw_visible: bool) -> str:
    # FastAPI has no Flask render_template. Values are escaped by autoescape, and the trusted local
    # template cannot fetch resources in the PDF renderer (see employees/record_pdf.py).
    # nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2
    template = Environment(autoescape=True).from_string(
        Path(__file__).with_name("organogram.html").read_text()
    )
    return template.render(
        people=people,
        count=_count(people),
        generated=generated,
        rtw_visible=rtw_visible,
    )
