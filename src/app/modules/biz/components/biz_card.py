# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import Any

from attr import frozen

from app.flask.lib.pywire import Component, component


@component
@frozen
class BizCard(Component):
    obj: Any
    show_author: bool = True

    def __attrs_post_init__(self) -> None:
        # "Hot fixes" for the marketplace object.
        self.obj._url = "#"
        self.obj.author = self.obj.owner
