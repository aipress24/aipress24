# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import enum
from collections.abc import Mapping
from typing import Any

from flask import Response, request
from loguru import logger
from werkzeug.exceptions import NotFound

from app.flask.lib.pages import page

from ..base import BaseWipPage
from ..home import HomePage
from .base_view import View
from .create_view import CreateView
from .detail_view import DetailView

# TEMP
# from .list_view import ListView
from .list2_view import ListView
from .update_view import UpdateView

__all__ = ["ContentsPage"]


class Mode(enum.Enum):
    LIST = "list"
    DETAIL = "detail"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


@page
class ContentsPage(BaseWipPage):
    name = "contents"
    label = "Mes articles"
    icon = "newspaper"

    parent = HomePage

    def __init__(self):
        logger.info("ContentsPage.__init__ called")

    @property
    def title(self) -> str:
        context = self.context()
        return context.get("title", self.label)

    def post(self) -> str | Response:
        view = self.get_view()
        if response := view.post():
            return response
        return self.render()

    def context(self) -> Mapping[str, Any]:
        view = self.get_view()
        ctx = view.context()
        assert isinstance(ctx, Mapping)
        return ctx

    def get_view(self) -> View:
        mode = Mode(request.args.get("mode", "list"))

        view: View
        match mode:
            case Mode.LIST:
                view = ListView()
            case Mode.DETAIL:
                view = DetailView()
            case Mode.UPDATE:
                view = UpdateView()
            case Mode.CREATE:
                view = CreateView()
            case _:
                msg = f"Can't match mode {mode}"
                raise NotFound(msg)

        return view
