# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import re

from .ui import *  # noqa

_settings = {}


def get_settings():
    """Get settings, to inject in Jinja context."""
    if _settings:
        return _settings
    for name in globals():
        if name.startswith("_"):
            continue
        if not re.match(r"^[A-Z_]+$", name):
            continue
        _settings[name] = globals()[name]

    return _settings
