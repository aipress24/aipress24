# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import app.flask.components.table as t
from app.flask.routing import url_for
from app.models.auth import User
from app.ui.macros.images import profile_image

__all__ = ["BaseTable"]

USER_PROFILE_TPL = """
<a
    href="{href}"
    class=""
>
  <div class="flex-shrink-0">
    {image}
  </div>
</a>
"""

Column = t.Column


class BaseTable(t.Table):
    def render_media(self, item) -> str:
        media = item["media"]
        name = media.name
        href = url_for(media)
        cls = "underline"
        return f"<a href='{href}' class='{cls}'>{name} </a>"

    def render_destinataire(self, item):
        member = item["destinataire"]
        return self._render_member(member)

    def render_auteur(self, item):
        member = item["auteur"]
        return self._render_member(member)

    def _render_member(self, member: User) -> str:
        href = url_for(member)
        image = profile_image(member, size=8)
        return USER_PROFILE_TPL.format(member=member, href=href, image=image)

    def ag_grid_data(self):
        return {
            "columnDefs": self.ag_column_defs(),
            "rowData": self.ag_row_data(),
        }

    def ag_column_defs(self):
        return [
            {
                "headerName": col.label,
                "field": col.name,
                "sortable": True,
                "filter": True,
                "resizable": True,
                # "flex": 1,
            }
            for col in self.columns
        ]

    def ag_row_data(self):
        return [
            {col.name: str(item[col.name]) for col in self.columns}
            for item in self.items
        ]
