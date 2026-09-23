# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Cron actor: update statistics (admin dashboard)."""

from __future__ import annotations

import time

from loguru import logger

from app.dramatiq.scheduler import crontab
from app.services.stats import update_stats


@crontab("0 2 * * *")
def compute_stats() -> None:
    """Daily cron: update statistics."""
    logger.info("cron: stats update starting")
    started = time.monotonic()
    update_stats()
    elapsed = time.monotonic() - started
    logger.info("cron: stats update done in {:.2f}s", elapsed)
