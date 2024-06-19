# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

# from __future__ import annotations
#
# from dataclasses import dataclass, field
#
# from flask import request
# from sqlalchemy import func, select
# from sqlalchemy.orm import selectinload
#
# from app.flask.extensions import db
# from app.flask.lib.pages import Page, page
# from app.flask.routing import url_for
# from app.flask.sqla import get_multi
# from app.lib.fts import tokenize
# from app.models.auth import User
# from app.models.common import STATUS
# from app.models.content.communication import PressRelease
# from app.models.content.events import Event
# from app.models.content.mixins import Searchable
# from app.models.content.multimedia import Image
# from app.models.content.textual import Article
# from app.models.orgs import Organisation
# from app.models.social import Group
#
# from .. import blueprint
#
#
#
# MENU = [
#     {
#         "name": "all",
#         "label": "Tout",
#         "icon": "collection",
#         "class": None,
#     },
#     {
#         "name": "articles",
#         "label": "Articles",
#         "icon": "newspaper",
#         "class": Article,
#     },
#     {
#         "name": "images",
#         "label": "Images",
#         "icon": "photograph",
#         "class": Image,
#     },
#     {
#         "name": "videos",
#         "label": "Vidéos",
#         "icon": "film",
#         # TODO: video
#         "class": Image,
#     },
#     {
#         "name": "press-releases",
#         "label": "Communiqués",
#         "icon": "volume-up",
#         "class": PressRelease,
#     },
#     {
#         "name": "events",
#         "label": "Evénements",
#         "icon": "calendar",
#         "class": Event,
#     },
#     {
#         "name": "members",
#         "label": "Membres",
#         "icon": "user",
#         "class": User,
#     },
#     {
#         "name": "orgs",
#         "label": "Entreprises",
#         "icon": "building-office",
#         "class": Organisation,
#     },
#     {
#         "name": "groups",
#         "label": "Groupes",
#         "icon": "user-group",
#         "class": Group,
#     },
# ]
#
#
# @page
# class SearchOldPage(Page):
#     name = "search"
#     label = "Rechercher"
#     layout = "layout/private.j2"
#     path = "/old"
#     template = "pages/search.j2"
#
#     def context(self):
#         qs = request.args.get("qs", "")
#         filter = request.args.get("filter", "all")
#
#         results = SearchResults(qs, filter)
#
#         match filter:
#             case "all":
#                 result_sets = [r for r in results.result_sets if r.count > 0]
#             case _:
#                 result_sets = [r for r in results.result_sets if r.name == filter]
#
#         return {
#             "qs": qs,
#             "search_menu": self.make_menu(filter, qs, results),
#             "result_sets": result_sets,
#         }
#
#     def make_menu(self, filter, qs, results):
#         menu = []
#         for m in MENU:
#             name = m["name"]
#             label = m["label"]
#             icon = m["icon"]
#
#             if name == "all":
#                 count = sum(r.count for r in results.result_sets)
#             else:
#                 count = sum(r.count for r in results.result_sets if r.name == name)
#
#             d = {
#                 "name": name,
#                 "label": label,
#                 "icon": icon,
#                 "href": url_for(".search", qs=qs, filter=name),
#                 "current": filter == name,
#                 "count": count,
#             }
#             menu.append(d)
#
#         return menu
#
#
# @dataclass
# class SearchResults:
#     qs: str
#     filter: str
#     results: list = field(default_factory=list)
#     result_sets: list[ResultSet] = field(default_factory=list)
#
#     def __post_init__(self):
#         for menu_entry in MENU:
#             cls = menu_entry["class"]
#             if not cls:
#                 continue
#             assert isinstance(cls, type)
#
#             name = menu_entry["name"]
#             icon = menu_entry["icon"]
#             label = menu_entry["label"]
#             result_set = ResultSet(cls, self.qs, name=name, label=label, icon=icon)
#
#             self.result_sets.append(result_set)
#
#
# @dataclass
# class ResultSet:
#     cls: type
#     qs: str
#
#     name: str
#     label: str
#     icon: str
#
#     count: int = 0
#     hits: list = field(default_factory=list)
#
#     def __post_init__(self):
#         if hasattr(self.cls, "_fts"):
#             self.execute_query()
#
#     def execute_query(self):
#         stmt = self.make_stmt()
#         self.update_count(stmt)
#         self.update_hits(stmt)
#
#     def update_count(self, stmt):
#         count_stmt = stmt.with_only_columns([func.count(self.cls.id)])
#         result = db.session.execute(count_stmt)
#         self.count = result.scalar()
#
#     def update_hits(self, stmt):
#         if hasattr(self.cls, "published_at"):
#             stmt = stmt.order_by(self.cls.published_at.desc())
#         stmt = stmt.limit(20)
#         self.hits = [Hit(model) for model in get_multi(self.cls, stmt)]
#
#     def make_stmt(self):
#         cls = self.cls
#
#         stmt = select(cls).where(cls.status == STATUS.PUBLIC)
#
#         if hasattr(cls, "owner"):
#             stmt = stmt.options(selectinload(cls.owner))
#
#         words = tokenize(self.qs)
#         tsquery = " & ".join(words)
#         stmt = stmt.where(func.to_tsvector(cls._fts).match(tsquery))
#
#         return stmt
#
#     # def get_matching_members(self, qs):
#     #     stmt = (
#     #         select(User)
#     #         .where(
#     #             or_(
#     #                 User.first_name.like(f"%{qs}% "),
#     #                 User.last_name.like(f"%{qs}% "),
#     #                 # User.organisation.like(f"%{qs}%"),
#     #             )
#     #         )
#     #         .limit(20)
#     #     )
#     #     return get_multi(User, stmt)
#
#
# @dataclass
# class Hit:
#     model: Searchable
#
#     @property
#     def title(self):
#         return self.model.title
#
#     @property
#     def summary(self):
#         return self.model.summary
#
#     @property
#     def date(self):
#         published_at = getattr(self.model, "published_at", None)
#         if published_at:
#             return published_at
#         else:
#             return self.model.created_at
#
#     @property
#     def url(self):
#         return url_for(self.model)
