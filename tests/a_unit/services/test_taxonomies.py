# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy

from app.services.taxonomies import create_entry, get_all_taxonomy_names, get_taxonomy


def test_taxonomy(db: SQLAlchemy) -> None:
    create_entry("test_taxonomy", "test_entry")
    db.session.flush()

    assert len(get_all_taxonomy_names()) == 1

    taxonomy = get_taxonomy("test_taxonomy")
    assert taxonomy[0] == "test_entry"
