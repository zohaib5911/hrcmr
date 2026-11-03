"""Enumerate effective routes, including FastAPI's deferred included routers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.routing import APIRoute, _iter_routes_with_context

if TYPE_CHECKING:
    from fastapi import FastAPI
    from fastapi.dependencies.models import Dependant


def registered_routes(app: FastAPI) -> list[tuple[str, set[str], Dependant]]:
    routes = []
    for original, context in _iter_routes_with_context(app.routes):
        if isinstance(original, APIRoute):
            effective = context or original
            assert effective.dependant is not None
            routes.append((effective.path, set(effective.methods or []), effective.dependant))
    return routes


def permissions(dependant: Dependant) -> list[str]:
    from app.modules.rbac.deps import PERMISSION_ATTRIBUTE

    found = []
    stack = list(dependant.dependencies)
    while stack:
        dep = stack.pop()
        permission = getattr(dep.call, PERMISSION_ATTRIBUTE, None)
        if permission:
            found.append(permission)
        stack.extend(dep.dependencies)
    return found
