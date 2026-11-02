"""Imports every model module so ``Base.metadata`` is complete (Alembic autogenerate reads it).

Add one import line here when a module gets its first model.
"""

from __future__ import annotations

import app.modules.audit.models
import app.modules.companies.models
import app.modules.email.models
import app.modules.employees.models
import app.modules.files.models
import app.modules.holidays.models
import app.modules.identity.models
import app.modules.notifications.models
import app.modules.pay.models
import app.modules.rtw.models
import app.modules.sponsor_documents.models  # noqa: F401
