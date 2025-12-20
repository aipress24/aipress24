# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import json

import click
from flask.cli import with_appcontext
from flask_super.cli import group
from rich import print

from app.modules.search.backend import SearchBackend
from app.modules.search.views import SearchResults

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


@index.command(short_help="List collections")
@with_appcontext
def collections() -> None:
    client = backend.get_client()
    collections = client.collections
    for collection in collections.retrieve():
        print(collection)


@index.command(short_help="Dump index content")
@with_appcontext
def dump() -> None:
    client = backend.get_client()
    collections = client.collections
    for collection in collections.retrieve():
        collection_name = collection["name"]
        print("Collection:", collection_name)
        documents = client.collections[collection_name].documents
        export = documents.export()

        if not export:
            print("No documents")
            print()
            continue

        json_lines = export.split("\n")
        for json_line in json_lines:
            data = json.loads(json_line)
            print(data)
        print()


@index.command(short_help="Search")
@click.argument("qs")
@with_appcontext
def search(qs) -> None:
    filter = "all"
    results = SearchResults(qs, filter)
    for rs in results.result_sets:
        print(rs.name, rs.count)
        for hit in rs.hits:
            print(hit)
