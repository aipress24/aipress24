"""CLI commands for development and debugging."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import operator
from importlib.metadata import distributions
from pathlib import Path
from typing import cast

import click
import rich
from cleez.colors import blue
from flask import current_app
from flask.cli import with_appcontext
from flask_mailman import EmailMessage
from flask_super.cli import command, group
from sqlalchemy import text

from app.flask.lib.pywire import component_registry, get_components
from app.lib.names import to_kebab_case
from app.services.healthcheck import healthcheck


@group(short_help="Development & debugging tools")
def dev() -> None:
    """Commands for development inspection and debugging."""


@dev.command("debug", short_help="Show debug information")
@with_appcontext
def debug_cmd() -> None:
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


@dev.command("check", short_help="Health check")
@click.option("--db", is_flag=True)
@click.option("--full", is_flag=True)
@with_appcontext
def check_cmd(db=False, full=False) -> None:
    from app.flask.extensions import db as _db

    if db:
        _db.session.execute(text("select 1"))
        print("db test OK")
        return

    if full:
        healthcheck()
        return

    print("Smoke test OK")


@dev.command("components", short_help="List components")
@with_appcontext
def components_cmd() -> None:
    print(blue("Static components:"))
    registry1 = component_registry
    for k, v in sorted(registry1.items()):
        print(f"{k}: {v}")

    print()

    print(blue("Live components:"))
    for component_cls in get_components().values():
        component_name = to_kebab_case(component_cls.__name__)
        print(f"{component_name}: {component_cls}")


@dev.command("packages", short_help="List installed packages")
def packages_cmd() -> None:
    sizes = []
    for distribution in distributions():
        size = 0
        files = distribution.files or []
        for file in files:
            path = cast("Path", file.locate())
            if not path.exists():
                continue
            size += path.stat().st_size

        sizes += [(size, distribution)]

    sizes.sort(key=operator.itemgetter(0), reverse=True)

    packages_info = [("Size", "Name", "Version")]
    for size, distribution in sizes:
        name = distribution.metadata["Name"]
        version = distribution.metadata["Version"]
        size_str = f"{size / 1024 / 1024:.2f} MB"
        packages_info += [(size_str, name, version)]
        print(f"{size_str} {name} {version}")


# Standalone command (not in a group)
@command("test-email", short_help="Send test email")
def send_test_email() -> None:
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
