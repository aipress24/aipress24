# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""S3 traffic validates the endpoint's certificate in production.

`S3_USE_SSL` feeds both the transport and boto's `verify`, so leaving
it off meant every object travelled over a connection nobody checked —
which the flag's name does not say. Development keeps it off because
MinIO runs on plain http locally.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

SETTINGS = Path(__file__).resolve().parents[3] / "etc" / "settings.toml"
EXTENSIONS = (
    Path(__file__).resolve().parents[3] / "src" / "app" / "flask" / "extensions.py"
)


def _settings() -> dict:
    return tomllib.loads(SETTINGS.read_text(encoding="utf-8"))


def test_production_verifies_the_certificate():
    assert _settings()["production"]["S3_USE_SSL"] is True


def test_development_does_not_because_minio_is_plain_http():
    settings = _settings()

    assert settings["development"]["S3_USE_SSL"] is False
    assert settings["development"]["S3_ENDPOINT_URL"].startswith("http://")


def test_the_code_default_is_on():
    """An environment that says nothing gets verification; turning it
    off has to be asked for."""
    assert 'get("S3_USE_SSL", True)' in EXTENSIONS.read_text(encoding="utf-8")
