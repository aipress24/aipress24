# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import enum
from typing import Any

from devtools import debug
from flask import request
from werkzeug.exceptions import NotFound

from .create_view import CreateView
from .detail_view import DetailView
from .list_view import ListView
from .update_view import UpdateView


class Mode(enum.Enum):
    LIST = "list"
    DETAIL = "detail"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class CrudMixin:
    label = "CRUD"

    @property
    def title(self):
        context = self.context()
        return context.get("title", self.label)

    def context(self) -> dict[str, Any]:
        mode = Mode(request.args.get("mode", "list"))

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
                raise NotFound(f"Can't match mode {mode}")

        ctx = view.context()
        debug(ctx)
        return ctx
