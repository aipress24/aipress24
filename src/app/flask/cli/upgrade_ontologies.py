"""Load new ontologies, without modifying existing ones."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import time

from flask.cli import with_appcontext
from flask_super.cli import command
from rich import print

from app.flask.bootstrap import upgrade_taxonomies
from app.flask.cli.bootstrap import fetch_bootstrap_data
from app.flask.extensions import db


@command(
    "upgrade-ontologies",
    short_help="Load only new ontologies",
)
@with_appcontext
def upgrade_ontologies_cmd() -> None:
    fetch_bootstrap_data()
    upgrade_ontologies()


def upgrade_ontologies() -> None:
    t0 = time.time()
    upgrade_taxonomies()
    db.session.commit()
    print(f"Ellapsed time: {time.time() - t0:.2f} seconds")
