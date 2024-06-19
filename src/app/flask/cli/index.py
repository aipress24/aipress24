# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask.cli import with_appcontext
from flask_super.cli import group
from rich import print

from app.modules.search.backend import SearchBackend

backend = SearchBackend()


@group(short_help="Manage index (typesense)")
def index() -> None:
    pass


@index.command(short_help="Initialize index")
@with_appcontext
def init() -> None:
    backend.make_schema()
    print("[green]Schema created[/green]")


@index.command(name="import", short_help="Import content")
@with_appcontext
def import_() -> None:
    backend.index_all()
    print("[green]Content imported[/green]")


@index.command(short_help="Rebuild index (drop + init + import)")
@with_appcontext
def rebuild() -> None:
    backend.make_schema()
    print("[green]Schema created[/green]")
    backend.index_all()
    print("[green]Content imported[/green]")
