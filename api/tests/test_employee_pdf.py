"""Employee-controlled text is escaped before rendering; PDFs cannot fetch any resources."""

import pytest

from app.modules.employees.record_pdf import _no_resources, record_html


def test_pdf_template_escapes_values_and_excludes_identifiers() -> None:
    html = record_html(
        '<img src="file:///etc/passwd">',
        "02 Nov 2026",
        [
            (
                "Notes",
                [
                    {
                        "id": "private-id",
                        "text": "<script>unsafe</script>",
                        "department_id": "internal-id",
                    }
                ],
            )
        ],
    )
    assert "<img src=" not in html
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "private-id" not in html
    assert "internal-id" not in html
    for url in ("file:///etc/passwd", "https://example.com", "data:text/plain,hello"):
        with pytest.raises(ValueError, match="not allowed"):
            _no_resources(url)
