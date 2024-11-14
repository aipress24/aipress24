# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.lib.types import JSON


def to_json_ld(obj) -> JSON:
    if meth := getattr(obj, "to_json_ld", None):
        return meth()
    else:
        return {}
