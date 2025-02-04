# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only


from __future__ import annotations

import json
from pathlib import Path

import ijson
from sqlalchemy import delete

from app.flask.extensions import db
from app.services.zip_codes import CountryEntry, ZipCodeEntry, ZipCodeRepository

COUNTRY_SRC = Path("bootstrap_data/country_zip_code/pays.json")
ZIP_CODE_SRC = Path("bootstrap_data/country_zip_code/towns")


def import_countries() -> None:
    db.session.execute(delete(CountryEntry))
    db.session.commit()

    data = json.loads(COUNTRY_SRC.read_text())
    # filter agains actual countries having zip codes
    country_list = [
        (item["iso3"], item["name"])
        for item in data
        if ZIP_CODE_SRC.joinpath(f"{item['iso3']}.json").is_file()
    ]
    print(f"importing {len(country_list)} country names")

    def sorter(country: tuple) -> str:
        if country[0] == "FRA":
            return "000"
        return country[0]

    country_list.sort(key=sorter)
    for seq, country_tuple in enumerate(country_list):
        country_entry = CountryEntry(
            iso3=country_tuple[0], name=country_tuple[1], seq=seq
        )
        db.session.add(country_entry)

    db.session.flush()


def import_zip_codes() -> None:
    db.session.execute(delete(ZipCodeEntry))
    db.session.commit()

    print("importing zip codes")
    for path in sorted(ZIP_CODE_SRC.glob("*.json")):
        print(f"importing {path}")
        import_zip_codes_for_country(path)


def import_zip_codes_for_country(path: Path) -> None:
    iso3 = path.stem
    zip_codes = []
    count = 0
    repo = ZipCodeRepository(session=db.session)
    with path.open() as file:
        parser = ijson.items(file, "item")

        for item in parser:
            zip_code = item["zip_code"]
            name = item["name"]
            value = f"{iso3} / {zip_code} {name}"
            label = f"{zip_code} {name}"
            zip_code_entry = ZipCodeEntry(
                iso3=iso3, zip_code=zip_code, name=name, value=value, label=label
            )
            zip_codes.append(zip_code_entry)
            count += 1
            if len(zip_codes) >= 1000:
                repo.add_many(zip_codes, auto_commit=True, auto_expunge=True)
                zip_codes = []

        repo.add_many(zip_codes, auto_commit=True, auto_expunge=True)


# #
# # Currently not used
# #
#
#
# def import_countries_old() -> None:
#     put_top_of_list = ["FRA"]
#     data = json.loads(COUNTRY_SRC.read_text())
#     # filter agains actual countries having zip codes
#     country_list = [
#         (item["iso3"], item["name"])
#         for item in data
#         if ZIP_CODE_SRC.joinpath(f"{item['iso3']}.json").is_file()
#     ]
#     print(f"importing {len(country_list)} country names")
#     # fix order, put FRA first
#     for iso3 in put_top_of_list:
#         copy = [x for x in country_list if x[0] == iso3]
#         country_list = [x for x in country_list if x[0] != iso3]
#         country_list = copy + country_list
#
#     _update_or_create_countries(country_list)
#
#
# def _update_or_create_countries(country_list: list) -> None:
#     # Check that the countries table is present in DB
#     if check_countries_exist():
#         updated = _update_countries_entries(country_list)
#         print(f"    - updated values: {updated}")
#     else:
#         print("    - create countries")
#         _create_country_entries(country_list)
#
#
# def _update_countries_entries(country_list: list) -> int:
#     seq: int = 0
#     updated: int = 0
#     for iso3, name in country_list:
#         seq += 10
#         if update_country_entry(
#             iso3=iso3,
#             name=name,
#             seq=seq,
#         ):
#             updated += 1
#     return updated
#
#
# def _create_country_entries(country_list: list[str]) -> None:
#     seq: int = 0
#     for iso3, name in country_list:
#         seq += 10
#         create_country_entry(
#             iso3=iso3,
#             name=name,
#             seq=seq,
#         )
#
#
# def import_zip_codes_old() -> None:
#     print("importing zip codes")
#     for path in ZIP_CODE_SRC.glob("*.json"):
#         iso3 = path.stem
#         zip_code_list = []
#         for item in json.loads(path.read_text()):
#             zip_code = item["zip_code"]
#             name = item["name"]
#             value = f"{iso3} / {zip_code} {name}"
#             label = f"{zip_code} {name}"
#             zip_code_list.append((zip_code, name, value, label))
#         zip_code_list.sort()
#         _update_or_create_zip_code(iso3, zip_code_list)
#
#
# def _update_or_create_zip_code(iso3: str, zip_code_list: list) -> None:
#     # Check that the zip_code table is present in DB
#     if check_zip_code_exist(iso3):
#         current_zip_codes = get_full_zip_code_country(iso3)
#         if current_zip_codes == zip_code_list:
#             updated = "none"
#         else:
#             print("pb ", iso3)
#             print(current_zip_codes)
#             for a, b in zip(current_zip_codes, zip_code_list, strict=False):
#                 if a != b:
#                     print(a, b, "\n")
#             updated = _update_zip_code_entries(iso3, zip_code_list)
#         print(f"    - {iso3} updated values: {updated}")
#     else:
#         print(f"    - create {iso3} zip codes")
#         _create_zip_code_entries(iso3, zip_code_list)
#
#
# def _update_zip_code_entries(iso3: str, zip_code_list: list) -> int:
#     updated: int = 0
#     for zip_code, name, value, label in zip_code_list:
#         if update_zip_code_entry(
#             iso3=iso3,
#             zip_code=zip_code,
#             name=name,
#             value=value,
#             label=label,
#         ):
#             updated += 1
#     return updated
#
#
# def _create_zip_code_entries(iso3: str, zip_code_list: list) -> None:
#     for zip_code, name, value, label in zip_code_list:
#         create_zip_code_entry(
#             iso3=iso3,
#             zip_code=zip_code,
#             name=name,
#             value=value,
#             label=label,
#         )
