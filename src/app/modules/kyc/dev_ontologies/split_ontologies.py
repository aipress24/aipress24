# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

import json
from pathlib import Path

from slugify import slugify

SOURCE = Path("./current.json")
DEST_DIR = Path("./ontology_json")


def main() -> None:
    data = json.loads(SOURCE.read_text())
    for sheet in data["body"]:
        make(sheet)


def make(sheet: dict) -> None:
    name = sheet["name"]
    slug = slugify(name)
    print(f"{name} -> {slug}")
    table_list = sheet["table"]
    while table_list and not table_list[0]:
        table_list = table_list[1:]
    print(f"  lignes: {len(table_list)}")
    destination = DEST_DIR / f"{slug}.json"
    save(destination, {"table": table_list})


def save(destination: Path, table: dict) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(table, ensure_ascii=False, indent=4),
        encoding="utf8",
    )
    print(f"  {destination}")


if __name__ == "__main__":
    main()
