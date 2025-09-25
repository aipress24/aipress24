"""Job decorator and registry for Dramatiq actors."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import dramatiq
from loguru import logger

from .lazy_actor import LazyActor

_actor_registry = set()


def job():
    """Decorator to register a function as a Dramatiq job.

    Returns:
        Decorator function that wraps the target function.
    """

    def decorator(func):
        logger.debug("Registering cron job: {}", func.__name__)
        actor = LazyActor(func)
        _actor_registry.add(actor)
        return actor

    return decorator


def register_regular_jobs() -> None:
    """Register all regular jobs with the Dramatiq broker."""
    logger.info("Registering regular jobs on Dramatiq")

    for actor in _actor_registry:
        logger.info("Registering cron job: {}", actor)
        broker = dramatiq.get_broker()
        actor.register(broker)
