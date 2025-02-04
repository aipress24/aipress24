# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import nox

nox.options.default_venv_backend = "uv|virtualenv"
nox.options.sessions = ["lint", "test", "check_prod"]
nox.options.reuse_existing_virtualenvs = True

# NB: first one is the default
PYTHON_VERSIONS = ["3.12", "3.11", "3.13"]


@nox.session(python=PYTHON_VERSIONS)
def test(session: nox.Session) -> None:
    session.run("uv", "sync")
    session.run("pytest")


@nox.session(python=PYTHON_VERSIONS[0])
def lint(session: nox.Session) -> None:
    session.run("uv", "sync")
    session.run("uv", "run", "make", "lint")


@nox.session(python=PYTHON_VERSIONS[0])
def check_prod(session: nox.Session) -> None:
    session.install(".")
    session.run("uv", "run", "flask", "inspect")
    # session.run("flask inspect")
