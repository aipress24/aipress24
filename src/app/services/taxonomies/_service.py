# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from sqlalchemy import select

from app.flask.extensions import db

from ._models import TaxonomyEntry


def get_taxonomy(name) -> list[str]:
    """Get a taxonomy from the database."""
    T = TaxonomyEntry  # noqa: N806
    query = select(T).where(T.taxonomy_name == name).order_by(T.name)
    result = db.session.execute(query).scalars()
    return [r.name for r in result]
    # return [(r.id, r.name) for r in result]


def create_entry(
    taxonomy_name: str,
    name: str,
    category: str = "",
    value: str = "",
    seq: int = 0,
) -> None:
    """Create a new entry in a taxonomy."""
    entry = TaxonomyEntry(
        taxonomy_name=taxonomy_name,
        name=name,
        category=category,
        value=value,
        seq=seq,
    )
    db.session.add(entry)
