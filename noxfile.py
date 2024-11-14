# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

import nox

nox.options.sessions = ["lint", "test"]
nox.options.reuse_existing_virtualenvs = True

# NB: first one is the default
PYTHON_VERSIONS = ["3.12", "3.11", "3.10"]


@nox.session(python=PYTHON_VERSIONS)
def test(session: nox.Session) -> None:
    session.install("poetry")
    session.run("poetry", "install")
    session.run("pytest")


@nox.session(python=PYTHON_VERSIONS[0])
def lint(session: nox.Session) -> None:
    session.install("poetry")
    session.run("poetry", "install")
    session.run("poetry", "run", "make", "lint")


@nox.session(python=PYTHON_VERSIONS[0])
def check_prod(session: nox.Session) -> None:
    session.install("poetry")
    session.run("poetry", "install", "--only", "main")
    session.run("flask inspect")
