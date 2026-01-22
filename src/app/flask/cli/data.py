"""CLI commands for data initialization and seeding."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import os
import shlex
import subprocess
import traceback
from pathlib import Path

import sqlalchemy.exc
import yarl
from cleez.colors import green
from flask import current_app
from flask.cli import with_appcontext
from flask_super.cli import group
from rich import print
from sqlalchemy import text

from app.flask.bootstrap import upgrade_taxonomies
from app.flask.extensions import db

from .bootstrap import fetch_bootstrap_data
from .bootstrap_user import import_user


@group(short_help="Data initialization commands")
def data() -> None:
    """Commands for data initialization and seeding."""


@data.command("bootstrap-users", short_help="Bootstrap users from YAML files")
@with_appcontext
def bootstrap_users_cmd() -> None:
    for path in Path("users").glob("*.yaml"):
        try:
            user = import_user(path)
            print(f"Imported user {user.email} from file: {path}")
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()
            print("Could not import user from file: ", path)


@data.command("fetch-bootstrap-data", short_help="Fetch the bootstrap data")
@with_appcontext
def fetch_bootstrap_data_cmd() -> None:
    fetch_bootstrap_data()


@data.command("upgrade-ontologies", short_help="Load only new ontologies")
@with_appcontext
def upgrade_ontologies_cmd() -> None:
    import time

    fetch_bootstrap_data()
    t0 = time.time()
    upgrade_taxonomies()
    db.session.commit()
    print(f"Elapsed time: {time.time() - t0:.2f} seconds")


@data.command("load-db", short_help="Load DB from a dump")
@with_appcontext
def load_db_cmd() -> None:
    try:
        res = db.session.execute(text("select count(*) from aut_user"))
        first_row = res.first()
        assert first_row is not None
        if first_row[0] > 0:
            print("Database is not empty")
            return
    except sqlalchemy.exc.ProgrammingError:
        pass

    print(green("Loading database..."))

    url = yarl.URL(current_app.config["SQLALCHEMY_DATABASE_URI"])
    host = url.host
    port = url.port
    db_name = url.path[1:]
    user = url.user
    password = url.password

    cmd = ["pg_restore", "-c", "-h", host, "-d", db_name]
    if port:
        cmd += ["-p", str(port)]
    if user:
        cmd += ["-U", user]
    cmd += ["db/db.dump"]

    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password

    print(shlex.join(cmd))
    print(list(Path("db").glob("*")))
    subprocess.run(cmd, env=env, check=True)
