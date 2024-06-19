# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from svcs.flask import container

from app.dramatiq.scheduler import crontab
from app.services import reputation
from app.services.emails import EmailService


@crontab("0 * * * *")
def update_reputations() -> None:
    """Update reputations for all users."""

    print("Updating reputations...")
    reputation.update_reputations(add_noise=True)
    print("... done")

    email_service = container.get(EmailService)
    email_service.send_system_email("Reputations updated")
