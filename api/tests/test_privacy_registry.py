"""Worker processes do not import the API routers before exporting or deleting data."""

from __future__ import annotations

import subprocess
import sys


def test_fresh_worker_registers_all_models_before_any_privacy_job() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
from app.jobs.worker import WorkerSettings
from app.db.base import Base
before = set(Base.metadata.tables)
import app.db.registry
assert before == set(Base.metadata.tables), set(Base.metadata.tables) - before
assert {'rtw_checks', 'sponsor_documents', 'employee_documents', 'data_exports',
        'sessions', 'ai_interactions', 'candidates', 'audit_events'} <= before
""",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
