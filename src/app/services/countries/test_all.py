# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy

from . import create_country_entry, get_country


def test_country(db: SQLAlchemy) -> None:
    create_country_entry("FRA", "France")
    db.session.flush()

    country = get_country("FRA")
    assert country == "France"
