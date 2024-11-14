# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from attr import define
from flask import g, url_for
from sqlalchemy import select

from app.flask.extensions import db
from app.models.auth import User
from app.models.content import BaseContent
from app.models.meta import get_label
from app.modules.wip.components import DataSource, Table

# # language=jinja2
# ROW_TEMPLATE_1 = """
# <tr class="bg-white">
#   {% set actions = row.get_actions() %}
#   {% if actions %}
#   <td class="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
#     {% for action in actions %}
#       <a class="underline text-blue-700" href="{{ action.url}}">{{ action.label }}</a>
#     {% endfor %}
#   </td>
#   {% endif %}
#
#   <td class="max-w-0 w-full px-4 py-4 whitespace-nowrap text-sm text-gray-900">
#     <div class="flex">
#       <a href="{{ url_for(item) }}" class="group inline-flex space-x-2 truncate text-sm">
#         <p class="text-gray-500 truncate group-hover:text-gray-900">
#           {{ item.title }}
#         </p>
#       </a>
#     </div>
#   </td>
#
#   <td class="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
#     {{ item.type }}
#   </td>
#
#   <td class="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
#     <span
#         class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 capitalize">
#       Publié
#     </span>
#   </td>
#
#   <td class="px-4 py-4 text-right whitespace-nowrap text-sm text-gray-500">
#     <time datetime="2020-07-11">{{ item.created_at.format("YYYY-MM-DD à HH:mm") }}</time>
#   </td>
# </tr>
# """


class RecentContentsDataSource(DataSource):
    def query(self):
        user: User = g.user

        return (
            select(BaseContent)
            .where(BaseContent.owner == user)
            .order_by(BaseContent.created_at.desc())
        )

    def get_items(self):
        query = self.query().limit(10)
        return list(db.session.scalars(query))

    def get_count(self):
        # FIXME:
        return len(list(db.session.scalars(self.query())))


def get_name(obj):
    # FIXME: temp hack
    try:
        return obj.name if obj else ""
    except:  # noqa: E722
        return ""


@define
class RecentContentsTable(Table):
    id = "recent-contents-table"
    # row_template = ROW_TEMPLATE_1
    columns = [
        {"name": "title", "label": "Titre", "class": "max-w-0 w-full truncate"},
        {"name": "type", "label": "Type", "render": get_label},
        {"name": "publisher", "label": "Média", "render": get_name},
        {"name": "status", "label": "Statut"},
        {"name": "created_at", "label": "Création"},
    ]
    data_source = RecentContentsDataSource()

    def url_for(self, obj, **kwargs):
        return url_for("wip.contents", id=obj.id, mode="update", **kwargs)
