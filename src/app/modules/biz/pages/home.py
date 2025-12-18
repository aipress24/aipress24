# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sqlalchemy as sa
from flask import request

from app.flask.components.filterset import FilterSet
from app.flask.lib.pages import Page
from app.flask.routing import url_for
from app.flask.sqla import get_multi
from app.models.lifecycle import PublicationStatus
from app.modules.biz.models import MarketplaceContent

TABS = [
    {
        "id": "stories",
        "label": "©",  # ex: "Stories"
        "tip": "",
    },
    {
        "id": "subscriptions",
        "label": "Abonnements",
        "tip": "",
    },
    {
        "id": "missions",
        "label": "Missions",
        "tip": "",
    },
    {
        "id": "projects",
        "label": "Projets",
        "tip": "",
    },
    {
        "id": "jobs",
        "label": "Job Board",
        "tip": "",
    },
]

FILTER_SPECS = [
    {
        "id": "sector",
        "label": "Secteur",
        "selector": "sector",
    },
    {
        "id": "topic",
        "label": "Thématique",
        "selector": "topic",
    },
    {
        "id": "genre",
        "label": "Genre",
        "selector": "genre",
    },
    {
        "id": "location",
        "label": "Localisation",
        "options": ["France", "Europe", "USA", "Chine", "..."],
    },
    {
        "id": "language",
        "label": "Langue",
        "selector": "language",
    },
]


# Disabled: migrated to views/home.py
# @page
class BizHomePage(Page):
    name = "biz"
    label = "Marketplace"
    template = "pages/biz-home.j2"

    path = "/"

    # Not needed (yet?)
    # components = [BizList]

    def context(self):
        objs = self.get_objs()
        # tabs = self.get_tabs()

        # sorter = Sorter(SORTER_OPTIONS)
        # if self.sort_order in (None, "", "date"):
        #     show_sorter = "false"
        # else:
        #     show_sorter = "true"
        #
        # if request.headers.get("Hx-Request"):
        #     return render_template("pages/wire.j2", posts=posts, tabs=tabs)
        #
        # filters = self.get_filters()

        return {
            "objs": objs,
            "tabs": self.get_tabs(),
            "filters": self.get_filters(),
            # "tab": self.current_tab,
            # "tag": self.tag,
            # "sorter": sorter,
            # "show_sorter": show_sorter,
            # "applied_filters": self.applied_filters,
        }

    def get_objs(self):
        current_tab = request.args.get("current_tab", "stories")
        match current_tab:
            case "stories":
                stmt = (
                    sa.select(MarketplaceContent)
                    .where(MarketplaceContent.status == PublicationStatus.PUBLIC)
                    # .order_by(order)
                    # .options(selectinload(Article.owner))
                    .limit(30)
                )
                return get_multi(MarketplaceContent, stmt)
            case _:
                return []

    def get_filters(self):
        stmt = sa.select(MarketplaceContent).where(
            MarketplaceContent.status == PublicationStatus.PUBLIC
        )
        articles = get_multi(MarketplaceContent, stmt)

        filter_set = FilterSet(FILTER_SPECS)
        filter_set.init(articles)

        return filter_set.get_filters()

    def get_tabs(self):
        current_tab = request.args.get("current_tab", "stories")
        tabs = []
        for tab in TABS:
            tab_id = tab["id"]
            tabs.append(
                {
                    "id": tab_id,
                    "label": tab["label"],
                    "href": url_for(".biz", current_tab=tab_id),
                    "current": tab_id == current_tab,
                }
            )
        return tabs


# @page
# class BizHomePage(Page):
#     name = "biz"
#     label = "Biz"
#     layout = "layout/private.j2"
#     template = "pages/sandbox.j2"
# template = "pages/biz.j2"

