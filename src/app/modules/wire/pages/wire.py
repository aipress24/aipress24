# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from flask import redirect, render_template, request, session
from werkzeug.exceptions import NotFound

from app.flask.lib.pages import Page
from app.flask.routing import url_for
from app.services.tagging import get_tags

from ._filters import FilterBar
from ._tabs import get_tabs

if TYPE_CHECKING:
    from app.modules.wire.models import Post

NS = "wire"
ONE_DAY = 60 * 60 * 24
TOP_NEWS_SIZE = 5


# Disabled: migrated to views/wire.py
# @page
class WirePage(Page):
    name = "wire"
    routes: ClassVar = [
        "/",
        "/tab/<tab>",
    ]
    label = "News"
    template = "pages/wire.j2"

    def __init__(self, tab: str = "") -> None:
        self.tab = tab
        self.tabs = get_tabs()

        if not tab:
            return

        if tab not in {tab.id for tab in self.tabs}:
            raise NotFound

        session["wire:tab"] = tab

        self.filter_bar = FilterBar(self.tab)

    def get(self):
        if not self.tab:
            tab = session.get("wire:tab", self.tabs[0].id)
            return redirect(url_for(".wire", tab=tab))

        if "tag" in request.args:
            tag = request.args["tag"]
            self.filter_bar.reset()
            self.filter_bar.set_tag(tag)
            return redirect(url_for(".wire", tab="wall"))

        return super().get()

    def post(self):
        self.filter_bar.update_state()
        ctx = self.context()
        return render_template("pages/wire/main.j2", **ctx)

    def context(self):
        posts = self.get_posts()

        return {
            "page": self,
            "posts": posts,
            "tabs": self.get_tabs(),
            "tab": self.tab,
            "filter_bar": self.filter_bar,
        }

    def get_tabs(self):
        tabs = []
        for tab in get_tabs():
            tab_id = tab.id
            tabs.append(
                {
                    "id": tab_id,
                    "label": tab.label,
                    "href": url_for(".wire", tab=tab_id),
                    "current": tab.is_active,
                }
            )
        return tabs

    def get_posts(self) -> list[Post]:
        for tab in self.tabs:
            if tab.is_active:
                active_tab = tab
                break
        else:
            raise RuntimeError

        posts = active_tab.get_posts(self.filter_bar)
        return self._filter_posts_by_tag(posts)

    def _filter_posts_by_tag(self, posts: list[Post]) -> list[Post]:
        if not (tag := self.filter_bar.tag):
            return posts
        filtered_posts = []
        for post in posts:
            tags = [t["label"] for t in get_tags(post)]
            if tag in tags:
                filtered_posts.append(post)

        return filtered_posts

    def top_news(self):
        return []

        # stmt = (
        #     sa.select(Article)
        #     .where(Article.status == PublicationStatus.PUBLIC)
        #     .order_by(Article.published_at.desc())
        #     .options(selectinload(Article.owner))
        #     .limit(100)
        # )
        # articles = get_multi(Article, stmt)
        # scored_articles = []
        # for article in articles:
        #     age_seconds = (arrow.now() - article.published_at).seconds
        #     karma = (article.view_count / 10 + article.like_count) / exp(
        #         age_seconds / ONE_DAY
        #     )
        #     scored_articles.append((karma, article))
        #
        # scored_articles.sort(key=lambda x: x[0], reverse=True)
        # if len(scored_articles) > TOP_NEWS_SIZE:
        #     scored_articles = scored_articles[0:TOP_NEWS_SIZE]
        #
        # return [x[1] for x in scored_articles]
