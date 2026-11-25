"""The sponsorship checker report, as HTML and PDF (plan 8.17 step 5, T15.6).

The report is built from the saved check only (its inputs, the code, the rules version and the
engine's answer), so it is the same whenever it is printed. It always carries the disclaimer and the
rules version. The PDF is made by the same WeasyPrint route as the employee records (R4).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from jinja2 import Environment

from app.modules.employees.record_pdf import render_pdf_async

if TYPE_CHECKING:
    from app.modules.soc.models import SocCheck

DISCLAIMER = (
    "General guidance, not legal or immigration advice. Check the rules on GOV.UK, or with an "
    "adviser or CASCOT, before you rely on this."
)
INPUT_LABELS = (
    ("weekly_hours", "Weekly hours"),
    ("offered_salary", "Offered salary"),
    ("salary_per", "Salary per"),
    ("work_nation", "Work location (nation)"),
    ("cos_assignment_date", "Certificate of Sponsorship assignment date"),
    ("situation", "Applicant situation"),
)
# A constant template; every value is escaped (autoescape), and WeasyPrint fetches no resources.
# nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2
TEMPLATE = Environment(autoescape=True).from_string(
    """<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<title>Sponsorship job checker report</title>
<style>
  body { font-family: sans-serif; font-size: 10.5pt; color: #111; }
  h1 { font-size: 18pt; margin: 0 0 4pt; }
  h2 { font-size: 12.5pt; margin: 16pt 0 6pt; border-bottom: 1px solid #bbb; padding-bottom: 2pt; }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 3pt 4pt; vertical-align: top;
           border-bottom: 1px solid #e3e3e3; }
  .muted { color: #555; }
  .disclaimer { border: 1px solid #888; padding: 6pt 8pt; margin-top: 18pt; font-size: 9.5pt; }
</style>
</head>
<body>
<h1>Sponsorship job checker report</h1>
<p class="muted">Rules: {{ rules_name }}, effective {{ rules_effective }}.
 Status: {{ status }}{% if confirmed_on %}, confirmed {{ confirmed_on }}{% endif %}.</p>

<h2>Code</h2>
<p><strong>{{ soc_code }}</strong> {{ soc_title }}</p>
<p>Eligibility: {{ eligibility }}</p>

<h2>Job and pay</h2>
<table>
{% for label, value in inputs %}<tr><th style="width: 40%">{{ label }}</th><td>{{ value }}</td></tr>
{% endfor %}</table>

<h2>Minimum pay for this code</h2>
<table>
<tr><th>Option</th><th>Criteria</th><th>Going rate</th><th>Minimum required</th><th>Meets</th></tr>
{% for option in options %}<tr>
  <td>{{ option.option }}</td><td>{{ option.criteria }}</td><td>{{ option.going }}</td>
  <td>{{ option.minimum }}</td><td>{{ option.meets }}</td>
</tr>
{% endfor %}</table>

<h2>Verdict</h2>
<p>{{ verdict }}</p>
<p>Dependants allowed: {{ dependants }}.</p>

{% if notes %}<h2>Notes</h2>
<ul>{% for note in notes %}<li>{{ note }}</li>{% endfor %}</ul>{% endif %}

<div class="disclaimer">{{ disclaimer }}</div>
</body>
</html>
"""
)


def _yes_no(value: bool | None) -> str:
    if value is None:
        return "Needs a band or role first"
    return "Yes" if value else "No"


def _money(value: Any) -> str:
    return "" if value in (None, "") else f"£{value}"


def _verdict(verdict: dict[str, Any]) -> str:
    if verdict.get("meets") is True:
        return f"Meets the minimum for option {verdict.get('option')}."
    if verdict.get("meets") is False:
        short = _money(verdict.get("short_by"))
        hours = verdict.get("hours_needed")
        more = f" The same hourly pay would need {hours} hours a week." if hours else ""
        return f"Short by {short} of the minimum.{more}"
    return "Cannot be decided yet: this code needs a band or role (see the notes)."


def report_html(row: SocCheck) -> str:
    result: dict[str, Any] = row.result
    inputs: dict[str, Any] = row.inputs
    rows = []
    for key, label in INPUT_LABELS:
        value = inputs.get(key)
        if key == "offered_salary":
            value = _money(value)
        elif key == "situation" and value is not None:
            value = str(value).replace("_", " ")
        rows.append((label, "" if value is None else str(value)))
    options = [
        {
            "option": option["option"],
            "criteria": str(option["criteria_key"]).replace("_", " "),
            "going": "" if option.get("going_rate") is None else f"£{option['going_rate']}",
            "minimum": "Not applicable"
            if option.get("minimum_required") is None
            else f"£{option['minimum_required']}",
            "meets": _yes_no(option.get("meets")),
        }
        for option in result.get("options", [])
    ]
    confirmed = row.confirmed_at.strftime("%d %B %Y") if row.confirmed_at else None
    return TEMPLATE.render(
        rules_name=row.rules_version_name,
        rules_effective=row.rules_effective_from.strftime("%d %B %Y"),
        status="confirmed" if row.status == "confirmed" else "draft",
        confirmed_on=confirmed,
        soc_code=row.soc_code,
        soc_title=row.soc_title,
        eligibility=result.get("eligibility", {}).get("label", ""),
        inputs=rows,
        options=options,
        verdict=_verdict(result.get("verdict", {})),
        dependants="yes" if result.get("dependants_allowed") else "no",
        notes=result.get("notes", []),
        disclaimer=DISCLAIMER,
    )


async def report_pdf(row: SocCheck) -> bytes:
    return await render_pdf_async(report_html(row))
