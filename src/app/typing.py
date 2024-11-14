# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import TypeAlias

Json: TypeAlias = dict[str, "Json"] | list["Json"] | str | int | float | bool | None
JsonDict: TypeAlias = dict[str, Json]
JsonList: TypeAlias = list[Json]
