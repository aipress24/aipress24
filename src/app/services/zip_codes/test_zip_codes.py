# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from unittest import skip

from flask_sqlalchemy import SQLAlchemy

from . import create_zip_code_entry, get_zip_code_country


@skip
def test_zip_code(db: SQLAlchemy) -> None:
    create_zip_code_entry("FRA", "75018", "Paris", "", "")
    db.session.flush()

    zip_code_list = get_zip_code_country("FRA")
    assert zip_code_list == [("75018", "Paris", "", "")]
