# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: Apache-2.0
"""Generate ``aipress24_client/_generated.py`` from the API's OpenAPI spec.

The SDK's transport is hand-written and stable; only the drift-prone parts —
the list of collections and the typed models of the JSON bodies — are derived from
the spec, so the client can't fall out of step with ``/api/v1/openapi.json``.

Usage::

    python sdk/python/generate.py path/to/openapi.json

``make api-sdk`` exports the live spec and runs this; a unit test regenerates
in-memory and asserts the committed file still matches the spec.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_DETAIL_PATH = re.compile(r"^/api/v1/([^/{]+)/\{[^}]+\}$")

_SCALAR = {"string": "str", "integer": "int", "number": "float", "boolean": "bool"}

_HEADER = '''# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: Apache-2.0
"""AUTO-GENERATED from the OpenAPI spec by ``generate.py`` — do not edit.

Regenerate with ``make api-sdk``. A unit test asserts this file matches the
served ``/api/v1/openapi.json``.
"""

from __future__ import annotations

from typing import Any, TypedDict
'''


def collections_from_spec(spec: dict[str, Any]) -> dict[str, str]:
    """Map each collection name to its item-schema name, from detail endpoints.

    A detail endpoint ``GET /api/v1/<collection>/{id}`` responds with the
    resource's item schema — the authoritative source for both the collection
    list and the model to type.
    """
    out: dict[str, str] = {}
    for path, ops in spec.get("paths", {}).items():
        match = _DETAIL_PATH.match(path)
        if not match or "get" not in ops:
            continue
        schema = (
            ops["get"]
            .get("responses", {})
            .get("200", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema", {})
        )
        ref = schema.get("$ref", "")
        if ref:
            out[match.group(1)] = ref.rsplit("/", 1)[-1]
    return dict(sorted(out.items()))


def json_models(spec: dict[str, Any]) -> list[str]:
    """Name every schema a JSON request or response body reaches."""
    schemas = spec.get("components", {}).get("schemas", {})
    pending = [
        media["schema"]
        for operations in spec.get("paths", {}).values()
        for operation in operations.values()
        if isinstance(operation, dict)
        for body in (
            operation.get("requestBody", {}),
            *operation.get("responses", {}).values(),
        )
        if (media := body.get("content", {}).get("application/json"))
    ]
    found: set[str] = set()
    while pending:
        for name in _refs(pending.pop()) - found:
            found.add(name)
            pending.append(schemas[name])
    return sorted(found)


def _refs(node: Any) -> set[str]:
    if isinstance(node, list):
        return {name for item in node for name in _refs(item)}
    if not isinstance(node, dict):
        return set()
    own = {node["$ref"].rsplit("/", 1)[-1]} if "$ref" in node else set()
    return own.union(*(_refs(value) for value in node.values()))


def _py_type(prop: Any) -> str:
    if isinstance(prop, dict) and prop.get("nullable"):
        return f"{_py_type({**prop, 'nullable': False})} | None"
    if not isinstance(prop, dict):
        return "Any"
    if "$ref" in prop:
        return prop["$ref"].rsplit("/", 1)[-1]
    kind = prop.get("type")
    if kind in _SCALAR:
        return _SCALAR[kind]
    if kind == "array":
        return f"list[{_py_type(prop.get('items', {}))}]"
    if kind == "object":
        return "dict[str, Any]"
    return "Any"


def generate(spec: dict[str, Any]) -> str:
    """Return the source of ``_generated.py`` for the given OpenAPI ``spec``."""
    collections = collections_from_spec(spec)
    schemas = spec.get("components", {}).get("schemas", {})

    parts: list[str] = [_HEADER]
    for model in json_models(spec):
        props: dict[str, Any] = schemas.get(model, {}).get("properties", {})
        body = [f"class {model}(TypedDict, total=False):"]
        if props:
            body += [f"    {field}: {_py_type(sch)}" for field, sch in props.items()]
        else:
            body.append("    pass")
        parts.append("\n".join(body))

    coll = ", ".join(f'"{name}"' for name in collections)
    mapping = ", ".join(f'"{name}": {model}' for name, model in collections.items())
    parts.append(f"COLLECTIONS: tuple[str, ...] = ({coll},)")
    parts.append(f"RESOURCE_MODELS: dict[str, type] = {{{mapping}}}")

    return "\n\n\n".join(parts) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: generate.py path/to/openapi.json", file=sys.stderr)
        return 2
    spec = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    target = Path(__file__).parent / "aipress24_client" / "_generated.py"
    target.write_text(generate(spec), encoding="utf-8")
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
