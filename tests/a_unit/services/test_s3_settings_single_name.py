# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The S3 endpoint has one name across the codebase.

`S3_URL` and `S3_PUBLIC_URL` were a second and a third name for it,
left pointing at a provider no longer in use. The screenshot job read
one of them, so it wrote to an endpoint nothing else could read back —
silently, because both names resolved to a valid-looking URL.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src"
SETTINGS = Path(__file__).resolve().parents[3] / "etc" / "settings.toml"

_RETIRED = ("S3_URL", "S3_PUBLIC_URL")


def test_no_module_reads_a_retired_name():
    offenders = []
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for name in _RETIRED:
            # `config["S3_URL"]` / `config.get("S3_URL")`, not a comment.
            if re.search(rf'\[["\']{name}["\']\]|get\(["\']{name}["\']', text):
                offenders.append(f"{path.name}: {name}")

    assert not offenders, offenders


def test_the_settings_no_longer_define_them():
    lines = [
        line
        for line in SETTINGS.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    ]
    defined = {line.split("=")[0].strip() for line in lines if "=" in line}

    assert not defined & set(_RETIRED)


def test_the_endpoint_is_read_under_its_one_name():
    """Both S3 callers must agree, or one of them writes where the other
    cannot look."""
    readers = [
        p
        for p in SRC.rglob("*.py")
        if 'config["S3_ENDPOINT_URL"]' in p.read_text(encoding="utf-8")
    ]

    names = {p.name for p in readers}
    assert {"extensions.py", "screenshots.py"} <= names, names
