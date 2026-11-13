"""An iCalendar (RFC 5545) invite for one interview, built by hand.

Text is escaped (backslash, semicolon, comma, newline), lines are folded at 75 octets, and times are
written in UTC so every calendar app reads them the same way.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

_FOLD = 75


def _escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> list[str]:
    """Split a line into parts of at most 75 octets. Continuation lines start with a space."""
    encoded = line.encode("utf-8")
    parts: list[str] = []
    start = 0
    limit = _FOLD
    while start < len(encoded):
        end = min(start + limit, len(encoded))
        while end < len(encoded) and (encoded[end] & 0xC0) == 0x80:
            end -= 1  # never split a multi-byte character
        parts.append(encoded[start:end].decode("utf-8"))
        start = end
        limit = _FOLD - 1  # the leading space counts toward the 75 octets of a continuation line
    return [parts[0], *[f" {part}" for part in parts[1:]]] if parts else [""]


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def interview_ics(
    *,
    uid: str,
    starts: datetime,
    duration_minutes: int,
    summary: str,
    location: str,
    description: str,
    attendees: list[tuple[str, str]],
    organizer: tuple[str, str],
    stamp: datetime,
) -> str:
    """One VEVENT in a VCALENDAR. ``attendees`` and ``organizer`` are (name, email) pairs."""
    organizer_name, organizer_email = organizer
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//StuffHub//Recruitment//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:REQUEST",
        "BEGIN:VEVENT",
        f"UID:{_escape(uid)}",
        f"DTSTAMP:{_stamp(stamp)}",
        f"ORGANIZER;CN={_escape(organizer_name)}:mailto:{organizer_email}",
        f"DTSTART:{_stamp(starts)}",
        f"DTEND:{_stamp(starts + timedelta(minutes=duration_minutes))}",
        f"SUMMARY:{_escape(summary)}",
        f"LOCATION:{_escape(location)}",
        f"DESCRIPTION:{_escape(description)}",
        "STATUS:CONFIRMED",
    ]
    for name, email in attendees:
        lines.append(f"ATTENDEE;CN={_escape(name)};RSVP=TRUE:mailto:{email}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    folded: list[str] = []
    for line in lines:
        folded.extend(_fold(line))
    return "\r\n".join(folded) + "\r\n"
