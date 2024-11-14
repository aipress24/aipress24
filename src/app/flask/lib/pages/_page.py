# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import Any

from flask import render_template, render_template_string, url_for
from svcs.flask import container
from werkzeug import Response

from app.flask.extensions import htmx
from app.services.context import Context
from app.services.menus import MenuService


class Page:
    name: str
    label: str
    path: str
    template: str = ""
    parent: Any = None
    args: dict = {}
    order: float = 0.0

    # breadcrumbs: list = []
    breadcrumbs2: list = []
    icon: str | None = None

    #
    # HTTP Methods
    #
    def get(self) -> str | Response:
        if htmx.boosted:
            return self.render()

        if htmx:
            return self.hx_get()

        return self.render()

    def post(self) -> str | Response:
        if htmx:
            return self.hx_post()
        return self.render()

    def hx_get(self) -> str | Response:
        return self.render()

    def hx_post(self) -> str | Response:
        return self.render()

    def context(self) -> dict[str, Any] | Response:
        """Override in subclasses to add context data.

        May also return a Response object.
        """
        return {}

    def menus(self):
        """Override in subclasses to menus."""
        return {}

    def get_template_path(self):
        if self.template:
            return self.template
        else:
            raise NotImplementedError

    #
    # Do not override these
    #
    def render(self) -> str | Response:
        menus = container.get(MenuService)
        menus.update(self.menus())

        context = container.get(Context)
        context.update(page=self, breadcrumbs=self.breadcrumbs)

        page_ctx = self.context()

        if isinstance(page_ctx, Response):
            return page_ctx

        ctx = {**page_ctx}
        if "page" not in ctx:
            ctx["page"] = self
        if "title" not in ctx:
            if hasattr(self, "title"):
                ctx["title"] = self.title
            else:
                ctx["title"] = self.label

        return self.content(ctx)

    def content(self, ctx):
        if template_str := self.get_template_str(ctx):
            return render_template_string(template_str, **ctx)
        else:
            return render_template(self.get_template_path(), **ctx)

    # def base_context(self):
    #     context = {}
    #     if hasattr(self, "view_model") and "model" not in context:
    #         context["model"] = self.view_model
    #
    #     if "model" in context:
    #         model = unwrap(context["model"])
    #         context["og_data"] = to_opengraph(model)
    #         context["json_ld"] = to_json_ld(model)
    #
    #     return context

    @property
    def breadcrumbs(self):
        breadcrumbs = [
            {"name": self.label, "href": self.url, "current": True},
        ]
        if not self.parent:
            return breadcrumbs

        parent = self.parent()
        while True:
            breadcrumbs += [
                {"name": parent.label, "href": parent.url, "current": False},
            ]
            if not parent.parent:
                break
            parent = parent.parent()

        breadcrumbs.reverse()
        return breadcrumbs

    @property
    def url(self):
        return url_for(f".{self.name}", **self.args)

    def get_template_str(self, ctx=None) -> str:
        if ctx and "_template_str" in ctx:
            return ctx["_template_str"]
        elif hasattr(self, "template_str"):
            return self.template_str
        else:
            return ""
