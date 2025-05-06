# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_super.decorators import service


@service
class Context:
    """Way to access / update the Jinja context."""

    def __init__(self) -> None:
        self._context = {}

    def __getitem__(self, item):
        return self._context[item]

    def update(self, **kwargs) -> None:
        for k, v in kwargs.items():
            self._context[k] = v
