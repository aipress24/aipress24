"""Reputation update actors for user scoring."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from loguru import logger

from app.dramatiq.scheduler import crontab
from app.services import reputation


@crontab("0 * * * *")
def update_reputations() -> None:
    """Update reputations for all users."""
    logger.info("cron: reputation update starting")
    reputation.update_reputations(add_noise=True)
    logger.info("cron: reputation update done")
