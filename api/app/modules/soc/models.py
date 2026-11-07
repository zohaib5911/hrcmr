"""SOC 2020 reference data (plan 6.10, T15.1): the unit groups and the coding index.

Global, like ``courses``: the tables have no company column, so every tenant may read them, and only
the owner role writes them (the importer in ``data/import_soc.py``). Each row keeps a local
embedding (fastembed, 384 dimensions) for vector retrieval in T15.4.
"""

from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin

EMBEDDING_DIMENSIONS = 384


class SocUnitGroup(Base, RecordMixin):
    __tablename__ = "soc_unit_groups"
    __table_args__ = (
        CheckConstraint("code ~ '^[1-9][0-9]{3}$'", name="code"),
        CheckConstraint("rqf_level in ('6', '3-5', 'below')", name="rqf_level"),
    )

    code: Mapped[str] = mapped_column(String(4), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    tasks: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    entry_requirements: Mapped[str] = mapped_column(Text, nullable=False)
    typical_titles: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    # Set by the rules-data importer (T15.2) from the Skilled Occupations appendix; null until then.
    rqf_level: Mapped[str | None] = mapped_column(String(10))
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)


class SocIndexEntry(Base, RecordMixin):
    __tablename__ = "soc_index_entries"
    __table_args__ = (
        UniqueConstraint(
            "index_title",
            "qualifier_add",
            "qualifier_ind",
            "soc_code",
            name="uq_soc_index_entries_one_entry",
        ),
        Index(
            "ix_soc_index_entries_index_title_trgm",
            "index_title",
            postgresql_using="gin",
            postgresql_ops={"index_title": "gin_trgm_ops"},
        ),
    )

    index_title: Mapped[str] = mapped_column(Text, nullable=False)
    # The ONS "ADD" and "IND" qualifiers. Empty text, not null, so the unique key works.
    qualifier_add: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    qualifier_ind: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    soc_code: Mapped[str] = mapped_column(
        String(4),
        ForeignKey("soc_unit_groups.code", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
