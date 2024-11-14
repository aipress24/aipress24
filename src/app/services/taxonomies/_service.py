# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sys
from typing import Any

from sqlalchemy import select

from app.flask.extensions import db

from ._models import TaxonomyEntry


def check_taxonomy_exist(taxonomy_name: str) -> bool:
    """Return the existence of the taxonomy in DB"""
    return (
        db.session.query(TaxonomyEntry.id)
        .filter(TaxonomyEntry.taxonomy_name == taxonomy_name)
        .first()
        is not None
    )


def get_taxonomy(name) -> list[str]:
    """Get a taxonomy from the database."""
    # TODO: ne retourner que les valeurs qui correspondent à un utilisateur existant
    T = TaxonomyEntry  # noqa: N806
    query = select(T).where(T.taxonomy_name == name).order_by(T.name)
    result = db.session.execute(query).scalars()
    return [r.name for r in result]


def get_full_taxonomy(name: str, category: str = "") -> list[tuple[str, str]]:
    """Get a taxonomy from the database."""
    T = TaxonomyEntry  # noqa: N806
    query = select(T)
    if category:
        query = query.where(T.taxonomy_name == name, T.category == category)
    else:
        query = query.where(T.taxonomy_name == name)
    query = query.order_by(T.seq)
    results = db.session.scalars(query).all()
    return [(row.value, row.name) for row in results]


def get_full_taxonomy_category_value(name: str) -> list[tuple[str, str]]:
    """Get a taxonomy from the database, with categories."""
    T = TaxonomyEntry  # noqa: N806
    query = select(T).where(T.taxonomy_name == name).order_by(T.seq)
    results = db.session.scalars(query).all()
    return [(row.category, row.value) for row in results]


def get_taxonomy_dual_select(
    name: str,
) -> dict[str, Any]:
    """Get a taxonomy in dual select format"""
    T = TaxonomyEntry  # noqa: N806
    query = select(T).where(T.taxonomy_name == name).order_by(T.seq)
    results = db.session.scalars(query).all()
    seen = set()
    distinct = []
    field2 = {}
    for item in results:
        if item.category not in seen:
            seen.add(item.category)
            distinct.append(item.category)
            field2[item.category] = []
        field2[item.category].append([item.value, item.name])
    response = {}
    response["field1"] = [(category, category) for category in distinct]
    response["field2"] = field2
    return response


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


def update_entry(
    taxonomy_name: str,
    name: str,
    category: str = "",
    value: str = "",
    seq: int = 0,
) -> bool:
    """Update an entry if necessary.
    - assuming existing and new values are valid (no duplicates in either list)
    - id is used for faster queries, and should not be stored between updates
    - seq number is only used for sorting
    """
    query = select(TaxonomyEntry).filter(
        TaxonomyEntry.taxonomy_name == taxonomy_name, TaxonomyEntry.value == value
    )
    # print(f"/////////////////// {taxonomy_name} {value}", file=sys.stderr)
    result = db.session.execute(query).scalar()
    if not result:
        create_entry(taxonomy_name, name, category, value, seq)
        return True
    if result.name == name and result.category == category and result.seq == seq:
        # unchanged item
        # print("/////////////////// no change", file=sys.stderr)
        return False
    # update required

    print(
        f"    update: {result.name}, {result.category}, {result.seq} ->  {name}, {category}, {seq}",
        file=sys.stderr,
    )

    result.name = name
    result.category = category
    result.seq = seq

    return True
