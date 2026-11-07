"""T11.4 interview invites: the RFC 5545 fields, escaping, folding and UTC times."""

from __future__ import annotations

from datetime import UTC, datetime

from app.modules.recruitment.ics import interview_ics


def _unfold(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.split("\r\n"):
        if raw.startswith(" ") and lines:
            lines[-1] += raw[1:]
        elif raw:
            lines.append(raw)
    return lines


def test_the_invite_has_the_fields_a_calendar_needs() -> None:
    text = interview_ics(
        uid="interview-1@example.test",
        starts=datetime(2026, 11, 12, 14, 30, tzinfo=UTC),
        duration_minutes=45,
        summary="Interview: Ada Test, Barista",
        location="Video call; link to follow",
        description="Panel: Sam, Lee; bring a CV",
        attendees=[("Sam Lee", "sam@example.com"), ("Ada Test", "ada@example.com")],
        organizer=("Brand HR Ltd", "hr@example.com"),
        stamp=datetime(2026, 11, 7, 9, 0, tzinfo=UTC),
    )
    assert text.endswith("\r\n")
    lines = _unfold(text)
    assert lines[0] == "BEGIN:VCALENDAR"
    assert lines[-1] == "END:VCALENDAR"
    fields = dict(
        line.split(":", 1) for line in lines if ":" in line and not line.startswith("ATTENDEE")
    )
    assert fields["VERSION"] == "2.0"
    assert fields["UID"] == "interview-1@example.test"
    assert fields["DTSTART"] == "20261112T143000Z"
    assert fields["DTEND"] == "20261112T151500Z"
    assert fields["DTSTAMP"] == "20261107T090000Z"
    organizer = [line for line in lines if line.startswith("ORGANIZER")]
    assert organizer == ["ORGANIZER;CN=Brand HR Ltd:mailto:hr@example.com"]
    assert lines.index(organizer[0]) == lines.index("DTSTAMP:20261107T090000Z") + 1
    assert fields["SUMMARY"] == "Interview: Ada Test\\, Barista"
    assert fields["DESCRIPTION"] == "Panel: Sam\\, Lee\\; bring a CV"
    attendees = [line for line in lines if line.startswith("ATTENDEE")]
    assert attendees == [
        "ATTENDEE;CN=Sam Lee;RSVP=TRUE:mailto:sam@example.com",
        "ATTENDEE;CN=Ada Test;RSVP=TRUE:mailto:ada@example.com",
    ]


def test_long_lines_are_folded_at_75_octets_without_splitting_characters() -> None:
    long_note = "Café " * 40
    text = interview_ics(
        uid="x@example.test",
        starts=datetime(2026, 11, 12, 9, 0, tzinfo=UTC),
        duration_minutes=60,
        summary="Interview",
        location="Office",
        description=long_note,
        attendees=[],
        organizer=("Brand HR Ltd", "hr@example.com"),
        stamp=datetime(2026, 11, 7, 9, 0, tzinfo=UTC),
    )
    for raw in text.split("\r\n"):
        if raw:
            assert len(raw.encode("utf-8")) <= 75, raw
    assert "".join(_unfold(text)).count("Café") == 40


def test_text_with_a_line_break_is_escaped() -> None:
    text = interview_ics(
        uid="y@example.test",
        starts=datetime(2026, 11, 12, 9, 0, tzinfo=UTC),
        duration_minutes=30,
        summary="Interview",
        location="Room 1",
        description="First line\nSecond, line; with \\ slash",
        attendees=[],
        organizer=("Brand HR Ltd", "hr@example.com"),
        stamp=datetime(2026, 11, 7, 9, 0, tzinfo=UTC),
    )
    assert "DESCRIPTION:First line\\nSecond\\, line\\; with \\\\ slash" in _unfold(text)
