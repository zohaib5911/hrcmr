"""Imports every model module so ``Base.metadata`` is complete (Alembic autogenerate reads it).

Add one import line here when a module gets its first model.
"""

from __future__ import annotations

import app.modules.audit.models
import app.modules.companies.models
import app.modules.email.models
import app.modules.files.models
import app.modules.identity.models
import app.modules.notifications.models  # noqa: F401
