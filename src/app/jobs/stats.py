"""Statistics update job for calculating application metrics."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import arrow
from flask_super.registry import register

from app.flask.lib.jobs import Job
from app.services.stats import update_stats


@register
class StatsJob(Job):
    """Job for updating application statistics."""

    name = "stats"
    description = "Stats update job"

    def run(self, *args) -> None:
        """Run statistics update job.

        Args:
            *args: Command arguments. If first arg is 'recalc', recalculate
                  stats for the past 365 days.
        """
        if args and args[0] == "recalc":
            now = arrow.now()
            for i in range(365):
                date = now.shift(days=-i)
                update_stats(date)

        else:
            update_stats()
