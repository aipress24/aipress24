# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.extensions import db


def create_tables(app):
    with app.app_context():
        db.create_all()
