"""The base of every request body: a field we do not know is refused, never silently dropped.

Without this, a form that sends ``is_admin: true`` or a misspelt field would succeed as if the
extra part had not been there. A test walks the OpenAPI document and fails for any request body
that does not inherit from this class.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
