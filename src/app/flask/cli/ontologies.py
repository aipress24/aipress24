# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask.cli import with_appcontext
from flask_super.cli import group

from app.flask.bootstrap.ontologies import (
    TAXO_NAME_ONTOLOGIE_SLUG,
    get_converter,
    import_ontologies_content,
    parse_source_ontologies,
)


@group(short_help="Manage ontologies (aka taxonomies or vocabularies)")
def ontologies() -> None:
    pass


@ontologies.command(name="dump", short_help="dump ontologies")
@with_appcontext
def print_cmd() -> None:
    raw_ontologies = parse_source_ontologies()
    for taxonomy_name, slug in TAXO_NAME_ONTOLOGIE_SLUG:
        print(taxonomy_name, slug)
        converter_class = get_converter(slug)
        converter = converter_class(raw_ontologies)
        converter.run()
        values = converter.export()
        print(values)


@ontologies.command(name="import", short_help="Import ontologies")
@with_appcontext
def import_cmd() -> None:
    import_ontologies_content()
