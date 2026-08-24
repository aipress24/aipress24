# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only


from __future__ import annotations

import json
from pathlib import Path

import ijson
from sqlalchemy import delete

from app.flask.extensions import db
from app.logging import warn
from app.services.zip_codes import (
    CountryEntry,
    CountryRepository,
    ZipCodeEntry,
    ZipCodeRepository,
)

# Both data directories sit at the repository root, next to `src/`.
_REPO_ROOT = Path(__file__).resolve().parents[4]

COUNTRY_SRC = _REPO_ROOT / "bootstrap_data" / "country_zip_code" / "pays.json"
ZIP_CODE_SRC = _REPO_ROOT / "bootstrap_data" / "country_zip_code" / "towns"
UPDATE_COUNTRY_SRC = _REPO_ROOT / "update_data" / "country_zip_code" / "pays.json"
UPDATE_ZIP_CODE_SRC = _REPO_ROOT / "update_data" / "country_zip_code" / "towns"

DEFAULT_NO_ZIP_CODE = [
    {"name": "Aucune donnée de code postal disponible", "zip_code": "000"}
]
LOAD_CHUNK = 5000


def get_country_update_paths() -> tuple[Path, Path]:
    """Return update paths for pays.json and towns."""
    return UPDATE_COUNTRY_SRC, UPDATE_ZIP_CODE_SRC


def import_countries(countries_path: Path = COUNTRY_SRC) -> None:
    """Replace the country table with the contents of `countries_path`.

    Read first, write second. The previous version committed the DELETE
    before parsing and caught the parse failure, so a missing or
    unreadable file emptied the table for good — that is bugs #0287 and
    #0288, « la table des pays est cassée ». Nothing is caught here: a
    reload that cannot read its source must fail before it destroys the
    data it was meant to replace.
    """
    countries = _parse_countries(countries_path)
    warn(f"loading {len(countries)} countries")

    db.session.execute(delete(CountryEntry))
    db.session.commit()

    repo = CountryRepository(session=db.session)  # type: ignore[arg-type]
    entries = [
        CountryEntry(iso3=iso3, name=name, seq=seq)
        for seq, (iso3, name) in enumerate(countries)
    ]
    repo.add_many(entries, auto_commit=True, auto_expunge=True)


def _parse_countries(countries_path: Path) -> list[tuple[str, str]]:
    """Return the (iso3, name) pairs of `countries_path`, France first."""

    def sorter(country: tuple[str, str]) -> str:
        if country[0] == "FRA":
            return "000"
        return country[0]

    data = json.loads(countries_path.read_text())
    return sorted(((item["iso3"], item["name"]) for item in data), key=sorter)


def import_zip_codes(
    countries_path: Path = COUNTRY_SRC, zipcodes_path: Path = ZIP_CODE_SRC
) -> None:
    """Replace the zip code table with the contents of `zipcodes_path`.

    Unlike the countries, the town files are streamed country by country
    (some hold hundreds of thousands of rows), so the table is emptied
    before the load rather than after. A country whose file is broken is
    skipped so the other 200 still load, but the failures are raised at
    the end: a silent skip leaves a country with no zip code at all and
    nobody the wiser.
    """
    db.session.execute(delete(ZipCodeEntry))
    db.session.commit()

    failures: list[str] = []
    for iso3, _name in _parse_countries(countries_path):
        try:
            import_one_country_zip_codes(zipcodes_path / f"{iso3}.json")
        except Exception as e:
            # ken: not swallowed — collected and raised below.
            db.session.rollback()
            failures.append(f"{iso3} ({e})")

    if failures:
        msg = f"Échec du chargement des codes postaux : {', '.join(failures)}"
        raise RuntimeError(msg)


def import_one_country_zip_codes(iso3_path: Path) -> None:
    """Load one country's zip codes, or a placeholder if it has no file."""
    if iso3_path.is_file():
        import_zip_codes_for_country(iso3_path)
    else:
        import_default_zip_code_for_country(iso3_path)


def import_default_zip_code_for_country(iso3_path: Path) -> None:
    iso3 = iso3_path.stem
    repo = ZipCodeRepository(session=db.session)  # type: ignore[arg-type]
    zip_codes = []
    for item in DEFAULT_NO_ZIP_CODE:
        zip_code = item["zip_code"]
        name = item["name"]
        value = f"{iso3} / {zip_code} {name}"
        label = f"{zip_code} {name}"
        zip_code_entry = ZipCodeEntry(
            iso3=iso3, zip_code=zip_code, name=name, value=value, label=label
        )
        zip_codes.append(zip_code_entry)
    warn(f"loading {iso3} {len(zip_codes)} zipcodes")
    repo.add_many(zip_codes, auto_commit=True, auto_expunge=True)


def import_zip_codes_for_country(iso3_path: Path) -> None:
    iso3 = iso3_path.stem
    zip_codes = []
    count = 0
    repo = ZipCodeRepository(session=db.session)  # type: ignore[arg-type]
    with iso3_path.open() as file:
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
            if len(zip_codes) >= LOAD_CHUNK:
                repo.add_many(zip_codes, auto_commit=True, auto_expunge=True)
                warn(f"loaded {iso3} {len(zip_codes)} zipcodes")
                zip_codes = []
        repo.add_many(zip_codes, auto_commit=True, auto_expunge=True)
        warn(f"loaded {iso3} {len(zip_codes)} zipcodes")


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
