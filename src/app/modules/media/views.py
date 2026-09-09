# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import mimetypes
import re
from io import BytesIO

from advanced_alchemy.types.file_object import storages
from flask import send_file
from werkzeug.exceptions import NotFound
from werkzeug.wrappers import Response

from . import blueprint

# Storage names produced by create_file_object() — 64 hex chars (sha256)
# plus optional extension. Validated here to keep the endpoint from ever
# forwarding arbitrary paths to the storage backend.
_STORAGE_NAME_RE = re.compile(r"^[0-9a-f]{64}(?:\.[A-Za-z0-9]{1,10})?$")

# One year; the content at a given hash is immutable by construction.
_MAX_AGE = 31_536_000

# Types this endpoint will name. Anything else falls back to
# `application/octet-stream`, which no browser executes.
SERVABLE_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/avif",
        "application/pdf",
        "text/csv",
        "text/plain",
        "application/vnd.oasis.opendocument.spreadsheet",
    }
)


@blueprint.route("/<string:storage_name>")
def serve(storage_name: str) -> Response:
    if not _STORAGE_NAME_RE.match(storage_name):
        raise NotFound

    backend = storages.get_backend("s3")
    try:
        content = backend.get_content(storage_name)
    except (FileNotFoundError, OSError) as err:
        raise NotFound from err

    # Second lock, for the files stored before `safe_suffix` existed:
    # a name is not allowed to talk this endpoint into serving active
    # content. `guess_type` on a `.svg` or `.html` name returns a type
    # the browser will execute, on this origin, under the viewer's
    # session — so an unrecognised type is served as bytes, not as
    # something to run.
    guessed, _ = mimetypes.guess_type(storage_name)
    mimetype = guessed if guessed in SERVABLE_TYPES else None
    sha256 = storage_name.split(".", 1)[0]
    response = send_file(
        BytesIO(content),
        mimetype=mimetype or "application/octet-stream",
        download_name=storage_name,
        etag=sha256,
        max_age=_MAX_AGE,
        conditional=True,
    )
    # Override send_file's default `public` with `private` (content is
    # session-gated) and add `immutable` (URL is content-addressed, bytes
    # never change). Flask-Security's global hook still flips `private`
    # → `private=True` via dict-style assignment (cosmetic only).
    response.headers["Cache-Control"] = f"private, max-age={_MAX_AGE}, immutable"
    return response
