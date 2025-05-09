# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sys
from pathlib import Path

import click
import dramatiq
from dramatiq.cli import (
    main as dramatiq_worker,
    make_argument_parser as dramatiq_argument_parser,
)
from flask import current_app
from flask.cli import with_appcontext
from flask_super.cli import group
from loguru import logger

from app.actors.dummy import dummy

from .scheduler import run_scheduler

BROKER = "app.dramatiq.setup:setup_broker"


@group(short_help="Queue commands")
def queue() -> None:
    pass


@queue.command()
@with_appcontext
def scheduler() -> None:
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
    help="the number of worker treads per processes",
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
@with_appcontext
def worker(verbose, processes, threads, queues) -> None:
    """Run dramatiq workers.

    Setup Dramatiq with broker and task modules from Flask app.

    \b
    examples:
      # Run dramatiq with 1 thread per process.
      $ flask worker --threads 1

    \b
      # Listen only to the "foo" and "bar" queues.
      $ flask worker -Q foo,bar

    \b
      # Consuming from a specific broker
      $ flask worker mybroker
    """
    # Plugin for flask.commands entrypoint.
    #
    # Wraps dramatiq worker CLI in a Flask command. This is private API of
    # dramatiq.

    parser = dramatiq_argument_parser()

    # Set worker broker globally.
    # needle = "dramatiq-" + broker_name
    # broker = current_app.extensions[needle].broker
    # set_broker(broker)

    command = [
        "--processes",
        str(processes),
        "--threads",
        str(threads),
        # This module does not have broker local. Thus dramatiq fallbacks to
        # global broker.
        __name__,
    ]
    if current_app.config["DEBUG"]:
        verbose = max(1, verbose)
        # if HAS_WATCHDOG:
        #     command += ["--watch", guess_code_directory(broker)]

    if queues:
        queues = queues.split(",")
    else:
        queues = []
    if queues:
        command += ["--queues", *queues]

    command += verbose * ["-v"]

    args = parser.parse_args(command)

    broker = dramatiq.get_broker()

    logger.info("Able to execute the following actors:")
    for actor in list_managed_actors(broker, queues):
        current_app.logger.info("    %s.", format_actor(actor))

    args.broker = BROKER
    dramatiq_worker(args)


@queue.command()
@with_appcontext
def info() -> None:
    broker = dramatiq.get_broker()
    all_actors = broker.actors.values()

    print("The following actors are registered:")
    for actor in all_actors:
        print(f"-    {format_actor(actor)}.")


def list_managed_actors(broker, queues):
    queues = set(queues)
    all_actors = broker.actors.values()
    if not queues:
        return all_actors
    return [a for a in all_actors if a.queue_name in queues]


def guess_code_directory(broker):
    actor = next(iter(broker.actors.values()))
    modname, *_ = actor.fn.__module__.partition(".")
    mod = sys.modules[modname]
    return Path(mod.__file__).parent


def format_actor(actor) -> str:
    return f"{actor.actor_name}@{actor.queue_name}"


@queue.command()
@with_appcontext
def launch_dummy() -> None:
    dummy.send()
