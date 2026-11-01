"""Database role names (plan.md 4.3). One place, so nothing hard-codes them elsewhere.

* ``app_owner`` owns every table and runs migrations. It is never used by the running API.
* ``app_user``  is the runtime role. It owns nothing, is not a superuser, and does NOT have
  BYPASSRLS, so Row-Level Security always applies to it.
"""

from __future__ import annotations

OWNER_ROLE = "app_owner"
APP_ROLE = "app_user"

# Extensions the schema relies on (plan.md T0.5). `vector` is not "trusted" in PostgreSQL, so a
# non-superuser cannot create it; provisioning creates all five as a superuser.
EXTENSIONS = ("pgcrypto", "pg_trgm", "unaccent", "vector", "citext")
