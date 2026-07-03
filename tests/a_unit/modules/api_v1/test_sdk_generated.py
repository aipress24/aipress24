# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""The committed generated SDK must stay in sync with the OpenAPI spec.

Compares the committed ``aipress24_client/_generated.py`` (collections and
per-resource models) against the live spec. A mismatch means the API changed
without regenerating — run ``make api-sdk``.
"""

from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask

from app.modules.api_v1 import current_openapi_json

SDK_PATH = Path(__file__).resolve().parents[4] / "sdk" / "python"
if str(SDK_PATH) not in sys.path:
    sys.path.insert(0, str(SDK_PATH))

import generate  # noqa: E402
from aipress24_client import _generated  # noqa: E402


def test_generated_collections_and_models_match_spec(app: Flask) -> None:
    with app.app_context():
        spec = current_openapi_json()

    collections = generate.collections_from_spec(spec)
    assert collections, "no collections discovered in the spec"

    # The collection list and the resource->model map are in sync.
    assert set(_generated.COLLECTIONS) == set(collections)
    assert set(_generated.RESOURCE_MODELS) == set(collections)

    # Every model's fields match its spec schema exactly.
    schemas = spec["components"]["schemas"]
    for collection, model_name in collections.items():
        model = _generated.RESOURCE_MODELS[collection]
        assert model.__name__ == model_name
        spec_fields = set(schemas[model_name].get("properties", {}))
        generated_fields = set(model.__annotations__)
        assert generated_fields == spec_fields, (
            f"{model_name} is out of sync with the spec — run `make api-sdk`"
        )
