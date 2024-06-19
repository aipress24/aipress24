# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from attr import frozen


@frozen
class BreadCrumb:
    label: str
    url: str

    @property
    def href(self) -> str:
        return self.url

    @property
    def name(self) -> str:
        return self.label
