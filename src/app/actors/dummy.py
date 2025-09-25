"""Dummy actors for testing and demonstration."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from loguru import logger

from app.dramatiq.job import job
from app.dramatiq.scheduler import crontab


@job()
def dummy() -> None:
    """Simple dummy job for testing."""
    logger.info("Dummy job running")


@crontab("* * * * *")
def dummy2() -> None:
    """Scheduled dummy job that runs every minute."""
    logger.info("Dummy2 job running")
