# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import json
import random
from pathlib import Path

# from app.models.geoloc import GeoLocation
from app.models.mixins import Addressable
from app.settings.geonames import departement_to_region, departements, regions

CACHE: list[dict] = []


def fake_geoloc(obj: Addressable) -> None:
    if not isinstance(obj, Addressable):
        return
    if not CACHE:
        with Path("data/bano-streets-sample.json").open() as f:
            CACHE.extend(json.load(f))

    street = random.choice(CACHE)

    dept_code = random.choice(list(departements.keys()))
    obj.dept_code = dept_code
    obj.zip_code = f"{dept_code}000"
    obj.region_code = departement_to_region[obj.dept_code]

    obj.departement = departements[obj.dept_code]
    obj.region = regions[obj.region_code]

    obj.city = street["city"]
    obj.country_code = "FRA"
    obj.country = "France"

    if "housenumbers" in street:
        house_number = random.choice(list(street["housenumbers"].items()))

        obj.address = f"{house_number[0]} {street['name']}"
        obj.geo_lat = house_number[1]["lat"]
        obj.geo_lng = house_number[1]["lon"]
    else:
        obj.address = street["name"]
        obj.geo_lat = street["lat"]
        obj.geo_lng = street["lon"]
