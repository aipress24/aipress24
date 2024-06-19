# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from loguru import logger

from app.dramatiq.job import job
from app.dramatiq.scheduler import crontab


@job()
def dummy():
    logger.info("Dummy job running")


@crontab("* * * * *")
def dummy2():
    logger.info("Dummy2 job running")
