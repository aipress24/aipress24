"""Dramatiq CLI commands for queue management and workers."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import os

import click
import dramatiq
from flask.cli import with_appcontext
from flask_super.cli import group

from .scheduler import run_scheduler

WORKER_ENTRY = "app.dramatiq.worker_entry"


@group(short_help="Queue commands")
def queue() -> None:
    """Queue management commands."""


@queue.command()
@with_appcontext
def scheduler() -> None:
    """Run the task scheduler."""
    run_scheduler()


@queue.command()
@click.option(
    "-v", "--verbose", default=0, count=True, help="turn on verbose log output"
)
@click.option(
    "-p",
    "--processes",
    default=1,
    metavar="PROCESSES",
    show_default=True,
    help="the number of worker processes to run",
)
@click.option(
    "-t",
    "--threads",
    default=1,
    metavar="THREADS",
    show_default=True,
    help="the number of worker threads per process",
)
@click.option(
    "-Q",
    "--queues",
    type=str,
    default=None,
    metavar="QUEUES",
    show_default=True,
    help="listen to a subset of queues, comma separated",
)
def worker(verbose, processes, threads, queues) -> None:
    r"""Run a Dramatiq worker.

    Convenience wrapper around the upstream ``dramatiq`` CLI: this
    command ``exec``\s into ``dramatiq`` so the worker becomes the
    foreground process, which is the only way SIGINT (^C) reaches its
    own signal handlers cleanly. Running ``dramatiq.cli.main`` inside
    a Click callback leaves the fork-pool subprocesses parented to
    Click, and ^C doesn't propagate.

    The ``WORKER_ENTRY`` module loads the Flask app + initialises the
    broker as a side effect of import.

    \b
    examples:
      # Default: 1 process × 1 thread.
      $ flask queue worker

    \b
      # 1 process × 4 threads.
      $ flask queue worker -t 4

    \b
      # Listen only to specific queues.
      $ flask queue worker -Q foo,bar
    """
    args = [
        "dramatiq",
        WORKER_ENTRY,
        "--processes",
        str(processes),
        "--threads",
        str(threads),
    ]
    if queues:
        args += ["--queues", *queues.split(",")]
    args += ["-v"] * verbose
    # Replace the Click process with dramatiq so signal handling works.
    # PATH lookup is the right resolution here — the venv's bin is on
    # PATH when this CLI is invoked, and we want the dramatiq that
    # matches the installed version, not a hardcoded path.
    os.execvp("dramatiq", args)  # noqa: S606, S607


@queue.command()
@with_appcontext
def info() -> None:
    """Display information about registered actors."""
    broker = dramatiq.get_broker()
    print("The following actors are registered:")
    for actor in broker.actors.values():
        print(f"-    {actor.actor_name}@{actor.queue_name}.")
