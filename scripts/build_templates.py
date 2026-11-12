"""Generate the DOCX templates and manifest.json in web/content/templates/.

Original wording only. Every template needs a human review before it is
published: set "reviewed_on" in REVIEWED below once a person has signed it off.
Run: python3 scripts/build_templates.py   (output is deterministic)
"""

import json
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent / "web" / "content" / "templates"
VERSION = "1.0"
REVIEWED: dict[str, str | None] = {}  # slug -> ISO date after human review

# Block types: ("h", text) heading, ("p", text) paragraph, ("b", text) bullet,
# ("c", text) tick-box line.
T = {
    "job-description": (
        "Job description (with worked example)",
        "A one-page job description with a filled-in example for a Customer Support Officer.",
        [
            ("h", "Job description"),
            (
                "p",
                "Job title: [title]    Department: [department]    Reports to: [manager]",
            ),
            (
                "p",
                "Location: [site or remote]    Hours: [hours per week]    Salary: [range or rate]",
            ),
            ("h", "Purpose of the role"),
            (
                "p",
                "[Two or three sentences on why the role exists and what it achieves.]",
            ),
            ("h", "Main duties"),
            ("b", "[Duty 1]"),
            ("b", "[Duty 2]"),
            ("b", "[Duty 3]"),
            ("h", "Skills and experience"),
            ("b", "Essential: [list]"),
            ("b", "Desirable: [list]"),
            ("h", "Right to work"),
            (
                "p",
                "The successful candidate must be able to prove their right to work in the UK before they start.",
            ),
            ("h", "Worked example: Customer Support Officer"),
            (
                "p",
                "Reports to: Support Team Lead. Location: Leeds office, hybrid. Hours: 37.5 per week. Salary: 26,000 to 29,000 a year.",
            ),
            (
                "p",
                "Purpose: answer customer questions by phone and email and resolve them at the first contact where possible.",
            ),
            ("b", "Reply to customer emails within one working day."),
            ("b", "Record every contact in the support system."),
            ("b", "Pass on complex cases to the team lead with clear notes."),
            ("b", "Essential: clear written English and a calm manner on the phone."),
        ],
    ),
    "offer-letter-standard": (
        "Offer letter: standard",
        "Offer of permanent employment on a salary.",
        [
            ("h", "Offer of employment"),
            ("p", "[Date]"),
            ("p", "Dear [name],"),
            (
                "p",
                "We are pleased to offer you the position of [job title] with [company], starting on [start date].",
            ),
            ("b", "Salary: [amount] a year, paid monthly in arrears."),
            ("b", "Hours: [hours] a week, [days]."),
            ("b", "Place of work: [location]."),
            ("b", "Holiday: [days] days a year including bank holidays."),
            ("b", "Probation: [length], then confirmed in writing."),
            ("h", "Conditions"),
            (
                "p",
                "This offer depends on you proving your right to work in the UK, and on [references or checks]. A full written statement of terms will follow within the legal time limit.",
            ),
            ("p", "Please sign and return a copy by [date]."),
            ("p", "Yours sincerely, [name, job title]"),
            ("p", "Accepted: ______________________  Date: ____________"),
        ],
    ),
    "offer-letter-sponsored": (
        "Offer letter: sponsored worker",
        "Offer of employment that depends on a Certificate of Sponsorship.",
        [
            ("h", "Offer of employment (sponsored role)"),
            ("p", "[Date]"),
            ("p", "Dear [name],"),
            (
                "p",
                "We would like to offer you the position of [job title] with [company], starting on [start date], subject to the conditions below.",
            ),
            (
                "b",
                "Salary: [amount] a year. It will not fall below the minimum required for your visa.",
            ),
            ("b", "Occupation code: [SOC code]. Hours: [hours] a week."),
            ("b", "Place of work: [location]."),
            ("h", "Conditions"),
            (
                "b",
                "We must assign you a Certificate of Sponsorship and you must be granted permission to work in this role.",
            ),
            (
                "b",
                "You must tell us promptly about any change of address, contact details or passport.",
            ),
            (
                "b",
                "You must not start work until your permission is valid and we have checked your documents.",
            ),
            (
                "p",
                "Please keep us informed of your visa application. We will pay the costs listed here: [costs].",
            ),
            ("p", "Yours sincerely, [name, job title]"),
            ("p", "Accepted: ______________________  Date: ____________"),
        ],
    ),
    "offer-letter-hourly": (
        "Offer letter: hourly or casual",
        "Offer of work paid by the hour, with or without guaranteed hours.",
        [
            ("h", "Offer of work"),
            ("p", "[Date]"),
            ("p", "Dear [name],"),
            (
                "p",
                "We are pleased to offer you work as [job title] with [company], starting on [start date].",
            ),
            ("b", "Pay: [rate] an hour, paid [weekly or monthly]."),
            (
                "b",
                "Hours: [guaranteed hours, or state that no hours are guaranteed and how shifts are offered].",
            ),
            ("b", "Holiday: paid holiday builds up as you work, as the law sets out."),
            ("b", "Place of work: [location]."),
            ("h", "Conditions"),
            (
                "p",
                "This offer depends on you proving your right to work in the UK before your first shift.",
            ),
            ("p", "Yours sincerely, [name, job title]"),
            ("p", "Accepted: ______________________  Date: ____________"),
        ],
    ),
    "right-to-work-checklist": (
        "Right to Work check checklist",
        "Steps to record for each right to work check, with a follow-up date.",
        [
            ("h", "Right to Work check checklist"),
            ("p", "Name: [name]    Role: [role]    Start date: [date]"),
            ("c", "Check made before the person started work."),
            (
                "c",
                "Route used: share code / identity document service / original documents.",
            ),
            (
                "c",
                "The person is the one shown in the documents (face to photo, in person or on video).",
            ),
            ("c", "Documents are genuine and not changed."),
            ("c", "Permission allows this type of work and these hours."),
            ("c", "Copy or record saved securely with the date of the check."),
            ("c", "Checker's name and date written on the record."),
            ("c", "Follow-up date set if permission has an end date: [date]."),
            ("p", "Checked by: ______________________  Date: ____________"),
        ],
    ),
    "new-starter-checklist": (
        "New starter checklist",
        "Tasks to finish before and after a new person's first day.",
        [
            ("h", "New starter checklist"),
            ("p", "Name: [name]    Role: [role]    Start date: [date]"),
            ("h", "Before day one"),
            ("c", "Signed offer letter received."),
            ("c", "Right to work check done and recorded."),
            ("c", "Contract or written statement of terms issued."),
            ("c", "Bank, tax and pension details collected."),
            ("c", "Equipment and accounts ready."),
            ("h", "First week"),
            ("c", "Welcome, tour and health and safety briefing."),
            ("c", "Policies shared and read."),
            ("c", "Manager sets first-month goals."),
            ("c", "Probation review dates booked."),
        ],
    ),
}

NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def para(kind: str, text: str) -> str:
    t = escape(text)
    if kind == "h":
        return f'<w:p><w:pPr><w:spacing w:before="240"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="28"/></w:rPr><w:t xml:space="preserve">{t}</w:t></w:r></w:p>'
    prefix = {"b": "• ", "c": "☐ "}.get(kind, "")
    ind = '<w:pPr><w:ind w:left="360"/></w:pPr>' if prefix else ""
    return f'<w:p>{ind}<w:r><w:t xml:space="preserve">{escape(prefix)}{t}</w:t></w:r></w:p>'


def docx(title: str, blocks: list) -> bytes:
    import io

    body = "".join(para(k, t) for k, t in blocks)
    body += para(
        "p",
        f"Template version {VERSION}. Draft for your own use; check it suits your situation.",
    )
    parts = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
        "word/document.xml": f'<?xml version="1.0" encoding="UTF-8"?><w:document {NS}><w:body>{body}</w:body></w:document>',
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    return buf.getvalue()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for slug, (title, desc, blocks) in T.items():
        (OUT / f"{slug}.docx").write_bytes(docx(title, blocks))
        manifest.append(
            {
                "slug": slug,
                "title": title,
                "description": desc,
                "file": f"{slug}.docx",
                "version": VERSION,
                "reviewed_on": REVIEWED.get(slug),
            }
        )
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
