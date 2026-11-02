"""The "What can each role do?" viewer (plan.md 8.15): the permission matrix in plain words.

Nothing here is written by hand per permission. Each name in ``rbac_matrix`` (``area.thing.action``,
the action optionally ``_own`` or ``_reports``) becomes a sentence from its own parts, grouped by
area, so the viewer cannot drift from what the API enforces.
"""

from __future__ import annotations

from app.core.rbac_matrix import ROLE_PERMISSIONS

AREAS: dict[str, str] = {
    "ai": "AI assistant",
    "attendance": "Attendance",
    "company": "Company settings",
    "compliance": "Sponsor compliance",
    "document": "Documents",
    "employee": "Employees",
    "holiday": "Holidays",
    "learning": "Learning",
    "leave": "Leave",
    "organogram": "Org chart",
    "policy": "Policies",
    "rbac": "User access",
    "recruitment": "Recruitment",
    "rota": "Rota",
    "settings": "Pay settings",
    "soc": "Sponsorship checker",
    "work_log": "Work log",
}

VERBS: dict[str, str] = {
    "read": "See",
    "write": "Add and change",
    "create": "Create",
    "approve": "Approve",
    "delete": "Delete",
    "export": "Export",
    "invite": "Invite",
    "assign": "Assign",
    "correct": "Correct",
    "convert": "Convert",
    "complete": "Complete",
    "generate": "Generate",
    "send": "Send",
    "run": "Run",
    "use": "Use",
    "draft": "Draft",
}

SCOPES: dict[str, str] = {"own": "their own", "reports": "their team's"}


def describe(permission: str) -> tuple[str, str, str]:
    """(area, sentence, scope) for one permission name. scope is "all", "own" or "reports"."""
    area, *middle, action = permission.split(".")
    verb, _, scope = action.partition("_")
    thing = " ".join(part.replace("_", " ") for part in middle)
    base = VERBS.get(verb, verb.capitalize())
    if scope in SCOPES:
        return area, f"{base} {SCOPES[scope]} {thing}", scope
    return area, f"{base} {thing}", "all"


def groups_for(role: str) -> list[dict[str, object]]:
    by_area: dict[str, list[dict[str, str]]] = {}
    for permission in sorted(ROLE_PERMISSIONS.get(role, frozenset())):
        area, sentence, scope = describe(permission)
        by_area.setdefault(area, []).append(
            {"permission": permission, "label": sentence, "scope": scope}
        )
    return [
        {"area": area, "label": AREAS.get(area, area.replace("_", " ").title()), "items": items}
        for area, items in sorted(by_area.items(), key=lambda pair: AREAS.get(pair[0], pair[0]))
    ]
