"""Base job class for background tasks."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations


class Job:
    """Base class for background jobs."""

    name: str
    description: str = ""

    def run(self, *args) -> None:
        """Run the job with given arguments.

        Args:
            *args: Arguments passed to the job.
        """
