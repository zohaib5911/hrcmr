from __future__ import annotations

from pathlib import Path

from app.db.data_model import data_model_markdown

DOC = Path(__file__).resolve().parents[3] / "docs" / "data-model.md"


def test_docs_data_model_is_what_the_models_produce() -> None:
    """Regenerate with: uv run python -m app.cli export-data-model --output ../docs/data-model.md"""
    assert DOC.read_text() == data_model_markdown()
