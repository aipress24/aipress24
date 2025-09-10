# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from pathlib import Path

from devtools import debug
from flask import current_app
from werkzeug.exceptions import NotFound

from app.modules.public import get


@get("/sandbox/<path:path>")
def sandbox(path: str):
    path = path.removesuffix("/")

    root = Path(current_app.root_path).parent.parent.parent / "sandbox-pages"
    debug(root)
    html_file = root / (path + ".html")
    if not html_file.exists():
        msg = "File not found"
        raise NotFound(msg)

    return html_file.read_text()
