# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import click
from flask.cli import with_appcontext
from flask_super.cli import command
from flask_super.registry import lookup
from rich import print

from app.flask.lib.jobs import Job


#
# Other operational commands
#
@command()
@click.argument("args", nargs=-1)
@with_appcontext
def job(args) -> None:
    all_jobs = [cls() for cls in lookup(Job)]

    if not args:
        print("Usage: 'flask job <job name> <args>', where <job name> can be:")
        print()
        for job in all_jobs:
            print(f"- {job.name}: {job.description}")
        return

    job_name = args[0]
    for job in all_jobs:
        if job.name == job_name:
            job.run(*args[1:])
            return

    print(f"No such job: {job_name}")
