# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Organizations table helpers for admin views."""

from __future__ import annotations

from flask import url_for as url_for_orig
from sqlalchemy import Select, select

from app.flask.extensions import db
from app.flask.routing import url_for
from app.models.organisation import Organisation
from app.modules.admin.table import Column, ColumnSpec, GenericOrgDataSource, Table
from app.modules.bw.bw_activation.models.business_wall import BusinessWall, BWStatus
from app.ui.labels import LABELS_BW_TYPE_V2, LABELS_ORGANISATION_TYPE

TABLE_COLUMNS: list[ColumnSpec] = [
    {"name": "name", "label": "Nom", "width": 50},
    {"name": "type", "label": "Type", "width": 20},
    {"name": "karma", "label": "Réputation", "width": 8},
]


class OrgsTable(Table):
    url_label = "Détail"
    all_search = False

    def compose(self):
        for col in TABLE_COLUMNS:
            yield Column(**col)


class OrgDataSource(GenericOrgDataSource):
    """Data source to sort organisations by active BW status."""

    def records(self):
        stmt = self.get_base_select()
        stmt = self.add_search_filter(stmt)
        # use execute() to get all columns
        result = db.session.execute(stmt)
        objects = list(result.all())
        return self.make_records(objects)

    def get_base_select(self) -> Select:
        """Override to sort by active BW first."""
        # Subquery to check for active BW
        active_bw_subq = (
            select(BusinessWall.organisation_id, BusinessWall.bw_type)
            .where(BusinessWall.status == BWStatus.ACTIVE.value)
            .distinct(BusinessWall.organisation_id)
            .subquery()
        )

        # Build query with left join to active BW
        stmt = (
            select(
                Organisation,
                active_bw_subq.c.bw_type.label("active_bw_type"),
            )
            .outerjoin(
                active_bw_subq,
                Organisation.id == active_bw_subq.c.organisation_id,
            )
            .where(Organisation.deleted_at.is_(None))
            .order_by(
                active_bw_subq.c.bw_type.is_(None).asc(),  # (NULLs last)
                Organisation.name,
            )
            .offset(self.offset)
            .limit(self.limit)
        )
        return stmt

    def make_records(self, objects) -> list[dict]:
        """Override to include BW type."""
        result = []
        for row in objects:
            obj = row[0]  # Organisation
            active_bw_type = row[1]  # BW type string or None

            # Determine type display: BW type if active, otherwise org type
            if active_bw_type:
                type_display = LABELS_BW_TYPE_V2.get(active_bw_type, active_bw_type)
            else:
                type_display = "Non officialisée"

            record = {
                "$url": url_for(obj),
                "id": obj.id,
                "show": url_for_orig(".show_org", uid=obj.id),
                "name": obj.name,
                "karma": obj.karma,
                "type": type_display,
            }
            result.append(record)
        return result
