# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import nox

# nox.options.default_venv_backend = "uv"
# nox.options.reuse_existing_virtualenvs = True

# NB: first one is the default
PYTHONS = ["3.12", "3.11", "3.13", "3.14"]


@nox.session(python=PYTHONS)
def tests(session: nox.Session) -> None:
    uv_sync(session)
    session.run("pytest")


@nox.session(python=PYTHONS[0])
def lint(session: nox.Session) -> None:
    uv_sync(session)
    session.run("uv", "run", "--active", "make", "lint")


@nox.session(python=PYTHONS[0])
def check_prod(session: nox.Session) -> None:
    session.run("uv", "run", "flask", "inspect")


#
# Utils
#
def uv_sync(session: nox.Session):
    session.run("uv", "sync", "--all-groups", "--all-extras", "--active", external=True)