# def __init__(self, current_tab: str = ""):
#     self.current_tab = current_tab
#     if current_tab:
#         session["wire.tab"] = current_tab
#
#     if "sort-order" in request.args:
#         session["wire:sort-order"] = request.args["sort-order"]
#
#     self.tag = request.args.get("tag")
#
#     if "toggle-filter" in request.args:
#         filter = request.args["toggle-filter"]
#         name, value = filter.split(":", 2)
#         if name == "sort":
#             session["wire:sort-order"] = value
#         else:
#             filters_json = session.get("wire:filters", "[]")
#             filters = json.loads(filters_json)
#             filters.append(filter)
#             session["wire:filters"] = json.dumps(filters)
#
#     self.sort_order = session.get("wire:sort-order")
#
#     filters_json = session.get("wire:filters", "[]")
#     filters = list(set(json.loads(filters_json)))
#     self.applied_filters = filters
#
# def get(self):
#     if not self.current_tab:
#         tab = session.get("wire.tab", "wires")
#         kw = {"current_tab": tab}
#         if self.tag:
#             kw["tag"] = self.tag
#         return redirect(url_for(".wire", **kw))
#     return super().get()
#
# def context(self):
#     posts = self.get_posts()
#     tabs = self.get_tabs()
#
#     sorter = Sorter(SORTER_OPTIONS)
#     if self.sort_order in (None, "", "date"):
#         show_sorter = "false"
#     else:
#         show_sorter = "true"
#
#     if request.headers.get("Hx-Request"):
#         return render_template("pages/wire.j2", posts=posts, tabs=tabs)
#
#     filters = self.get_filters()
#     return {
#         "posts": posts,
#         "tab": self.current_tab,
#         "tabs": tabs,
#         "tag": self.tag,
#         "filters": filters,
#         "sorter": sorter,
#         "show_sorter": show_sorter,
#         "applied_filters": self.applied_filters,
#     }
#
# def get_posts(self):
#     match self.current_tab:
#         case "wires":
#             return self.get_wires_posts()
#         case "com":
#             return self.get_com_posts()
#         case "journalists":
#             return self.get_journalists_posts()
#         case _:
#             return []
#
# def get_wires_posts(self):
#     match self.sort_order:
#         case "likes":
#             order = Article.like_count.desc()
#         case "comments":
#             order = Article.comment_count.desc()
#         case _:
#             order = Article.published_at.desc()
#
#     if self.tag:
#         stmt = (
#             sa.select(Article)
#             .where(Article.status == "public")
#             .order_by(order)
#             .options(selectinload(Article.owner))
#         )
#         articles = get_multi(Article, stmt)
#         articles_filtered = []
#         for article in articles:
#             tags = [t["label"] for t in get_tags(article)]
#             if self.tag in tags:
#                 articles_filtered.append(article)
#
#         return PostVM.from_many(articles_filtered)
#
#     stmt = (
#         sa.select(Article)
#         .where(Article.status == "public")
#         .order_by(order)
#         .options(selectinload(Article.owner))
#         .limit(30)
#     )
#     articles = get_multi(Article, stmt)
#     return PostVM.from_many(articles)
#
# def get_journalists_posts(self):
#     match self.sort_order:
#         case "likes":
#             order = Article.like_count.desc()
#         case "comments":
#             order = Article.comment_count.desc()
#         case _:
#             order = Article.published_at.desc()
#
#     followees = get_followees(g.user)
#     followee_ids = [f.id for f in followees]
#
#     if self.tag:
#         stmt = (
#             sa.select(Article)
#             .where(Article.status == "public")
#             .where(Article.owner_id.in_(followee_ids))
#             .order_by(order)
#             .options(selectinload(Article.owner))
#         )
#         articles = get_multi(Article, stmt)
#         articles_filtered = []
#         for article in articles:
#             tags = [t["label"] for t in get_tags(article)]
#             if self.tag in tags:
#                 articles_filtered.append(article)
#
#         posts = PostVM.from_many(articles_filtered)
#         return posts
#
#     stmt = (
#         sa.select(Article)
#         .where(Article.status == "public")
#         .where(Article.owner_id.in_(followee_ids))
#         .order_by(order)
#         .options(selectinload(Article.owner))
#         .limit(30)
#     )
#     articles = get_multi(Article, stmt)
#     posts = PostVM.from_many(articles)
#     return posts
#
# def get_com_posts(self):
#     match self.sort_order:
#         case "likes":
#             order = PressRelease.like_count.desc()
#         case "comments":
#             order = PressRelease.comment_count.desc()
#         case _:
#             # TODO
#             order = PressRelease.created_at.desc()
#
#     stmt = (
#         sa.select(PressRelease)
#         .where(PressRelease.status == "public")
#         .order_by(order)
#         .options(selectinload(PressRelease.owner))
#         .limit(30)
#     )
#     press_releases = get_multi(PressRelease, stmt)
#     posts = PostVM.from_many(press_releases)
#     return posts
#
# def get_tabs(self):
#     tabs = []
#     for tab in TABS:
#         tab_id = tab["id"]
#         tabs.append(
#             {
#                 "id": tab_id,
#                 "label": tab["label"],
#                 "href": url_for(".wire", current_tab=tab_id),
#                 "current": tab_id == self.current_tab,
#             }
#         )
#     return tabs
#
# def get_filters(self):
#     stmt = sa.select(Article).where(Article.status == "public")
#     articles = get_multi(Article, stmt)
#
#     filter_set = FilterSet(FILTER_SPECS)
#     filter_set.init(articles)
#
#     return filter_set.get_filters()
