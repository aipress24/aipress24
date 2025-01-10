# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only


from __future__ import annotations

import json
import time
from pathlib import Path

from app.flask.extensions import db

# from app.enums import OrganisationTypeEnum
# from app.models.organisation_light import LightOrganisation
from app.services.countries import (
    check_countries_exist,
    create_country_entry,
    update_country_entry,
)
from app.services.zip_code import (
    check_zip_code_exist,
    create_zip_code_entry,
    get_full_zip_code_country,
    update_zip_code_entry,
)

# format for HTML selects
VALUE_LABEL_MODE = False

COUNTRY_SRC = Path("data/country_zip_code/pays.json")
ZIP_CODE_SRC = Path("data/country_zip_code/towns")


def import_countries() -> None:
    put_top_of_list = ["FRA"]
    data = json.loads(COUNTRY_SRC.read_text())
    # filter agains actual countries having zip codes
    country_list = [
        (item["iso3"], item["name"])
        for item in data
        if ZIP_CODE_SRC.joinpath(f"{item['iso3']}.json").is_file()
    ]
    print(f"importing {len(country_list)} country names")
    # fix order, put FRA first
    for iso3 in put_top_of_list:
        copy = [x for x in country_list if x[0] == iso3]
        country_list = [x for x in country_list if x[0] != iso3]
        country_list = copy + country_list
    _update_or_create_countries(country_list)


def _update_or_create_countries(country_list: list) -> None:
    # Check that the countries table is present in DB
    if check_countries_exist():
        updated = _update_countries_entries(country_list)
        print(f"    - updated values: {updated}")
    else:
        print("    - create countries")
        _create_country_entries(country_list)


def _update_countries_entries(country_list: list) -> int:
    seq: int = 0
    updated: int = 0
    for iso3, name in country_list:
        seq += 10
        if update_country_entry(iso3=iso3, name=name, seq=seq):
            updated += 1
    return updated


def _create_country_entries(country_list: list[str]) -> None:
    seq: int = 0
    for iso3, name in country_list:
        seq += 10
        create_country_entry(iso3=iso3, name=name, seq=seq)


def import_zip_codes() -> None:
    print("importing zip codes")
    for path in sorted(ZIP_CODE_SRC.glob("*.json")):
        print(f"  - importing: {path}")
        iso3 = path.stem
        zip_code_list = []
        for item in json.loads(path.read_text()):
            zip_code = item["zip_code"]
            name = item["name"]
            value = f"{iso3} / {zip_code} {name}"
            label = f"{zip_code} {name}"
            zip_code_list.append((zip_code, name, value, label))

        print(f"    - {len(zip_code_list)} zip codes to import")
        t0 = time.time()
        zip_code_list.sort()
        for zip_code, name, value, label in zip_code_list:
            create_zip_code_entry(
                iso3=iso3, zip_code=zip_code, name=name, value=value, label=label
            )
        db.session.commit()
        print(f"    - imported in {time.time() - t0:.2f} s")


def _update_or_create_zip_code(iso3: str, zip_code_list: list) -> None:
    # Check that the zip_code table is present in DB
    if check_zip_code_exist(iso3):
        current_zip_codes = get_full_zip_code_country(iso3)
        if current_zip_codes == zip_code_list:
            updated = "none"
        else:
            print("pb ", iso3)
            # print(current_zip_codes)
            # for a, b in zip(current_zip_codes, zip_code_list, strict=False):
            #     if a != b:
            #         print(a, b, "\n")
            updated = _update_zip_code_entries(iso3, zip_code_list)
        print(f"    - {iso3} updated values: {updated}")
    else:
        print(f"    - create {iso3} zip codes")
        _create_zip_code_entries(iso3, zip_code_list)


def _update_zip_code_entries(iso3: str, zip_code_list: list) -> int:
    updated: int = 0
    for zip_code, name, value, label in zip_code_list:
        if update_zip_code_entry(
            iso3=iso3, zip_code=zip_code, name=name, value=value, label=label
        ):
            updated += 1
    return updated


def _create_zip_code_entries(iso3: str, zip_code_list: list) -> None:
    for zip_code, name, value, label in zip_code_list:
        create_zip_code_entry(
            iso3=iso3, zip_code=zip_code, name=name, value=value, label=label
        )
