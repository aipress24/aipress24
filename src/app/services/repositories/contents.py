# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.models.content import BaseContent

from ._base import Repository


class ContentsRepository(Repository[BaseContent]):
    model_type = BaseContent
