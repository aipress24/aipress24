# Copyright (c) 2025-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""CLI command to reload country and zip code data."""

from __future__ import annotations

from flask.cli import with_appcontext
from flask_super.cli import command
from rich import print

from app.flask.bootstrap.zip_codes import (
    get_country_update_paths,
    import_countries,
    import_zip_codes,
)


def run_reload_zip_codes() -> None:
    """Reload countries and zip codes from `update_data`.

    Also runs as a Dramatiq job (see `app.actors.zip_codes`), hence no
    printing here and no reliance on the current working directory.
    """
    countries_path, zipcodes_path = get_country_update_paths()
    import_countries(countries_path)
    import_zip_codes(countries_path, zipcodes_path)


@command("zipcodes", short_help="Recharger les pays et les codes postaux")
@with_appcontext
def zipcodes_cmd() -> None:
    """Command 'flask zipcodes' to reload country and zipcodes."""
    run_reload_zip_codes()
    print("Mise à jour des pays et des codes postaux terminée.")
