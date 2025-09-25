"""Reputation calculation job for user scoring."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_super.registry import register

from app.flask.lib.jobs import Job
from app.services import reputation


@register
class ReputationJob(Job):
    name = "reputation"
    description = "Reputation update job"

    def run(self, *args) -> None:
        reputation.update_reputations(show_progress=True)
