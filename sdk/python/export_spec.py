# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Export the served ``/api/v1`` OpenAPI document to a JSON file.

A dev/build step for the SDK generator (``make api-sdk``); not shipped with
the client package. Uses the test config so it boots without a real database.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# The test config lives at the repo root, which isn't on the path when this
# script is run directly (its own directory is).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.flask.main import create_app
from app.modules.api_v1 import current_openapi_json
from tests.conftest import TestConfig


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: export_spec.py path/to/openapi.json", file=sys.stderr)
        return 2

    app = create_app(TestConfig)
    with app.app_context():
        spec = current_openapi_json()

    Path(argv[1]).write_text(
        json.dumps(spec, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"exported OpenAPI spec ({len(spec.get('paths', {}))} paths) to {argv[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
