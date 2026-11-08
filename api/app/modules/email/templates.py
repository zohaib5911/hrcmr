"""The e-mails we send: their wording, and the rules that keep them safe (plan.md T2.8).

Each template names the *only* values it accepts. A caller cannot slip anything else in, so a
careless call cannot put a National Insurance number, a salary or a document name into an e-mail.
Messages say that something needs attention and link to the app, where the person signs in.
Values are escaped in the HTML version, and must be one short line (they also fill the subject).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup, escape

if TYPE_CHECKING:
    from app.core.config import Settings

LAYOUTS = Path(__file__).parent / "layouts"
MAX_VALUE_LENGTH = 300
ACCENT = "#0062c4"


class TemplateError(ValueError):
    """A call that does not match its template. A programming mistake, caught before sending."""


@dataclass(frozen=True)
class Template:
    subject: str
    heading: str
    paragraphs: tuple[str, ...]
    fields: frozenset[str]
    preheader: str
    button: tuple[str, str] | None = None  # (label, the field holding the link)
    secondary: tuple[str, str] | None = None  # a plain text link under the button
    code_field: str | None = None  # a short code shown large (the deletion code)
    small_print: tuple[str, ...] = ()


def _fields(*names: str) -> frozenset[str]:
    return frozenset(names)


TEMPLATES: dict[str, Template] = {
    "rota_published": Template(
        subject="Your rota for {dates}",
        heading="Your rota has been published",
        preheader="Review your schedule in My Shifts.",
        paragraphs=(
            "Hi {first_name},",
            "Your rota for {dates} now contains {shift_count} shifts.",
            "Sign in to review the latest published schedule.",
        ),
        button=("View My Shifts", "link"),
        fields=_fields("first_name", "dates", "shift_count", "link"),
    ),
    "verify_email": Template(
        subject="Confirm your email address",
        heading="Confirm your email address",
        preheader="One click and your account is ready.",
        paragraphs=(
            "Hi {first_name},",
            "Thanks for creating your {brand_name} account. Please confirm that this is your "
            "email address so we can finish setting it up.",
        ),
        button=("Confirm email address", "link"),
        small_print=(
            "This link works once and expires in 24 hours.",
            "If you did not create an account, you can ignore this email.",
        ),
        fields=_fields("first_name", "link"),
    ),
    "reset_password": Template(
        subject="Reset your password",
        heading="Reset your password",
        preheader="Choose a new password within the hour.",
        paragraphs=(
            "Hi {first_name},",
            "We were asked to reset the password on your {brand_name} account. Use the button "
            "below to choose a new one.",
        ),
        button=("Choose a new password", "link"),
        small_print=(
            "This link works once and expires in 1 hour.",
            "If you did not ask for this, ignore this email. Your password has not changed.",
        ),
        fields=_fields("first_name", "link"),
    ),
    "password_changed": Template(
        subject="Your password was changed",
        heading="Your password was changed",
        preheader="If this was not you, act now.",
        paragraphs=(
            "Hi {first_name},",
            "The password on your {brand_name} account has just been changed, and you were "
            "signed out on your other devices.",
            "If you made this change, there is nothing more to do. If you did not, reset your "
            "password straight away at {web_origin}/forgot-password and contact {support_email}.",
        ),
        fields=_fields("first_name"),
    ),
    "account_exists": Template(
        subject="You already have an account",
        heading="You already have an account",
        preheader="Someone tried to sign up with your email address.",
        paragraphs=(
            "Hi {first_name},",
            "Someone tried to create a {brand_name} account with this email address, but you "
            "already have one. No new account was made.",
            "If it was you, sign in below. If you cannot remember your password, you can reset it.",
        ),
        button=("Sign in", "sign_in_link"),
        secondary=("Reset your password", "reset_link"),
        small_print=("If it was not you, you can ignore this email.",),
        fields=_fields("first_name", "sign_in_link", "reset_link"),
    ),
    "invite": Template(
        subject="You have been invited to {company_name}",
        heading="You have been invited",
        preheader="{inviter_name} invited you to join {company_name}.",
        paragraphs=(
            "Hi {first_name},",
            "{inviter_name} has invited you to join {company_name} on {brand_name} as "
            "{role_label}. Accept the invitation to choose your password and get started.",
        ),
        button=("Accept invitation", "link"),
        small_print=(
            "This invitation can be used once and expires in 72 hours.",
            "If you were not expecting it, you can ignore this email.",
        ),
        fields=_fields("first_name", "inviter_name", "company_name", "role_label", "link"),
    ),
    "login_alert": Template(
        subject="New sign-in to your account",
        heading="New sign-in to your account",
        preheader="We noticed a sign-in we want you to know about.",
        paragraphs=(
            "Hi {first_name},",
            "Your {brand_name} account was signed in to on {when} using {device}.",
            "If that was you, there is nothing to do. If it was not, change your password now "
            "so that nobody else can use it.",
        ),
        button=("Secure my account", "link"),
        fields=_fields("first_name", "when", "device", "link"),
    ),
    "account_locked": Template(
        subject="Sign-in paused on your account",
        heading="Sign-in paused on your account",
        preheader="Too many wrong passwords were tried.",
        paragraphs=(
            "Hi {first_name},",
            "Someone entered the wrong password for your {brand_name} account several times in a "
            "row, so we have paused sign-in for {minutes}. This protects your account.",
            "If it was you, wait and try again, or reset your password now. If it was not, "
            "reset your password so that nobody else can get in.",
        ),
        button=("Reset my password", "link"),
        fields=_fields("first_name", "minutes", "link"),
    ),
    "notifications_digest": Template(
        subject="You have new notifications",
        heading="You have new notifications",
        preheader="{count} waiting for you in {brand_name}.",
        paragraphs=(
            "Hi {first_name},",
            "You have {count} new in {brand_name}. Sign in to read them.",
        ),
        button=("Open my notifications", "link"),
        small_print=("You can change how often we email you in your notification settings.",),
        fields=_fields("first_name", "count", "link"),
    ),
    "reminder_nudge": Template(
        subject="You have a reminder waiting",
        heading="You have a reminder waiting",
        preheader="{sender_name} sent you a reminder.",
        paragraphs=(
            "Hi {first_name},",
            "{sender_name} has sent you a reminder in {brand_name}. Sign in to see what it is "
            "about and what to do next.",
        ),
        button=("Open my reminder", "link"),
        fields=_fields("first_name", "sender_name", "link"),
    ),
    "leave_decision": Template(
        subject="Your leave request was {decision}",
        heading="Your leave request was {decision}",
        preheader="Your request for {dates} was {decision}.",
        paragraphs=(
            "Hi {first_name},",
            "Your leave request for {dates} was {decision}.",
            "Sign in to see the details and your remaining allowance.",
        ),
        button=("View my leave", "link"),
        fields=_fields("first_name", "decision", "dates", "link"),
    ),
    "policy_request": Template(
        subject="Please read and acknowledge a policy",
        heading="A policy needs your acknowledgement",
        preheader="Please read {policy_title}.",
        paragraphs=(
            "Hi {first_name},",
            "You have been asked to read and acknowledge the policy “{policy_title}”. It only "
            "takes a few minutes, and your acknowledgement is recorded.",
        ),
        button=("Read the policy", "link"),
        fields=_fields("first_name", "policy_title", "link"),
    ),
    "application_received": Template(
        subject="We have your application for {job_title}",
        heading="Thank you for applying",
        preheader="Your application for {job_title} at {company_name}.",
        paragraphs=(
            "Hi {first_name},",
            "We have received your application for {job_title} at {company_name}. "
            "Our team will be in touch if it moves forward.",
        ),
        fields=_fields("first_name", "job_title", "company_name"),
    ),
    "interview_invite": Template(
        subject="Interview for {job_title}",
        heading="You are on an interview panel",
        preheader="Interview for {job_title} on {when}.",
        paragraphs=(
            "Hi {first_name},",
            "You are on the panel for an interview for {job_title}. It is on {when}, at {where}.",
            "The calendar invite is on the application page.",
        ),
        button=("Open the application", "link"),
        fields=_fields("first_name", "job_title", "when", "where", "link"),
    ),
    "interview_invite_candidate": Template(
        subject="Your interview for {job_title}",
        heading="Your interview is booked",
        preheader="Your interview for {job_title} is on {when}.",
        paragraphs=(
            "Hi {first_name},",
            "Thank you for applying for {job_title}. Your interview is on {when}, at {where}.",
            "We look forward to meeting you.",
        ),
        fields=_fields("first_name", "job_title", "when", "where"),
    ),
    "payment_failed": Template(
        subject="Your payment did not go through",
        heading="Your payment did not go through",
        preheader="Update your card by {grace_end} to keep full access.",
        paragraphs=(
            "Hi {first_name},",
            "We could not take the payment for your {brand_name} annual plan. Please update your "
            "card details by {grace_end}.",
            "After that date your account becomes read-only until the payment goes through. You "
            "can still see everything, and nothing is deleted.",
        ),
        button=("Update payment details", "link"),
        fields=_fields("first_name", "grace_end", "link"),
    ),
    "deletion_code": Template(
        subject="Your confirmation code",
        heading="Your confirmation code",
        preheader="Use this code to confirm the request.",
        paragraphs=(
            "Hi {first_name},",
            "Enter this code in {brand_name} to confirm that you want to go ahead with the "
            "request to delete your company data.",
        ),
        code_field="code",
        small_print=(
            "The code expires in {minutes} minutes and works once.",
            "If you did not ask for this, do not enter the code. Sign in and change your "
            "password, then contact {support_email}.",
        ),
        fields=_fields("first_name", "code", "minutes"),
    ),
}


@dataclass(frozen=True)
class Rendered:
    subject: str
    html: str
    plain: str


# HTML escaping is on for .html layouts (select_autoescape), and a missing value is an error.
# nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2
_environment = Environment(
    loader=FileSystemLoader(LAYOUTS),
    autoescape=select_autoescape(["html"]),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


def check(template: str, data: dict[str, str]) -> Template:
    """The template, if ``data`` is exactly what it takes. Raises ``TemplateError`` otherwise."""
    spec = TEMPLATES.get(template)
    if spec is None:
        raise TemplateError(f"There is no e-mail template called {template!r}.")
    given = set(data)
    if given != spec.fields:
        missing, extra = sorted(spec.fields - given), sorted(given - spec.fields)
        raise TemplateError(
            f"Template {template!r}: missing {missing or 'nothing'}, "
            f"not accepted {extra or 'nothing'}."
        )
    for name, value in data.items():
        if not isinstance(value, str) or not value or len(value) > MAX_VALUE_LENGTH:
            raise TemplateError(
                f"Template {template!r}: {name!r} must be 1-{MAX_VALUE_LENGTH} characters."
            )
        if "\n" in value or "\r" in value:
            raise TemplateError(f"Template {template!r}: {name!r} must be a single line.")
        if name.endswith("link") and not value.startswith(("https://", "http://")):
            raise TemplateError(f"Template {template!r}: {name!r} must be a web address.")
    return spec


def render(template: str, data: dict[str, str], settings: Settings) -> Rendered:
    spec = check(template, data)
    common = {
        "brand_name": settings.brand_name,
        "support_email": settings.support_email or f"support@{settings.domain}",
        "web_origin": settings.web_origin,
    }
    plain = {**common, **data}
    safe = {key: escape(value) for key, value in plain.items()}

    def say(line: str) -> str:
        return line.format(**plain)

    def say_html(line: str) -> Markup:
        # The line is this module's own wording, and every value in `safe` was escaped above.
        # nosemgrep: python.flask.security.xss.audit.explicit-unescape-with-markup.explicit-unescape-with-markup  # noqa: E501
        return Markup(line.format(**safe))  # noqa: S704

    def link_of(field: str | None) -> str | None:
        return data[field] if field else None

    context = {
        "brand_name": settings.brand_name,
        "accent": ACCENT,
        "year": datetime.now(UTC).year,
        "support_email": common["support_email"],
        "web_origin": settings.web_origin,
        "preheader": say(spec.preheader),
        "heading": say(spec.heading),
        "button_label": spec.button[0] if spec.button else None,
        "button_link": link_of(spec.button[1]) if spec.button else None,
        "secondary_label": spec.secondary[0] if spec.secondary else None,
        "secondary_link": link_of(spec.secondary[1]) if spec.secondary else None,
        "code": data[spec.code_field] if spec.code_field else None,
    }
    html = _environment.get_template("layout.html").render(
        **context,
        paragraphs=[say_html(p) for p in spec.paragraphs],
        small_print=[say_html(p) for p in spec.small_print],
    )
    body = _environment.get_template("layout.txt").render(
        **context,
        paragraphs=[say(p) for p in spec.paragraphs],
        small_print=[say(p) for p in spec.small_print],
    )
    return Rendered(subject=say(spec.subject), html=html, plain=body)
