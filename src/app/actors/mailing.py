"""Mailing actors for email sending jobs."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_mailman import EmailMessage
from loguru import logger

from app.dramatiq.scheduler import crontab


@crontab("* * * * *")
def send_test_email() -> None:
    """Send a test email every minute for testing purposes."""
    print("Sending test email")
    logger.info("Sending test email")
    message = EmailMessage(
        subject="Flask-Mailing module",
        to=["test@aipress24.com"],
        body="This is the basic email body",
    )
    message.send()
