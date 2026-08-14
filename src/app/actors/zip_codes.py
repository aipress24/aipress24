# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Dramatiq actor for zip code and country data loading."""

from __future__ import annotations

from app.dramatiq.job import job
from app.flask.cli.zipcodes import run_reload_zip_codes


@job()
def reload_all_countries_zip_codes() -> None:
    """Dramatiq background job reload zip codes sequentially."""
    run_reload_zip_codes()
