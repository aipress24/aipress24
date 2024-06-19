# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from cleez.colors import blue
from flask.cli import with_appcontext
from flask_super.cli import command
from svcs.flask import container

from app.flask.lib.pages import PageRegistry
from app.lib.names import fqdn


@command(short_help="List pages")
@with_appcontext
def pages() -> None:
    print(blue("Pages:"))

    page_registry = container.get(PageRegistry)
    page_classes = page_registry.get_pages()
    for page_class in sorted(page_classes, key=fqdn):
        print(page_class)
