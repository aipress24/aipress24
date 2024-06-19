# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import dramatiq
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from .lazy_actor import LazyActor

_actor_registry = set()


def crontab(crontab: str):
    def decorator(func):
        logger.debug("Registering cron job: {}", func.__name__)
        actor = LazyActor(func, crontab=crontab)
        _actor_registry.add(actor)
        return actor

    return decorator


def register_cron_jobs():
    logger.info("Registering cron jobs on Dramatiq")

    for actor in _actor_registry:
        logger.info("Registering cron job: {}", actor)
        broker = dramatiq.get_broker()
        actor.register(broker)


def run_scheduler() -> int:
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
