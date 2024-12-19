# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from werkzeug.local import LocalProxy


def unproxy(obj):
    if isinstance(obj, LocalProxy):
        return obj._get_current_object()
    return obj
