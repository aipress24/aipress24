# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import json

from flask import Response


def toast(response: Response, msg) -> None:
    response.headers["HX-Trigger"] = json.dumps({"showToast": msg})
