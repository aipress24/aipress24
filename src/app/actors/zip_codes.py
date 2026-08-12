# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Dramatiq actor for zip code and country data loading."""

from __future__ import annotations

import json

from sqlalchemy import delete

from app.dramatiq.job import job
from app.flask.extensions import db
from app.logging import warn
from app.services.zip_codes import CountryEntry, ZipCodeEntry


@job()
def reload_all_countries_zip_codes() -> None:
    """Dramatiq background job reload zip codes sequentially."""
    from app.flask.bootstrap.zip_codes import (
        import_countries_chore,
        import_one_country_zip_codes,
    )
    from app.modules.admin.views.reload_zip_codes import _country_update_path

    # countries
    db.session.execute(delete(CountryEntry))
    db.session.commit()

    try:
        import_countries_chore()
    except Exception as e:
        db.session.rollback()
        warn(f"Dramatiq error importing countries: {e}")
    db.session.commit()
    warn("Dramatiq: completed countries reload")

    # zip codes

    countries_path, zipcodes_path = _country_update_path()
    if not countries_path.is_file():
        warn(f"Dramatiq: error {countries_path} not found")
        return

    warn("Dramatiq: starting sequential zip codes reload")

    # Delete existing zip codes
    db.session.execute(delete(ZipCodeEntry))
    db.session.commit()

    # Process countries sequentially one by one in a single thread
    data = json.loads(countries_path.read_text())
    for item in data:
        iso3 = item["iso3"]
        iso3_path = zipcodes_path.joinpath(f"{iso3}.json")
        try:
            import_one_country_zip_codes(iso3_path)
        except Exception as e:
            db.session.rollback()
            warn(f"Dramatiq error importing zip codes for {iso3}: {e}")

    warn("Dramatiq: completed sequential zip codes reload")
