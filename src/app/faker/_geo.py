# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import json
import random
from pathlib import Path

from app.models.geoloc import GeoLocation
from app.settings.geonames import departement_to_region, departements, regions

CACHE: list[dict] = []


def fake_geoloc() -> GeoLocation:
    if not CACHE:
        with Path("data/bano-streets-sample.json").open() as f:
            CACHE.extend(json.load(f))

    street = random.choice(CACHE)

    geoloc = GeoLocation()

    # postcode = street["postcode"]
    # if not isinstance(postcode, str):
    #     postcode = postcode[0]

    dept_code = random.choice(list(departements.keys()))
    geoloc.dept_code = dept_code
    geoloc.postal_code = f"{dept_code}000"
    geoloc.region_code = departement_to_region[geoloc.dept_code]

    geoloc.departement = departements[geoloc.dept_code]
    geoloc.region = regions[geoloc.region_code]

    geoloc.city_name = street["city"]
    geoloc.country_name = "France"

    if "housenumbers" in street:
        house_number = random.choice(list(street["housenumbers"].items()))

        geoloc.address = f"{house_number[0]} {street['name']}"
        geoloc.lat = house_number[1]["lat"]
        geoloc.lng = house_number[1]["lon"]
    else:
        geoloc.address = street["name"]
        geoloc.lat = street["lat"]
        geoloc.lng = street["lon"]

    return geoloc
