# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""New users table helpers for admin views."""

from __future__ import annotations

from flask import url_for as url_for_orig
from sqlalchemy import Select, desc, false, func, nulls_last, select

from app.flask.extensions import db
from app.flask.routing import url_for
from app.models.auth import User
from app.modules.admin.table import Column, GenericUserDataSource, Table

TABLE_COLUMNS = [
    {"name": "name", "label": "Nom", "width": 50},
    {"name": "organisation_name", "label": "Org.", "width": 50},
    {"name": "submited_at", "label": "Inscription", "width": 35},
    {"name": "job_title", "label": "Job", "width": 50},
    {"name": "email", "label": "E-mail", "width": 50},
]


class NewUsersTable(Table):
    url_label = "Validation"
    all_search = False

    def compose(self):
        for col in TABLE_COLUMNS:
            yield Column(**col)


class NewUserDataSource(GenericUserDataSource):
    def count(self) -> int:
        stmt = select(func.count()).select_from(User)
        stmt = stmt.filter(
            User.active == false(),
            User.is_clone == false(),
            User.deleted_at.is_(None),
        )
        stmt = self.add_search_filter(stmt)
        return db.session.scalar(stmt) or 0

    def get_base_select(self) -> Select:
        return (
            select(User)
            .where(
                User.active == false(),
                User.is_clone == false(),
                User.deleted_at.is_(None),
            )
            .order_by(nulls_last(desc(User.submited_at)))
            .offset(self.offset)
            .limit(self.limit)
        )

    def make_records(self, objects) -> list[dict]:
        result = []
        for obj in objects:
            record = {
                "$url": url_for(obj),
                "id": obj.id,
                "show": url_for_orig(".validation_profile", uid=obj.id),
                "name": obj.full_name,
                "email": obj.email_safe_copy or obj.email,
                "job_title": obj.job_title,
                "organisation_name": obj.organisation_name,
                "submited_at": obj.submited_at.strftime("%d %b %G %H:%M"),
            }
            result.append(record)
        return result
