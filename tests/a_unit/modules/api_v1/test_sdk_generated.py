# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""The committed generated SDK must stay in sync with the OpenAPI spec.

Compares the committed ``openapi.json`` and ``aipress24_client/_generated.py``
against the live spec. A mismatch means the API changed without regenerating:
run ``make api-sdk``.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

from flask import Flask

from app.modules.api_v1 import current_openapi_json

SDK_PATH = Path(__file__).resolve().parents[4] / "sdk" / "python"
if str(SDK_PATH) not in sys.path:
    sys.path.insert(0, str(SDK_PATH))

import generate  # noqa: E402
from aipress24_client import _generated  # noqa: E402


def test_committed_spec_matches_the_served_one(app: Flask) -> None:
    with app.app_context():
        served = json.loads(json.dumps(current_openapi_json()))

    committed = json.loads((SDK_PATH / "openapi.json").read_text(encoding="utf-8"))

    assert committed == served, "openapi.json is out of date — run `make api-sdk`"


def test_generated_module_matches_the_committed_spec() -> None:
    spec = json.loads((SDK_PATH / "openapi.json").read_text(encoding="utf-8"))
    expected = generate.generate(spec)
    committed = Path(_generated.__file__).read_text(encoding="utf-8")

    # Compared as syntax trees: the committed file is also ruff-formatted.
    assert ast.dump(ast.parse(committed)) == ast.dump(ast.parse(expected)), (
        "_generated.py is out of date — run `make api-sdk`"
    )


def test_image_upload_documents_the_file_and_its_captions(app: Flask) -> None:
    with app.app_context():
        spec = current_openapi_json()

    path = "/api/v1/me/press-releases/{press_release_id}/images"
    content = spec["paths"][path]["post"]["requestBody"]["content"]
    assert list(content) == ["multipart/form-data"]
    name = content["multipart/form-data"]["schema"]["$ref"].rsplit("/", 1)[-1]
    properties = spec["components"]["schemas"][name]["properties"]
    assert set(properties) == {"image", "caption", "copyright"}
    assert properties["image"]["format"] == "binary"


def test_every_property_is_typed(app: Flask) -> None:
    with app.app_context():
        schemas = current_openapi_json()["components"]["schemas"]

    untyped = [
        f"{name}.{field}"
        for name, schema in schemas.items()
        for field, prop in schema.get("properties", {}).items()
        if "type" not in prop and "$ref" not in prop and "allOf" not in prop
    ]
    assert untyped == []
