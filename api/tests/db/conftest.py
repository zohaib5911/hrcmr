from __future__ import annotations

from collections.abc import Iterator

import pytest

from tests.db.support import DatabaseUnderTest, temporary_database


@pytest.fixture(scope="session")
def database(stack: None) -> Iterator[DatabaseUnderTest]:
    """One provisioned, fully migrated database shared by the read-mostly tests."""
    with temporary_database() as db:
        yield db
