# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin view to reload country zip code data."""

from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for
from sqlalchemy import func, select

from app.flask.bootstrap import import_countries, import_zip_codes
from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.modules.admin import blueprint
from app.services.zip_codes import CountryEntry, ZipCodeEntry


@blueprint.route("/reload-zip-codes", methods=["GET", "POST"])
@nav(
    parent="index",
    icon="refresh-cw",
    label="Recharger zip codes",
)
def reload_zip_codes():
    """Reload country and zip code data."""
    if request.method == "POST":
        try:
            import_countries()
            import_zip_codes()
            db.session.commit()
            flash("Les pays et codes postaux ont été chargés.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Erreur lors du chargement des codes postaux : {e}", "error")
        return redirect(url_for("admin.reload_zip_codes"))

    countries_count = db.session.scalar(select(func.count(CountryEntry.id))) or 0
    zip_codes_count = db.session.scalar(select(func.count(ZipCodeEntry.id))) or 0

    return render_template(
        "admin/pages/reload_zip_codes.j2",
        title="recharger zip codes",
        countries_count=countries_count,
        zip_codes_count=zip_codes_count,
    )
