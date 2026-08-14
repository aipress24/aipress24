# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin view to reload country zip code data."""

from __future__ import annotations

from pathlib import Path

from flask import flash, redirect, render_template, request, url_for
from sqlalchemy import func, select

from app.flask.bootstrap.zip_codes import get_country_update_paths
from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.modules.admin import blueprint
from app.services.zip_codes import CountryEntry, ZipCodeEntry


def _country_update_path() -> tuple[Path, Path]:
    return get_country_update_paths()


@blueprint.route("/reload-zip-codes", methods=["GET", "POST"])
@nav(
    parent="index",
    icon="refresh-cw",
    label="Màj zip codes",
)
def reload_zip_codes():
    """Reload country and zip code data."""
    if request.method == "POST":
        from app.actors.zip_codes import reload_all_countries_zip_codes

        reload_all_countries_zip_codes.send()
        flash(
            "Mise à jour des pays et des codes postaux lancée en arrière-plan.",
            "info",
        )
        return redirect(url_for("admin.reload_zip_codes"))

    countries_count = db.session.scalar(select(func.count(CountryEntry.id))) or 0
    zip_codes_count = db.session.scalar(select(func.count(ZipCodeEntry.id))) or 0

    return render_template(
        "admin/pages/reload_zip_codes.j2",
        title="Màj zip codes",
        countries_count=countries_count,
        zip_codes_count=zip_codes_count,
    )
