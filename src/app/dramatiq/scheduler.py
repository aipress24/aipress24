"""Cron-based task scheduler for Dramatiq jobs."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import dramatiq
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from .lazy_actor import LazyActor

_actor_registry: set[LazyActor] = set()


def crontab(crontab: str):
    """Decorator to register a function as a scheduled cron job.

    Args:
        crontab: Cron expression for scheduling (e.g., '0 * * * *').

    Returns:
        Decorator function that wraps the target function.
    """

    def decorator(func):
        logger.debug("Registering cron job: {}", func.__name__)
        actor = LazyActor(func, crontab=crontab)
        _actor_registry.add(actor)
        return actor

    return decorator


def register_cron_jobs() -> None:
    """Register all cron jobs with the Dramatiq broker."""
    logger.info("Registering cron jobs on Dramatiq")

    for actor in _actor_registry:
        logger.info("Registering cron job: {}", actor)
        broker = dramatiq.get_broker()
        actor.register(broker)


def run_scheduler() -> int:
    """Run the APScheduler blocking scheduler for cron jobs.

    Returns:
        int: Exit code (0 for success).
    """
    scheduler = BlockingScheduler()

    for actor in _actor_registry:
        logger.info("Registering cron job: {}", actor)

        scheduler.add_job(
            actor.send,
            CronTrigger.from_crontab(actor.crontab),
        )

    try:
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.shutdown()

    return 0
