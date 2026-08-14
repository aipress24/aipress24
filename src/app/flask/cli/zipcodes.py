# Copyright (c) 2025-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""CLI command to reload country and zip code data."""

from __future__ import annotations

import json

from flask.cli import with_appcontext
from flask_super.cli import command
from rich import print
from sqlalchemy import delete

from app.flask.bootstrap.zip_codes import (
    get_country_update_paths,
    import_countries_chore,
    import_one_country_zip_codes,
)
from app.flask.extensions import db
from app.logging import warn
from app.services.zip_codes import CountryEntry, ZipCodeEntry


def run_reload_zip_codes() -> None:
    """Reload country and zip codes."""
    db.session.execute(delete(CountryEntry))
    db.session.commit()

    try:
        import_countries_chore()
    except Exception as e:
        db.session.rollback()
        warn(f"Erreur lors de l'import des pays: {e}")
    db.session.commit()
    print("Mise à jour des pays terminée avec succès")

    countries_path, zipcodes_path = get_country_update_paths()
    if not countries_path.is_file():
        msg = f"{countries_path!r}"
        raise FileNotFoundError(msg)

    # Delete existing zip codes
    db.session.execute(delete(ZipCodeEntry))
    db.session.commit()

    # Process countries sequentially one by one
    data = json.loads(countries_path.read_text())
    for item in data:
        iso3 = item["iso3"]
        iso3_path = zipcodes_path.joinpath(f"{iso3}.json")
        try:
            import_one_country_zip_codes(iso3_path)
        except Exception as e:
            db.session.rollback()
            msg = f"Erreur lors de l'import des codes postaux pour {iso3}: {e}"
            warn(msg)
            print(msg)

    print("Mise à jour des codes postaux terminée.")

    # test:
    from sqlalchemy import select

    test_entry = db.session.scalars(
        select(ZipCodeEntry).where(
            ZipCodeEntry.iso3 == "FRA", ZipCodeEntry.name == "Brest"
        )
    ).first()
    print("test d'une valeur:", test_entry.value)


@command("zipcodes", short_help="Recharger les pays et les codes postaux")
@with_appcontext
def zipcodes_cmd() -> None:
    """Command 'flask zipcodes' to reload country and zipcodes."""
    run_reload_zip_codes()
