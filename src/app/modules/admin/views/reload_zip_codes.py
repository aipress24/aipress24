# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin view to reload country zip code data."""

from __future__ import annotations

from pathlib import Path

from flask import flash, redirect, render_template, request, url_for
from sqlalchemy import func, select

from app.flask.bootstrap import import_countries, import_zip_codes
from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.modules.admin import blueprint
from app.services.zip_codes import CountryEntry, ZipCodeEntry


def _country_update_path() -> tuple[Path, Path]:
    root_path = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
    update_path = root_path / "update_data"
    countries_path = update_path / "country_zip_code" / "pays.json"
    zipcodes_path = update_path / "country_zip_code" / "towns"
    return countries_path, zipcodes_path


@blueprint.route("/reload-zip-codes", methods=["GET", "POST"])
@nav(
    parent="index",
    icon="refresh-cw",
    label="Recharger zip codes",
)
def reload_zip_codes():
    """Reload country and zip code data."""
    countries_path, zipcodes_path = _country_update_path()
    if request.method == "POST":
        import_countries(countries_path)
        import_zip_codes(countries_path, zipcodes_path)
        flash("Les pays et codes postaux ont été chargés.", "success")
        return redirect(url_for("admin.reload_zip_codes"))

    countries_count = db.session.scalar(select(func.count(CountryEntry.id))) or 0
    zip_codes_count = db.session.scalar(select(func.count(ZipCodeEntry.id))) or 0

    return render_template(
        "admin/pages/reload_zip_codes.j2",
        title="recharger zip codes",
        countries_count=countries_count,
        zip_codes_count=zip_codes_count,
    )
