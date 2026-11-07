"""Imports every model module so ``Base.metadata`` is complete (Alembic autogenerate reads it).

Add one import line here when a module gets its first model.
"""

from __future__ import annotations

# ruff: noqa: F401 -- These imports register models for Alembic and are intentionally unused.
import app.ai.models
import app.modules.attendance.models
import app.modules.audit.models
import app.modules.companies.models
import app.modules.compliance.dossier_models
import app.modules.compliance.models
import app.modules.compliance.reminder_models
import app.modules.dashboard.models
import app.modules.documents.models
import app.modules.email.models
import app.modules.employees.models
import app.modules.files.models
import app.modules.holidays.models
import app.modules.identity.models
import app.modules.learning.models
import app.modules.leave.models
import app.modules.leave.request_models
import app.modules.leave.year_end_models
import app.modules.notifications.models
import app.modules.organogram.models
import app.modules.pay.models
import app.modules.policies.models
import app.modules.recruitment.models
import app.modules.reports.models
import app.modules.rota.models
import app.modules.rota.week_models
import app.modules.rtw.models
import app.modules.sponsor_documents.models
import app.modules.work_log.models
