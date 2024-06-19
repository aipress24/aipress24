# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

import rich
import sqlalchemy.exc
import yarl
from cleez.colors import blue, green
from flask import current_app
from flask.cli import with_appcontext
from flask_mailman import EmailMessage
from flask_super.cli import command
from sqlalchemy import text

from app.flask.extensions import db
from app.flask.lib.pages import get_pages
from app.flask.lib.pywire import get_components
from app.services.healthcheck import healthcheck


@command(short_help="Show config")
@with_appcontext
def config() -> None:
    config_ = dict(sorted(current_app.config.items()))
    print("CONFIG:\n")
    for k, v in config_.items():
        try:
            print(f"{k}: {v}")
        except Exception as e:
            print(f"{k}: {e}")

    print("\nENV:\n")

    env_ = dict(sorted(os.environ.items()))
    for k, v in env_.items():
        print(f"{k}: {v}")


@command(name="debug", short_help="Show debug information")
@with_appcontext
def _debug() -> None:
    rich.print(blue("List of registered pages"))
    print()

    pages = get_pages()
    for key, _value in sorted(pages.items()):
        rich.print(f"{key}")

    print()

    rich.print(blue("List of registered components"))
    print()
    components = get_components()
    for key, _value in sorted(components.items()):
        rich.print(f"{key}")

    print()

    rich.print(blue("List of template globals"))
    print()
    for key, _value in sorted(current_app.jinja_env.globals.items()):
        rich.print(f"{key}")

    print()


@command(short_help="Health check")
@with_appcontext
def check() -> None:
    healthcheck()


@command("test-email", short_help="Send test email")
def send_test_email():
    for k in sorted(current_app.config.keys()):
        if not k.startswith("MAIL"):
            continue
        print(f"{k}: {current_app.config[k]}")

    message = EmailMessage(
        subject="Flask-Mailing module",
        to=["test@aipress24.com", "sfermigier@gmail.com"],
        body="This is the basic email body",
    )
    message.send()


@command(short_help="Load DB")
@with_appcontext
def load_db() -> None:
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
